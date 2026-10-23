import base64
import binascii
import contextlib
import hashlib
import io
import json
import os
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from datenputz import breach as BR
from datenputz import checker as C
from datenputz import cli
from datenputz import leakcheck as LC
from datenputz import net
from datenputz import report as R
from datenputz import brokers as B
from datenputz import shield as SH
from datenputz import store as S
from datenputz import vpn as V


def dns_query(name, qtype=1, qid=b"\x12\x34"):
    labels = b"".join(bytes([len(x)]) + x.encode() for x in name.split("."))
    return qid + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + labels + b"\x00" + struct.pack(">HH", qtype, 1)


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DATENPUTZ_HOME"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()


class X25519Tests(unittest.TestCase):
    def test_rfc7748_vectors(self):
        k = binascii.unhexlify("a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4")
        u = binascii.unhexlify("e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c")
        self.assertEqual(V._x25519(k, u).hex(), "c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552")

    def test_public_key_without_wg(self):
        alice = base64.b64encode(binascii.unhexlify(
            "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a")).decode()
        with mock.patch("shutil.which", return_value=None):
            pub = V.public_key(alice)
            self.assertEqual(base64.b64decode(pub).hex(),
                             "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a")
            self.assertEqual(len(base64.b64decode(V.private_key())), 32)


class VPNTests(Home):
    def setUp(self):
        super().setUp()
        with mock.patch("shutil.which", return_value=None):
            self.s = V.init("203.0.113.10")
            self.full = V.add_peer(self.s, "laptop")
            self.split = V.add_peer(self.s, "handy", "split", ["192.168.0.0/16"])
            self.mesh = V.add_peer(self.s, "nas", "mesh")

    def test_addresses_and_duplicates(self):
        self.assertEqual([p["address"] for p in self.s["peers"]], ["10.66.0.2", "10.66.0.3", "10.66.0.4"])
        with self.assertRaises(ValueError):
            V.add_peer(self.s, "laptop")

    def test_full_tunnel_has_killswitch(self):
        conf = V.client_conf(self.s, self.full)
        self.assertIn("AllowedIPs = 0.0.0.0/0, ::/0", conf)
        self.assertIn("PostUp = iptables -I OUTPUT ! -o %i", conf)
        self.assertIn("PresharedKey = " + self.full["psk"], conf)
        self.assertIn("DNS = 10.66.0.1", conf)

    def test_split_tunnel_excludes_lan_and_endpoint(self):
        import ipaddress
        nets = [ipaddress.ip_network(n) for n in V.allowed_ips(self.s, self.split)]
        def routed(ip):
            a = ipaddress.ip_address(ip)
            return any(a in n for n in nets if n.version == a.version)
        self.assertFalse(routed("192.168.1.10"))
        self.assertFalse(routed("203.0.113.10"))
        self.assertTrue(routed("8.8.8.8"))
        self.assertTrue(routed("10.66.0.1"))  # DNS-Filter im Tunnel
        self.assertNotIn("PostUp", V.client_conf(self.s, self.split))

    def test_mesh_only_vpn_network(self):
        self.assertEqual(V.allowed_ips(self.s, self.mesh), ["10.66.0.0/24", "fd66:6d70::/64"])

    def test_server_conf_and_export(self):
        conf = V.server_conf(self.s)
        self.assertEqual(conf.count("[Peer]"), 3)
        self.assertIn("MASQUERADE", conf)
        files = V.export(self.s)
        names = {f.name for f in files}
        self.assertTrue({"wg0.conf", "laptop.conf", "install-server.sh", "datenputz-dns.service"} <= names)
        self.assertEqual(oct((Path(self.tmp.name) / "vpn/export/laptop.conf").stat().st_mode & 0o777), "0o600")
        self.assertTrue(V.remove_peer(self.s, "nas"))
        self.assertEqual(V.server_conf(self.s).count("[Peer]"), 2)


