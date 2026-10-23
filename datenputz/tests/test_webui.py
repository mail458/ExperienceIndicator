import contextlib
import hashlib
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
from unittest import mock
from urllib.parse import quote

from datenputz import cli
from datenputz import keystore as K
from datenputz import qr
from datenputz import score as SC
from datenputz import store as S
from datenputz import web
from datenputz import webui as U

EMAIL = "erika@example.org"


def mhash(q):
    return hashlib.sha256("".join("1" if v else "0" for r in q.matrix for v in r).encode()).hexdigest()[:16]


class QRTests(unittest.TestCase):
    def test_regression_against_verified_output(self):
        # Matrizen wurden für alle Masken gegen die Referenzbibliothek „qrcode“ geprüft
        q = qr.QR("https://ntfy.sh/datenputz-HoTiYJBWP8sgVdJcdvju5RCp")
        self.assertEqual((q.version, q.mask, mhash(q)), (4, 3, "f0e8c2909bd1d9f0"))
        q = qr.QR("x" * 600)
        self.assertEqual((q.version, q.mask, mhash(q)), (19, 0, "784a1c88f3adb194"))

    def test_structure_and_output(self):
        q = qr.QR("Hallo Wält", "L")
        self.assertEqual(q.size, 17 + 4 * q.version)
        m = q.matrix
        self.assertTrue(all(m[0][i] for i in range(7)))  # Finder oben links
        self.assertFalse(m[1][1])
        svg = q.svg()
        self.assertTrue(svg.startswith("<svg") and 'fill="#fff"' in svg and "style=" not in svg)
        self.assertIn("\033[", q.terminal())
        with self.assertRaises(ValueError):
            qr.QR("a" * 5000)


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DATENPUTZ_HOME"] = self.tmp.name
        self.st = S.Store()
        self.kc = mock.patch("shutil.which", return_value=None)  # kein echter Schlüsselbund im Test
        self.kc.start()

    def tearDown(self):
        self.kc.stop()
        self.st.close()
        self.tmp.cleanup()


class ScoreAndCardsTests(Home):
    def test_history_one_entry_per_day(self):
        SC.record(self.st)
        SC.record(self.st)
        self.assertEqual(len(self.st.get_kv("history")), 1)
        self.assertEqual(U.chart_svg(self.st.get_kv("history")), "")
        two = [{"d": "2026-10-01", "score": 10, "done": 1, "total": 5, "serious": 0},
               {"d": "2026-10-02", "score": 30, "done": 2, "total": 5, "serious": 0}]
        svg = U.chart_svg(two)
        self.assertIn("data-points", svg)
        self.assertIn("30 Punkte", svg)
        self.assertNotIn("style=", svg)

    def test_cards_setup_id_webform_and_skip(self):
        cards = U.today_cards(self.st)
        self.assertEqual(cards[0]["key"], "setup:profil")
        self.st.add_profile("erika", {"name": "Erika", "emails": [EMAIL], "country": "de"})
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["plan", "--only", "acxiom,adform"])
            cli.main(["run", "--outbox"])
        acx = self.st.latest(self.st.profile("erika")["_id"], "acxiom")
        from datenputz import engine as E
        E.Engine(self.st).mark(acx["id"], S.AWAITING_USER, "automatisch erkannt: Bitte Kopie Ihres Ausweises")
        cards = {c["key"]: c for c in U.today_cards(self.st)}
        idc = cards[f"req:{acx['id']}"]
        self.assertEqual(idc["kind"], "Ausweis verlangt")
        self.assertIn("Art. 12 Abs. 6", idc["letter"])
        form = next(c for c in cards.values() if c["kind"] == "Formular")
        self.assertTrue(form["open"].startswith("https://"))
        first = U.ordered_cards(self.st)[0]["key"]
        self.st.set_kv("today_skip", {"d": S.now().date().isoformat(), "keys": [first]})
        self.assertEqual(U.ordered_cards(self.st)[-1]["key"], first)


