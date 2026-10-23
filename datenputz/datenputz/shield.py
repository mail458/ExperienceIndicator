"""Bedrohungsschutz: DNS-Filter gegen Werbung, Tracker, Malware und Phishing.

Entspricht NordVPNs „Threat Protection (Lite)“: Domains von Sperrlisten werden
schon bei der Namensauflösung blockiert – für alle Programme und, über den
eigenen VPN-Server, für alle Geräte. Erlaubte Anfragen gehen verschlüsselt
per DNS-over-HTTPS (RFC 8484) an den Upstream-Resolver.

Daneben: Export der Liste für hosts-Datei, Pi-hole/AdGuard, dnsmasq, Unbound,
und das Entfernen von Tracking-Parametern aus Links („URL cleaning“).
"""
import json
import signal
import socket
import socketserver
import struct
import threading
import time
from collections import Counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import net
from . import store as S

SOURCES = {
    "werbung": ("Werbung, Tracker, Telemetrie – HaGeZi Multi PRO",
                "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/pro-onlydomains.txt"),
    "bedrohungen": ("Malware, Phishing, Betrug, Kryptojacking – HaGeZi Threat Intelligence Feeds",
                    "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/tif.medium-onlydomains.txt"),
    "phishing": ("Aktive Phishing-Domains – Phishing.Database",
                 "https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/master/phishing-domains-ACTIVE.txt"),
}
DEFAULT_UPSTREAM = "https://dns.quad9.net/dns-query"  # Quad9 (Schweiz), filtert zusätzlich Malware


def folder():
    d = S.home() / "shield"
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_list(text):
    """Versteht reine Domainlisten und hosts-Format ("0.0.0.0 example.com")."""
    out = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if not line or line.startswith("!"):
            continue
        parts = line.split()
        d = parts[1] if len(parts) > 1 and parts[0] in ("0.0.0.0", "127.0.0.1", "::", "::1") else parts[0]
        d = d.lstrip("*.").rstrip(".")
        if "." in d and d not in ("localhost", "localhost.localdomain", "broadcasthost", "0.0.0.0"):
            out.add(d)
    return out


def update(names=None):
    """Listen herunterladen und zu blocklist.txt zusammenführen. Gibt {name: anzahl} zurück."""
    names = names or list(SOURCES)
    counts, merged = {}, set()
    for name in names:
        _, url = SOURCES[name]
        _, body = net.fetch(url, timeout=120)
        domains = parse_list(body.decode("utf-8", "replace"))
        (folder() / f"{name}.txt").write_text("\n".join(sorted(domains)) + "\n", encoding="utf-8")
        counts[name] = len(domains)
        merged |= domains
    (folder() / "blocklist.txt").write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")
    (folder() / "sources.json").write_text(json.dumps({"updated": S.iso(S.now()), "counts": counts}))
    return counts


def _read(name):
    p = folder() / name
    return parse_list(p.read_text(encoding="utf-8")) if p.exists() else set()


class Blocklist:
    def __init__(self, domains=None, allow=None):
        self.deny = set(domains) if domains is not None else _read("blocklist.txt") | _read("deny.txt")
        self.allow = set(allow) if allow is not None else _read("allow.txt")

    def __len__(self):
        return len(self.deny)

    @staticmethod
    def _suffixes(name):
        parts = name.lower().rstrip(".").split(".")
        return [".".join(parts[i:]) for i in range(len(parts) - 1)]

    def match(self, name):
        """Gibt den Sperrlisteneintrag zurück, der `name` blockiert, sonst None."""
        sfx = self._suffixes(name)
        if any(s in self.allow for s in sfx):
            return None
        return next((s for s in sfx if s in self.deny), None)


def add_custom(kind, domains):
    p = folder() / ("allow.txt" if kind == "allow" else "deny.txt")
    cur = _read(p.name) | {d.lower().strip() for d in domains}
    p.write_text("\n".join(sorted(cur)) + "\n", encoding="utf-8")
    return len(cur)


def export(fmt, domains):
    lines = sorted(domains)
    if fmt == "hosts":
        return "".join(f"0.0.0.0 {d}\n" for d in lines)
    if fmt == "dnsmasq":
        return "".join(f"address=/{d}/0.0.0.0\naddress=/{d}/::\n" for d in lines)
    if fmt == "unbound":
        return "server:\n" + "".join(f'  local-zone: "{d}." always_null\n' for d in lines)
    if fmt == "domains":  # Pi-hole, AdGuard Home, NextDNS, Blocky
        return "\n".join(lines) + "\n"
    raise ValueError(fmt)


# --------------------------------------------------------------------------
# DNS-Paketverarbeitung (RFC 1035) – nur das Nötigste für einen Filter.
def parse_query(data):
    """(id, name, qtype, ende_der_frage) aus einer DNS-Anfrage."""
    if len(data) < 17:
        raise ValueError("zu kurz")
    pos, labels = 12, []
    while True:
        n = data[pos]
        if n == 0:
            pos += 1
            break
        if n & 0xC0:
            raise ValueError("Kompression in Frage")
        labels.append(data[pos + 1:pos + 1 + n].decode("ascii", "replace"))
        pos += 1 + n
    qtype, _ = struct.unpack(">HH", data[pos:pos + 4])
    return data[:2], ".".join(labels).lower(), qtype, pos + 4


def build_query(name, qtype=1, qid=b"\x00\x00"):
    """Einfache DNS-Anfrage mit Rekursionswunsch (für Tests und den Selbsttest)."""
    labels = b"".join(bytes([len(x)]) + x.encode("ascii") for x in name.strip(".").split("."))
    return qid + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + labels + b"\x00" + struct.pack(">HH", qtype, 1)