class ShieldTests(Home):
    def test_parse_formats(self):
        text = "# Kommentar\n0.0.0.0 ads.example.com\n127.0.0.1 localhost\n*.track.example.org\nphish.example.net\n"
        self.assertEqual(SH.parse_list(text), {"ads.example.com", "track.example.org", "phish.example.net"})

    def test_blocklist_suffix_and_allow(self):
        bl = SH.Blocklist({"tracker.com", "bad.org"}, {"ok.tracker.com"})
        self.assertEqual(bl.match("x.y.tracker.com"), "tracker.com")
        self.assertIsNone(bl.match("ok.tracker.com"))
        self.assertIsNone(bl.match("goodtracker.com"))

    def test_blocked_answers(self):
        q = dns_query("ads.tracker.com", 1)
        _, name, qtype, end = SH.parse_query(q)
        self.assertEqual((name, qtype), ("ads.tracker.com", 1))
        a = SH.blocked_answer(q, end, 1)
        self.assertEqual(a[:2], b"\x12\x34")
        self.assertEqual(struct.unpack(">H", a[6:8])[0], 1)
        self.assertEqual(a[-4:], bytes(4))
        aaaa = SH.blocked_answer(dns_query("x.com", 28), end - 10, 28)
        self.assertEqual(aaaa[-16:], bytes(16))

    def test_filter_and_udp_upstream(self):
        # Fake-Upstream, der jede Anfrage mit Kennung "UP" beantwortet
        up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        up.bind(("127.0.0.1", 0))
        port = up.getsockname()[1]

        def answer():
            data, addr = up.recvfrom(512)
            up.sendto(data[:2] + b"\x81\x80UP", addr)
        threading.Thread(target=answer, daemon=True).start()
        flt = SH.Filter(SH.Blocklist({"tracker.com"}, set()), SH.Resolver(f"udp:127.0.0.1:{port}"))
        self.assertEqual(flt.handle(dns_query("example.org", qid=b"\xaa\xbb")), b"\xaa\xbb\x81\x80UP")
        # Zweite Anfrage aus dem Cache, mit neuer ID
        self.assertEqual(flt.handle(dns_query("example.org", qid=b"\x01\x02"))[:2], b"\x01\x02")
        blocked = flt.handle(dns_query("cdn.tracker.com"))
        self.assertEqual(blocked[-4:], bytes(4))
        stats = flt.save_stats()
        self.assertEqual((stats["blocked"], stats["allowed"]), (1, 2))
        up.close()

    def test_update_with_fake_download(self):
        bodies = {u: b"0.0.0.0 a.com\nb.com\n" for _, u in SH.SOURCES.values()}
        with mock.patch.object(net, "fetch", lambda url, **kw: (200, bodies[url])):
            counts = SH.update(["werbung", "phishing"])
        self.assertEqual(counts, {"werbung": 2, "phishing": 2})
        SH.add_custom("deny", ["extra.net"])
        SH.add_custom("allow", ["a.com"])
        bl = SH.Blocklist()
        self.assertEqual(bl.match("x.extra.net"), "extra.net")
        self.assertIsNone(bl.match("a.com"))

    def test_export_formats(self):
        self.assertEqual(SH.export("hosts", {"a.com"}), "0.0.0.0 a.com\n")
        self.assertIn('local-zone: "a.com." always_null', SH.export("unbound", {"a.com"}))
        self.assertIn("address=/a.com/::", SH.export("dnsmasq", {"a.com"}))

    def test_clean_url(self):
        clean, removed = SH.clean_url("https://shop.de/p?id=7&utm_source=nl&fbclid=abc&gclid=x")
        self.assertEqual(clean, "https://shop.de/p?id=7")
        self.assertEqual(set(removed), {"utm_source", "fbclid", "gclid"})


