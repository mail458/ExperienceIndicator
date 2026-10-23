import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

from datenputz import aliases as AL
from datenputz import breach as BR
from datenputz import brokers as B
from datenputz import cli
from datenputz import keystore as K
from datenputz import net
from datenputz import report as R
from datenputz import store as S
from datenputz import vault as VA

EMAIL = "erika@example.org"
ADOBE = {"Name": "Adobe", "Title": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04",
         "DataClasses": ["Email addresses", "Password hints", "Passwords"], "IsVerified": True}
SPAM = {"Name": "SpamList", "Title": "Spam", "Domain": "", "BreachDate": "2020-01-01",
        "DataClasses": ["Email addresses"], "IsSpamList": True}
CANVA = {"Name": "Canva", "Title": "Canva", "Domain": "canva.com", "BreachDate": "2019-05-24",
         "DataClasses": ["Email addresses", "Names", "Passwords"]}


def sha(pw):
    return hashlib.sha1(pw.encode()).hexdigest().upper()


class Router:
    """Ersetzt net.fetch: URL-Teilstring → (status, body) oder Exception."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, **kw):
        self.calls.append(url)
        for part, resp in self.routes.items():
            if part in url:
                if isinstance(resp, Exception):
                    raise resp
                status, body = resp
                return status, body if isinstance(body, bytes) else json.dumps(body).encode()
        return 404, b""


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DATENPUTZ_HOME"] = self.tmp.name
        self.st = S.Store()

    def tearDown(self):
        self.tmp.cleanup()


class AssessTests(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(BR.assess(["Passwords"], "x.de")[0], "hoch")
        self.assertEqual(BR.assess(["Credit cards"], "x.de")[0], "kritisch")
        self.assertEqual(BR.assess(["Email addresses"], "x.de")[0], "info")
        self.assertEqual(BR.assess(["Passwords"], "x.de", {"IsSpamList": True})[0], "info")
        sev, actions = BR.assess([], "x.de", {"IsStealerLog": True})
        self.assertEqual((sev, actions[0]), ("kritisch", BR.STEALER_ACTION))
        sev, actions = BR.assess(["Phone numbers", "Physical addresses"], "x.de")
        self.assertEqual(sev, "mittel")
        self.assertEqual(len(actions), 2)


class MonitorTests(Home):
    def routes(self):
        return {
            "breachedaccount/": (200, [ADOBE, SPAM]),
            "pasteaccount/": (200, [{"Source": "Pastebin", "Id": "8Q0BvKD8", "Title": "dump", "Date": "2014-03-04T19:14:54Z",
                                     "EmailCount": 139}]),
            "stealerlogsbyemail/": net.HTTPError(403),
            "xposedornot.com": (200, {"breaches": [["Canva", "Adobe"]], "email": EMAIL}),
            "leakcheck.io": (200, {"success": True, "found": 1, "fields": ["username", "password"],
                                   "sources": [{"name": "Collection1", "date": "2019-01"}]}),
            "hudsonrock.com": (200, {"message": "found", "stealers": [
                {"date_compromised": "2023-02-01T10:00:00.000Z", "operating_system": "Windows 10",
                 "computer_name": "PC", "antiviruses": ["Defender"]}]}),
        }

    def test_all_sources_and_dedup(self):
        r = Router(self.routes())
        with mock.patch.object(net, "fetch", r), mock.patch("time.sleep"):
            new, errors = BR.monitor(self.st, [EMAIL], list(BR.SOURCES), key="K" * 32, pause=0)
            kinds = sorted((f["source"], f["kind"], f["severity"]) for f in new)
            self.assertIn(("hibp", "breach", "hoch"), kinds)       # Adobe mit Passwörtern
            self.assertIn(("hibp", "breach", "info"), kinds)       # Spam-Liste
            self.assertIn(("hibp", "paste", "hoch"), kinds)
            self.assertIn(("hudsonrock", "infostealer", "kritisch"), kinds)
            self.assertIn(("leakcheck", "breach", "hoch"), kinds)  # Feld „password“
            self.assertEqual(sum(1 for f in new if f["source"] == "xposedornot"), 2)
            self.assertTrue(any("Stealer Logs" in e for e in errors))
            again, _ = BR.monitor(self.st, [EMAIL], list(BR.SOURCES), key="K" * 32, pause=0)
            self.assertEqual(again, [])
        self.assertFalse(any("subscription" in c for c in r.calls))  # pause=0 → keine Tarifabfrage

    def test_stealer_logs_when_entitled(self):
        routes = self.routes()
        routes["stealerlogsbyemail/"] = (200, ["netflix.com", "spotify.com"])
        with mock.patch.object(net, "fetch", Router(routes)):
            new, errors = BR.monitor(self.st, [EMAIL], ["hibp"], key="K", pause=0)
        stealers = [f for f in new if f["kind"] == "stealer"]
        self.assertEqual({f["key"] for f in stealers}, {"netflix.com", "spotify.com"})
        self.assertTrue(all(f["severity"] == "kritisch" for f in stealers))
        self.assertEqual(errors, [])

    def test_source_failure_does_not_stop_others(self):
        routes = {"xposedornot.com": net.HTTPError(500), "leakcheck.io": (200, {"success": True, "fields": [],
                                                                                "sources": [{"name": "X"}]})}
        with mock.patch.object(net, "fetch", Router(routes)):
            new, errors = BR.monitor(self.st, [EMAIL], ["xposedornot", "leakcheck"], pause=0)
        self.assertEqual(len(new), 1)
        self.assertTrue(errors[0].startswith("xposedornot"))

    def test_invalid_key_aborts(self):
        with mock.patch.object(net, "fetch", Router({"breachedaccount/": net.HTTPError(401)})):
            with self.assertRaises(SystemExit):
                BR.monitor(self.st, [EMAIL], ["hibp"], key="bad", pause=0)

    def test_retry_after_is_respected(self):
        calls = iter([net.HTTPError(429, headers={"Retry-After": "3"}), (200, b"[]")])

        def fake(url, **kw):
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r
        with mock.patch.object(net, "fetch", fake), mock.patch("time.sleep") as sleep:
            BR.set_rate(0)
            self.assertEqual(BR.account_breaches(EMAIL, "K"), [])
        sleep.assert_any_call(3)

    def test_domain_monitoring(self):
        routes = {"breacheddomain/firma.de": (200, {"info": ["Adobe"], "chef": ["Canva", "Adobe"]}),
                  "stealerlogsbyemaildomain/firma.de": (200, {"chef": ["login.bank.de"]})}
        with mock.patch.object(net, "fetch", Router(routes)):
            new, _ = BR.monitor(self.st, [], ["hibp"], key="K", domains=["firma.de"], pause=0)
        subjects = {(f["subject"], f["kind"]) for f in new}
        self.assertIn(("chef@firma.de", "stealer"), subjects)
        self.assertEqual(sum(1 for f in new if f["kind"] == "domain_breach"), 3)


class AliasTests(Home):
    def test_leak_of_alias_points_to_service(self):
        self.st.add_alias("netflix.x7@example.org", "netflix.com")
        with mock.patch.object(net, "fetch", Router({"breachedaccount/": (200, [CANVA])})):
            new, _ = BR.monitor(self.st, ["netflix.x7@example.org"], ["hibp"], key="K", pause=0)
        f = new[0]
        self.assertEqual(f["alias_service"], "netflix.com")
        self.assertIn("weitergegeben", f["actions"][0][1])
        self.assertEqual(f["severity"], "hoch")

    def test_inbox_scan(self):
        self.st.add_alias("shop.a1@example.org", "shop.de", related=["shop-mail.de"])

        def mail(sender):
            m = EmailMessage()
            m["From"], m["To"], m["Subject"] = sender, "Shop A1 <shop.a1@example.org>", "Hallo"
            m.set_content("x")
            return m
        found = AL.scan(self.st, [mail("news@shop.de"), mail("info@news.shop-mail.de"),
                                  mail("deals@fremdfirma.com"), mail("MAILER-DAEMON@mx.example.org")])
        self.assertEqual([f["key"] for f in found], ["fremdfirma.com"])
        self.assertEqual(AL.scan(self.st, [mail("deals@fremdfirma.com")]), [])  # nicht doppelt

    def test_alias_request_creates_erasure(self):
        self.st.add_profile("erika", {"name": "Erika Mustermann", "emails": [EMAIL], "country": "de"})
        self.st.add_alias("shop.a1@example.org", "shop.de")
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["alias", "request", "shop.a1@example.org", "--email", "datenschutz@shop.de"])
        r = self.st.requests()[0]
        self.assertEqual((r["broker_id"], r["kind"]), ("custom-shop-de", "erasure"))
        self.assertEqual(B.by_id()["custom-shop-de"]["email"], "datenschutz@shop.de")
        from datenputz import engine as E

        class Box:
            dry_run, sent = True, []

            def send(self, msg, name):
                self.sent.append(msg)

            def close(self):
                pass
        box = Box()
        E.Engine(self.st, box).run()
        body = box.sent[0].get_content()
        self.assertIn("shop.a1@example.org", body)
        self.assertNotIn(EMAIL, body.split("Zur Identifikation:")[1])  # Hauptadresse bleibt verborgen


class VaultTests(Home):
    def write(self, name, text):
        p = Path(self.tmp.name) / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_bitwarden_audit(self):
        csv_text = ("folder,favorite,type,name,notes,fields,reprompt,login_uri,login_username,login_password,login_totp\n"
                    ",,login,Mail,,,,https://mail.example.org,erika,Tr0ub4dor&3-sehr-lang!,otpauth://x\n"
                    ",,login,Shop A,,,,https://shop-a.de,erika,Gleich1234567!Gleich,\n"
                    ",,login,Shop B,,,,https://shop-b.de,erika,Gleich1234567!Gleich,\n"
                    ",,login,Forum,,,,https://forum.de,erika,erika2020,\n"
                    ",,login,Adobe,,,,https://www.adobe.com,erika@example.org,KomplettZufaellig#9813xyzQ,\n"
                    ",,login,Leer,,,,https://leer.de,erika,,\n")
        path = self.write("bw.csv", csv_text)
        entries = VA.load(path)
        self.assertEqual(len(entries), 5)
        self.assertFalse(any("Gleich1234567" in json.dumps(e, default=str) for e in entries))  # nur Hashes
        pwned = sha("erika2020")

        def fake(url, **kw):
            prefix = url.rsplit("/", 1)[-1]
            body = f"{pwned[5:]}:5120\r\n" if prefix == pwned[:5] else "0000000000000000000000000000000000A:0\r\n"
            return 200, body.encode()
        with mock.patch.object(net, "fetch", fake):
            results, summary = VA.audit(entries, [ADOBE])
        by = {r["name"]: r for r in results}
        self.assertEqual(by["Forum"]["severity"], "kritisch")
        self.assertTrue(any("5.120" in t for _, t in by["Forum"]["issues"]))
        self.assertEqual(by["Shop A"]["severity"], "hoch")
        self.assertIn("Shop B", by["Shop A"]["issues"][0][1])
        self.assertEqual(by["Adobe"]["severity"], "hoch")  # Leak, Änderungsdatum unbekannt
        self.assertNotIn("Mail", by)
        self.assertEqual((summary["total"], summary["reused"], summary["kritisch"]), (5, 1, 1))
        self.assertNotIn("erika2020", json.dumps(results))

    def test_firefox_dates_and_shred(self):
        # Adobe-Passwort 2012 gesetzt (vor dem Leak 2013) → kritisch; 2020 gesetzt → in Ordnung
        csv_text = ('"url","username","password","httpRealm","formActionOrigin","guid","timeCreated",'
                    '"timeLastUsed","timePasswordChanged"\n'
                    '"https://adobe.com","a","Xq7#vLp2!mZr9@wKt4","","","{1}","1","1","1330000000000"\n'
                    '"https://www.adobe.com","b","Yq7#vLp2!mZr9@wKt5","","","{2}","1","1","1590000000000"\n')
        path = self.write("ff.csv", csv_text)
        entries = VA.load(path)
        results, summary = VA.audit(entries, [ADOBE], offline=True)
        self.assertEqual(len(results), 2)
        sev = sorted((r["severity"] for r in results), key=BR.RANK.get)
        self.assertEqual(sev[0], "kritisch")  # vor dem Leak gesetzt
        self.assertTrue(all(i[0] != "kritisch" for i in results[1]["issues"]))
        VA.shred(path)
        self.assertFalse(path.exists())
        self.assertEqual(list(Path(self.tmp.name).glob("*.csv")), [])

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            VA.load(self.write("x.csv", "a,b\n1,2\n"))

    def test_cli_vault_offline_report(self):
        path = self.write("chrome.csv", "name,url,username,password,note\nX,https://x.de,u,kurz,\n")
        out = Path(self.tmp.name) / "audit.html"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["breach", "vault", str(path), "--offline", "-o", str(out), "--shred"])
        self.assertIn("schwach", buf.getvalue())
        self.assertNotIn("kurz,", out.read_text())
        self.assertFalse(path.exists())
        self.assertEqual(self.st.get_kv("vault_audit")["total"], 1)


class KeystoreTests(Home):
    def test_fallback_env_and_delete(self):
        with mock.patch("shutil.which", return_value=None):
            where = K.put("hibp", "abc", self.st)
            self.assertIn("config.json", where)
            self.assertEqual(K.get("hibp", self.st), "abc")
            self.assertEqual(oct(self.st.config_path.stat().st_mode & 0o777), "0o600")
            with mock.patch.dict(os.environ, {"HIBP_API_KEY": "env"}):
                self.assertEqual(K.get("hibp", self.st), "env")
            K.delete("hibp", self.st)
            self.assertIsNone(K.get("hibp", self.st))

    def test_legacy_config_key(self):
        self.st.save_config({"hibp_api_key": "old"})
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(K.get("hibp", self.st), "old")


class CliTests(Home):
    def test_email_plan_report(self):
        self.st.add_profile("erika", {"name": "Erika", "emails": [EMAIL], "country": "de"})
        routes = {"xposedornot.com": (200, {"breaches": [["Canva"]]}),
                  "leakcheck.io": (200, {"success": True, "fields": ["password"], "sources": [{"name": "Canva"}]})}
        buf = io.StringIO()
        with mock.patch.object(net, "fetch", Router(routes)), mock.patch("time.sleep"), \
                mock.patch.object(K, "get", return_value=None), contextlib.redirect_stdout(buf):
            cli.main(["breach", "email", "--sources", "xposedornot,leakcheck", "--yes"])
            cli.main(["breach", "plan"])
            cli.main(["breach", "manual"])
        out = buf.getvalue()
        self.assertIn("Gesamt: 2 Funde", out)
        self.assertIn("Passwort bei Canva", out)
        self.assertIn("sec.hpi.de", out)
        self.assertEqual(set(self.st.config()["darkweb_consent"]), {"xposedornot", "leakcheck"})
        page = R.render(self.st, B.by_id())
        self.assertIn("Leak-Funde", page)
        self.assertEqual(oct((Path(self.tmp.name) / "datenputz.db").stat().st_mode & 0o777), "0o600")

    def test_consent_required(self):
        with mock.patch("builtins.input", return_value="n"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main(["breach", "email", "--sources", "hudsonrock", "--email", EMAIL])


if __name__ == "__main__":
    unittest.main()