def blocked_answer(query, qend, qtype):
    """Antwort 0.0.0.0 bzw. :: (wie Pi-hole „NULL“); andere Typen ohne Daten."""
    rd = query[2] & 0x01
    flags = struct.pack(">BB", 0x80 | 0x04 | rd, 0x80)  # QR, AA, RD übernehmen, RA
    question = query[12:qend]
    answers = b""
    if qtype == 1:
        answers = b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 300, 4) + bytes(4)
    elif qtype == 28:
        answers = b"\xc0\x0c" + struct.pack(">HHIH", 28, 1, 300, 16) + bytes(16)
    header = query[:2] + flags + struct.pack(">HHHH", 1, 1 if answers else 0, 0, 0)
    return header + question + answers


class Resolver:
    """Leitet erlaubte Anfragen per DoH (Standard) oder UDP weiter, mit kleinem Cache."""

    def __init__(self, upstream=DEFAULT_UPSTREAM, cache_seconds=60):
        self.upstream = upstream
        self.cache, self.ttl, self.lock = {}, cache_seconds, threading.Lock()

    def resolve(self, query, name, qtype):
        key = (name, qtype)
        with self.lock:
            hit = self.cache.get(key)
        if hit and hit[0] > time.monotonic():
            return query[:2] + hit[1][2:]
        if self.upstream.startswith("https://"):
            _, resp = net.fetch(self.upstream, data=query, timeout=10, method="POST",
                                headers={"Content-Type": "application/dns-message",
                                         "Accept": "application/dns-message"})
        else:
            host, _, port = self.upstream.removeprefix("udp:").partition(":")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(5)
                s.sendto(query, (host, int(port or 53)))
                resp, _ = s.recvfrom(4096)
        with self.lock:
            if len(self.cache) > 20000:
                self.cache.clear()
            self.cache[key] = (time.monotonic() + self.ttl, resp)
        return query[:2] + resp[2:]


class Filter:
    def __init__(self, blocklist, resolver, verbose=False):
        self.bl, self.res, self.verbose = blocklist, resolver, verbose
        self.stats, self.top, self.lock = Counter(), Counter(), threading.Lock()

    def handle(self, data):
        qid, name, qtype, qend = parse_query(data)
        hit = self.bl.match(name)
        with self.lock:
            self.stats["blocked" if hit else "allowed"] += 1
            if hit:
                self.top[hit] += 1
        if hit:
            if self.verbose:
                print(f"  blockiert  {name}  ({hit})", flush=True)
            return blocked_answer(data, qend, qtype)
        return self.res.resolve(data, name, qtype)

    def save_stats(self):
        p = folder() / "stats.json"
        old = json.loads(p.read_text()) if p.exists() else {"blocked": 0, "allowed": 0, "top": {}}
        with self.lock:
            old["blocked"] += self.stats["blocked"]
            old["allowed"] += self.stats["allowed"]
            top = Counter(old["top"]) + self.top
            old["top"] = dict(top.most_common(50))
            old["updated"] = S.iso(S.now())
            self.stats.clear()
            self.top.clear()
        p.write_text(json.dumps(old))
        return old


def _interrupt(*_):
    raise KeyboardInterrupt


def serve(host="127.0.0.1", port=5353, upstream=DEFAULT_UPSTREAM, verbose=False):
    bl = Blocklist()
    if not len(bl):
        raise SystemExit("Keine Sperrliste vorhanden. Zuerst: python -m datenputz shield update")
    flt = Filter(bl, Resolver(upstream), verbose)

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            data, sock = self.request
            try:
                sock.sendto(flt.handle(data), self.client_address)
            except Exception as e:  # fehlerhafte Pakete oder Upstream-Ausfall: SERVFAIL
                if verbose:
                    print("  Fehler:", e, flush=True)
                if len(data) >= 12:
                    sock.sendto(data[:2] + b"\x81\x82" + b"\x00" * 8, self.client_address)

    socketserver.ThreadingUDPServer.allow_reuse_address = True
    with socketserver.ThreadingUDPServer((host, port), Handler) as srv:
        print(f"DNS-Filter läuft auf {host}:{port} · {len(bl):,} gesperrte Domains · Upstream {upstream}".replace(",", "."))
        print("System-DNS auf diese Adresse stellen. Beenden mit Strg+C.")
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        signal.signal(signal.SIGTERM, _interrupt)  # systemd stop → Statistik sichern
        try:
            while t.is_alive():
                time.sleep(60)
                flt.save_stats()
        except KeyboardInterrupt:
            pass
        finally:
            s = flt.save_stats()
            print(f"\nGesamt: {s['blocked']} blockiert, {s['allowed']} erlaubt.")
            srv.shutdown()


# --------------------------------------------------------------------------
TRACKING_PARAMS = {
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid", "msclkid", "yclid", "twclid", "ttclid",
    "li_fat_id", "igshid", "mc_cid", "mc_eid", "_hsenc", "_hsmi", "mkt_tok", "vero_id", "oly_anon_id",
    "oly_enc_id", "rb_clickid", "s_cid", "wickedid", "ns_mchannel", "ns_source", "ns_campaign", "spm",
    "si", "ref_src", "srsltid", "epik", "_ga", "_gl", "trk", "trkcampaign", "sc_campaign",
}


def clean_url(url):
    """Entfernt Tracking-Parameter (utm_*, fbclid, gclid …). Gibt (sauber, entfernt) zurück."""
    parts = urlsplit(url)
    kept, removed = [], []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        if k.lower().startswith(("utm_", "pk_", "mtm_", "hsa_")) or k.lower() in TRACKING_PARAMS:
            removed.append(k)
        else:
            kept.append((k, v))
    return urlunsplit(parts._replace(query=urlencode(kept, doseq=True))), removed