class BreachTests(Home):
    def test_password_k_anonymity(self):
        sha = hashlib.sha1(b"passwort123").hexdigest().upper()
        seen = []

        def fake(url, **kw):
            seen.append(url)
            return 200, f"0000000000000000000000000000000000A:1\r\n{sha[5:]}:4242\r\n".encode()
        with mock.patch.object(net, "fetch", fake):
            self.assertEqual(BR.password_count("passwort123"), 4242)
        self.assertTrue(seen[0].endswith("/range/" + sha[:5]))
        self.assertNotIn("passwort123", seen[0])


class CheckerTests(Home):
    def test_links(self):
        bl = SH.Blocklist({"evil.example"}, set())
        self.assertEqual(C.check_url("https://www.paypal.com/signin", bl)["verdict"], "unauffällig")
        self.assertEqual(C.check_url("https://www.sparkasse-koelnbonn.de", bl)["verdict"], "unauffällig")
        self.assertEqual(C.check_url("http://paypa1.com/login", bl)["verdict"], "gefährlich")
        self.assertEqual(C.check_url("https://paypal.com.konto-check.xyz/", bl)["verdict"], "gefährlich")
        self.assertEqual(C.check_url("https://dhl-zustellung.top/pay", bl)["verdict"], "verdächtig")
        self.assertEqual(C.check_url("https://cdn.evil.example/x", bl)["verdict"], "gefährlich")

    def test_scam_texts(self):
        bl = SH.Blocklist(set(), set())
        r = C.check_text("Hallo Mama, das ist meine neue Nummer. Kannst du heute dringend 900€ überweisen?", bl)
        self.assertEqual(r["verdict"], "gefährlich")
        self.assertEqual(C.check_text("Treffen wir uns morgen um acht im Café?", bl)["verdict"], "unauffällig")

    def test_files(self):
        d = Path(self.tmp.name)
        fake = d / "Rechnung.pdf.exe"
        fake.write_bytes(b"MZ\x90\x00rest")
        self.assertEqual(C.check_file(fake)["verdict"], "gefährlich")
        masked = d / "Foto.jpg"
        masked.write_bytes(b"MZ\x90\x00rest")
        self.assertEqual(C.check_file(masked)["verdict"], "gefährlich")
        ok = d / "Brief.pdf"
        ok.write_bytes(b"%PDF-1.7\n")
        r = C.check_file(ok)
        self.assertEqual((r["verdict"], r["type"]), ("unauffällig", "PDF"))


class LeakCheckTests(unittest.TestCase):
    def test_ipv6_and_dns_leak(self):
        info = {"1.2.3.4": {"org": "VPS GmbH"}, "2001:db8::1": {"org": "Telekom"}}
        with mock.patch.object(LC, "tunnels", return_value=["wg0"]), \
             mock.patch.object(LC, "public_ips", return_value=("1.2.3.4", "2001:db8::1", info)), \
             mock.patch.object(LC, "resolvers", return_value=["192.168.178.1"]):
            out = dict((t, lvl) for lvl, t in LC.run(expect_vpn=True, vpn_dns=["10.66.0.1"]))
        self.assertTrue(any("IPv6-Leck" in t and lvl == "bad" for t, lvl in out.items()))
        self.assertTrue(any("DNS-Leck" in t for t in out))

    def test_no_vpn(self):
        with mock.patch.object(LC, "tunnels", return_value=[]), \
             mock.patch.object(LC, "public_ips", return_value=("1.2.3.4", None, {})), \
             mock.patch.object(LC, "resolvers", return_value=[]):
            self.assertIn(("bad", "Kein VPN-Tunnel aktiv"), LC.run(expect_vpn=True))


class CliTests(Home):
    def test_password_and_link(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["password", "--length", "24", "--count", "2"])
            cli.main(["link", "http://paypa1.com/login"])
        lines = buf.getvalue().splitlines()
        self.assertEqual(len(lines[0]), 24)
        self.assertIn("GEFÄHRLICH", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