class WebTests(Home):
    def setUp(self):
        super().setUp()
        self.srv, self.app = web.make_server(self.tmp.name, "127.0.0.1", 0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def req(self, method, path, headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=10)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, dict(r.getheaders()), data

    def login(self):
        s, h, _ = self.req("GET", "/login?t=" + self.app.token)
        self.ck = {"Cookie": h["Set-Cookie"].split(";")[0]}
        return h["Location"]

    def get(self, path):
        s, h, d = self.req("GET", path, self.ck)
        return s, d.decode()

    def post(self, path, **data):
        body = "&".join(f"{k}={quote(str(v))}" for k, v in {"csrf": self.app.csrf, **data}.items())
        s, h, _ = self.req("POST", path, {**self.ck, "Content-Type": "application/x-www-form-urlencoded"}, body)
        return s, h.get("Location")

    def test_static_and_pwa(self):
        s, h, d = self.req("GET", "/manifest.webmanifest")
        self.assertEqual(json.loads(d)["start_url"], "/heute")
        self.assertIn("manifest-src 'self'", h["Content-Security-Policy"])
        self.assertTrue(self.req("GET", "/static/icon-512.png")[2].startswith(b"\x89PNG"))
        self.assertIn(b"caches", self.req("GET", "/sw.js")[2])
        self.assertEqual(self.req("GET", "/offline")[0], 200)
        self.assertEqual(self.req("GET", "/job.json")[0], 401)

    def test_wizard_end_to_end(self):
        self.assertEqual(self.login(), "/einrichten")  # ohne Profil direkt in die Einrichtung
        s, page = self.get("/")
        self.assertIn("Einrichtung starten", page)
        # Profil für andere Person ohne Einwilligung wird abgelehnt
        self.post("/einrichten/profil", key="neu", name="Kind", emails="kind@example.org", on_behalf_of_by="Erika")
        self.assertEqual(self.st.profiles(), [])
        s, loc = self.post("/einrichten/profil", key="neu", name="Erika Mustermann", emails=f"{EMAIL}, alt@example.org",
                           addresses="Heidestraße 17, 51147 Köln", country="de", language="de", plan_now="1")
        self.assertEqual(loc, "/einrichten?s=mail")
        p = S.Store().profile("erika-mustermann")
        self.assertEqual(p["emails"], [EMAIL, "alt@example.org"])
        self.assertGreater(len(S.Store().requests()), 300)
        # Mail mit Vorlage; Passwort wird gespeichert, aber nie angezeigt
        self.post("/einrichten/mail", provider="gmx", smtp_host="", smtp_user=EMAIL, smtp_password="GeheimesPW-123",
                  smtp_security="starttls", daily_limit="30", action="save")
        cfg = S.Store().config()
        self.assertEqual((cfg["smtp"]["host"], cfg["imap"]["host"], cfg["daily_limit"]), ("mail.gmx.net", "imap.gmx.net", 30))
        self.assertEqual(K.get("smtp", S.Store()), "GeheimesPW-123")
        s, page = self.get("/einrichten?s=mail")
        self.assertNotIn("GeheimesPW-123", page)
        self.assertIn("✓ hinterlegt", page)
        # Leak-Quellen: falscher Schlüssel abgelehnt, richtige Zustimmung gespeichert
        self.post("/einrichten/leaks", hibp_key="falsch")
        self.assertIsNone(K.get("hibp", S.Store()))
        self.post("/einrichten/leaks", hibp_key="a" * 32, src_xposedornot="1", monitor_emails="beruf@firma.de\nkeine-adresse")
        cfg = S.Store().config()
        self.assertEqual(cfg["darkweb_sources"], ["hibp", "xposedornot"])
        self.assertIn("xposedornot", cfg["darkweb_consent"])
        self.assertEqual(cfg["monitor_emails"], ["beruf@firma.de"])
        # Handy: ntfy mit geheimem Thema und QR-Code
        self.post("/einrichten/push", channel="ntfy", ntfy_server="https://ntfy.sh")
        topic = S.Store().config()["notify"]["channels"][0]["topic"]
        self.assertTrue(topic.startswith("datenputz-"))
        s, page = self.get("/einrichten?s=push")
        self.assertIn("<svg", page)
        self.post("/einrichten/push", channel="ntfy", ntfy_server="javascript:alert(1)")
        self.assertEqual(S.Store().config()["notify"]["channels"][0]["topic"], topic)  # unverändert
        # Automatik: ungültige Uhrzeit
        self.post("/einrichten/auto", time="99:99", action="install")
        self.assertIsNone(S.Store().get_kv("schedule"))
        s, page = self.get("/einrichten")
        self.assertIn("von 5 Schritten erledigt", page)

    def test_pages_detail_filters_and_actions(self):
        self.st.add_profile("erika", {"name": "Erika", "emails": [EMAIL], "country": "de"})
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["plan"])
            cli.main(["run", "--outbox"])
        self.login()
        for path in ("/", "/heute", "/aufgaben", "/anfragen", "/anfragen?f=du", "/anfragen?f=erledigt&page=99",
                     "/anfragen?q=acxiom", "/leaks", "/pruefen", "/system", "/einrichten?s=profil", "/einrichten?s=leaks",
                     "/einrichten?s=auto"):
            s, page = self.get(path)
            self.assertEqual(s, 200, path)
            self.assertNotIn('style="', page, path)
            self.assertNotIn("<script>", page, path)
        s, page = self.get("/anfragen?f=alle")
        self.assertIn("Seite 1 von", page)
        self.assertIn("Acxiom", self.get("/anfragen?q=acxiom")[1])
        rid = self.st.latest(self.st.profile("erika")["_id"], "acxiom")["id"]
        s, page = self.get(f"/anfrage/{rid}")
        self.assertIn("Verlauf", page)
        self.assertIn("Antrag gesendet", page)
        self.assertEqual(self.get("/anfrage/999999")[0], 404)
        self.assertEqual(self.post("/heute/skip", key="vault")[1], "/heute")
        self.assertIn("vault", S.Store().get_kv("today_skip")["keys"])
        self.post("/manual-done")
        self.assertIsNotNone(S.Store().get_kv("manual_checks_done"))
        self.post("/complaint-filed", id=rid)
        self.assertEqual(S.Store().get_kv("complaints_filed"), [rid])
        self.assertEqual(self.post("/complaint-filed", id="x")[0], 400)
        self.assertEqual(self.post("/unbekannt")[0], 404)
        s, h, d = self.req("GET", "/job.json", self.ck)
        self.assertIn("running", json.loads(d))

    def test_persistent_link_keeps_session(self):
        a = web.App(self.tmp.name, token="fest")
        b = web.App(self.tmp.name, token="fest")
        self.assertEqual(a.session, b.session)
        self.assertNotEqual(web.App(self.tmp.name).session, web.App(self.tmp.name).session)


if __name__ == "__main__":
    unittest.main()
