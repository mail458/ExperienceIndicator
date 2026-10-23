import contextlib
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from datenputz import cli
from datenputz import daily as D
from datenputz import doctor
from datenputz import keystore as K
from datenputz import net
from datenputz import notify as N
from datenputz import report as R
from datenputz import brokers as B
from datenputz import schedule as SC
from datenputz import store as S
from datenputz import web

EMAIL = "erika@example.org"


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DATENPUTZ_HOME"] = self.tmp.name
        self.st = S.Store()

    def tearDown(self):
        self.st.close()
        self.tmp.cleanup()


class Capture:
    def __init__(self, status=200, body=b"ok"):
        self.calls, self.status, self.body = [], status, body

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        return self.status, self.body


class NotifyTests(Home):
    def test_ntfy_request(self):
        N.add_channel(self.st, {"type": "ntfy", "server": "https://ntfy.example", "topic": "datenputz-geheim"})
        cap = Capture()
        with mock.patch.object(net, "fetch", cap), mock.patch.object(K, "get", return_value="tok"):
            res = N.send(self.st, "Datenputz: kritischer Fund", "2 neue Funde", "kritisch")
        self.assertEqual(res, [("ntfy", None)])
        url, kw = cap.calls[0]
        u = urlsplit(url)
        self.assertEqual(u.path, "/datenputz-geheim")
        self.assertEqual(parse_qs(u.query)["title"], ["Datenputz: kritischer Fund"])  # Umlaute sicher als Parameter
        self.assertEqual(parse_qs(u.query)["priority"], ["5"])
        self.assertEqual(kw["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(kw["data"], "2 neue Funde".encode())

    def test_gotify_telegram_and_failures_are_isolated(self):
        N.add_channel(self.st, {"type": "gotify", "server": "https://g.example"})
        N.add_channel(self.st, {"type": "telegram", "chat_id": "42"})
        cap = Capture()
        with mock.patch.object(net, "fetch", cap), mock.patch.object(K, "get", side_effect=lambda n, s=None: {
                "gotify": "G", "telegram": None}.get(n)):
            res = dict(N.send(self.st, "T", "B", "hoch"))
        self.assertIsNone(res["gotify"])
        self.assertIn("Telegram-Bot-Token fehlt", res["telegram"])
        url, kw = cap.calls[0]
        self.assertEqual(url, "https://g.example/message")
        self.assertEqual(kw["headers"]["X-Gotify-Key"], "G")
        self.assertEqual(json.loads(kw["data"])["priority"], 8)

    def test_random_topic(self):
        a, b = N.new_ntfy_topic(), N.new_ntfy_topic()
        self.assertNotEqual(a, b)
        self.assertGreater(len(a), 30)


class DailyTests(Home):
    def test_nothing_configured_is_quiet(self):
        steps, notable = D.run(self.st)
        levels = {n: lv for n, lv, _ in steps}
        self.assertEqual(levels["Antworten"], D.SKIP)
        self.assertEqual(levels["Dashboard"], D.OK)
        self.assertIsNone(D.summarize(self.st, steps, notable))
        self.assertTrue((Path(self.tmp.name) / "report.html").exists())
        self.assertIsNotNone(self.st.get_kv("daily_last"))

    def test_missing_smtp_password_reported_and_notified(self):
        self.st.add_profile("erika", {"name": "Erika", "emails": [EMAIL], "country": "de"})
        self.st.save_config({"smtp": {"host": "smtp.example", "user": "u", "from": EMAIL}})
        cli_out = io.StringIO()
        with contextlib.redirect_stdout(cli_out):
            cli.main(["plan", "--only", "acxiom"])
        sent = []
        with mock.patch.object(K, "get", return_value=None), \
                mock.patch.object(N, "send", lambda st, t, b, lv: sent.append((t, b, lv)) or []):
            steps, _ = D.run(self.st)
        req = next(s for s in steps if s[0] == "Löschanträge")
        self.assertEqual(req[1], D.BAD)
        self.assertIn("secret set smtp", req[2])
        self.assertEqual(len(sent), 1)
        self.assertIn("Fehler bei Löschanträge", sent[0][1])
        self.assertNotIn(EMAIL, sent[0][1])  # knappe Meldung ohne persönliche Daten

    def test_summary_minimal_vs_full(self):
        f = {"severity": "kritisch", "subject": EMAIL, "title": "Stealer", "key": "x", "classes": []}
        notable = {"findings": [f], "replies": {S.CONFIRMED: 2}, "tasks": 1, "escalated": 0}
        title, body, level = D.summarize(self.st, [], notable)
        self.assertEqual(level, "kritisch")
        self.assertIn("kritischer Fund", title)
        self.assertIn("2 Händler", body)
        self.assertNotIn(EMAIL, body)
        cfg = self.st.config()
        cfg["notify"] = {"detail": "full", "channels": []}
        self.st.save_config(cfg)
        self.assertIn(EMAIL, D.summarize(self.st, [], notable)[1])

    def test_only_subset_does_not_count_as_daily(self):
        D.run(self.st, only={"Dashboard"})
        self.assertIsNone(self.st.get_kv("daily_last"))

    def test_require_never_prompts_without_tty(self):
        with mock.patch.object(K, "get", return_value=None), mock.patch("sys.stdin", io.StringIO()):
            with self.assertRaises(RuntimeError):
                K.require("smtp", "Passwort: ")


class ScheduleTests(Home):
    def test_units_and_install(self):
        with mock.patch("os.geteuid", return_value=1000), mock.patch.object(Path, "home", return_value=Path(self.tmp.name)):
            kind, files, cmds = SC.plan("06:05", "systemd", self.st.dir)
            self.assertIn("OnCalendar=*-*-* 06:05:00", files[1][1])
            self.assertIn("Persistent=true", files[1][1])
            self.assertIn(f'Environment="DATENPUTZ_HOME={self.st.dir}"', files[0][1])
            self.assertIn("--user", cmds[0])
            ran = []
            with mock.patch("subprocess.run", lambda c, **kw: ran.append(c) or mock.Mock(returncode=0)):
                kind, text = SC.install(self.st, "06:05", "systemd")
            self.assertTrue(files[0][0].exists())
            self.assertEqual(ran[-1][-2:], ["--now", "datenputz.timer"])
            self.assertEqual(self.st.get_kv("schedule")["time"], "06:05")
            with mock.patch("subprocess.run", lambda c, **kw: mock.Mock(returncode=0)):
                SC.remove(self.st)
            self.assertFalse(files[0][0].exists())
            self.assertIsNone(self.st.get_kv("schedule"))

    def test_failed_command_raises(self):
        with mock.patch("os.geteuid", return_value=1000), mock.patch.object(Path, "home", return_value=Path(self.tmp.name)), \
                mock.patch("subprocess.run", return_value=mock.Mock(returncode=1, stderr="Failed to connect to bus", stdout="")):
            with self.assertRaises(RuntimeError):
                SC.install(self.st, "06:05", "systemd")

    def test_other_platforms(self):
        self.assertIn("<integer>6</integer>", SC.launchd_plist("06:05", "/x"))
        self.assertIn("/ST", SC.schtasks_cmd("06:05", "C:/x"))
        self.assertTrue(SC.cron_line("06:05", "/h").startswith("5 6 * * *"))

    def test_cli_validates_time(self):
        with self.assertRaises(SystemExit):
            cli.main(["schedule", "install", "--time", "25:99", "--dry-run"])


class DoctorTests(Home):
    def test_detects_open_permissions(self):
        self.st.save_config({})
        os.chmod(self.st.config_path, 0o644)
        res = {n: lv for lv, n, _ in doctor.local_checks(self.st)}
        self.assertEqual(res["Konfiguration"], doctor.BAD)
        self.assertEqual(res["Datenbank"], doctor.OK)
        self.assertEqual(res["Profile"], doctor.WARN)

    def test_online_checks_with_failures(self):
        def fake(url, **kw):
            if "pwnedpasswords" in url:
                return 200, b"0018A45C4D1DEF81644B54AB7F969B88D65:1\r\n"
            raise OSError("offline")
        with mock.patch.object(net, "fetch", fake), mock.patch.object(K, "get", return_value=None):
            res = {n: (lv, t) for lv, n, t in doctor.online_checks(self.st)}
        self.assertEqual(res["Pwned Passwords"][0], doctor.OK)
        self.assertEqual(res["Verschlüsseltes DNS (DoH)"][0], doctor.BAD)
        self.assertEqual(res["Have I Been Pwned"][0], doctor.WARN)
        self.assertEqual(res["SMTP (Versand)"][0], doctor.INFO)

    def test_cli_exit_code(self):
        with mock.patch.object(doctor, "online_checks", return_value=[(doctor.BAD, "X", "kaputt")]), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main(["doctor"])


class WebTests(Home):
    def setUp(self):
        super().setUp()
        self.st.add_profile("erika", {"name": "Erika", "emails": [EMAIL], "country": "de"})
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["plan", "--only", "acxiom,adform"])
            cli.main(["run", "--outbox"])
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
        return r.status, dict(r.getheaders()), data.decode("utf-8", "replace")

    def login(self):
        s, h, _ = self.req("GET", "/login?t=" + self.app.token)
        self.assertEqual(s, 303)
        self.assertIn("HttpOnly", h["Set-Cookie"])
        self.assertIn("SameSite=Strict", h["Set-Cookie"])
        return {"Cookie": h["Set-Cookie"].split(";")[0]}

    def post(self, ck, path, data, extra=None):
        body = "&".join(f"{k}={v}" for k, v in data.items())
        return self.req("POST", path, {**ck, "Content-Type": "application/x-www-form-urlencoded", **(extra or {})}, body)

    def test_access_control(self):
        self.assertEqual(self.req("GET", "/")[0], 401)
        self.assertEqual(self.req("GET", "/", {"Host": "evil.example"})[0], 421)
        self.assertEqual(self.req("GET", "/login?t=falsch")[0], 403)
        for _ in range(10):
            self.req("GET", "/login?t=falsch")
        self.assertEqual(self.req("GET", "/login?t=" + self.app.token)[0], 429)  # Bremse greift

    def test_pages_and_headers(self):
        ck = self.login()
        for path in ("/", "/aufgaben", "/anfragen", "/leaks", "/pruefen", "/system"):
            s, h, body = self.req("GET", path, ck)
            self.assertEqual(s, 200, path)
            self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])
            self.assertEqual(h["X-Frame-Options"], "DENY")
            self.assertNotIn('style="', body)  # CSP verbietet Inline-Styles
            self.assertNotIn("<script>", body)
        self.assertIn("Privatsphäre-Wert", self.req("GET", "/", ck)[2])
        self.assertIn("Adform", self.req("GET", "/aufgaben", ck)[2])
        self.assertEqual(self.req("GET", "/favicon.ico")[0], 204)

    def test_csrf_origin_and_mark(self):
        ck = self.login()
        rid = self.st.latest(self.st.profile("erika")["_id"], "adform")["id"]
        data = {"id": rid, "status": S.SENT, "back": "/aufgaben"}
        self.assertEqual(self.post(ck, "/mark", data)[0], 403)  # ohne CSRF-Token
        self.assertEqual(self.post(ck, "/mark", {**data, "csrf": self.app.csrf}, {"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.post(ck, "/mark", {**data, "csrf": self.app.csrf}, {"Origin": "null"})[0], 403)
        s, h, _ = self.post(ck, "/mark", {**data, "csrf": self.app.csrf},
                            {"Origin": f"http://127.0.0.1:{self.app.port}"})
        self.assertEqual((s, h["Location"]), (303, "/aufgaben"))
        self.assertEqual(S.Store().request(rid)["status"], S.SENT)
        s, h, _ = self.post(ck, "/mark", {**data, "csrf": self.app.csrf, "back": "//evil.example"})
        self.assertEqual(h["Location"], "/anfragen")  # keine Weiterleitung nach außen
        self.assertEqual(self.post(ck, "/mark", {**data, "csrf": self.app.csrf, "status": "x"})[0], 400)

    def test_checker_and_plan_toggle(self):
        ck = self.login()
        s, _, body = self.post(ck, "/pruefen", {"csrf": self.app.csrf, "text": "http%3A%2F%2Fpaypa1.com%2Flogin"})
        self.assertIn("gefährlich", body)
        self.post(ck, "/plan", {"csrf": self.app.csrf, "h": "abc"})
        self.assertEqual(S.Store().get_kv("plan_done"), ["abc"])
        self.post(ck, "/plan", {"csrf": self.app.csrf, "h": "abc"})
        self.assertEqual(S.Store().get_kv("plan_done"), [])

    def test_job_runs_in_background(self):
        ck = self.login()
        done = threading.Event()
        with mock.patch.dict(web.JOBS, {"daily": ("Test", lambda st, log: (log("hallo"), done.set()))}):
            self.post(ck, "/job", {"csrf": self.app.csrf, "name": "daily"})
            self.assertTrue(done.wait(5))
        for _ in range(50):
            if not self.app.job["running"]:
                break
            threading.Event().wait(0.05)
        self.assertIn("hallo", self.req("GET", "/", ck)[2])

    def test_safe_read_stays_in_data_dir(self):
        self.assertEqual(web._safe_read(self.st, "/etc/passwd"), "")

    def test_score(self):
        score, parts, tips = web.privacy_score(self.st, R.rows(self.st, B.by_id()), [])
        self.assertTrue(0 <= score <= 100)
        self.assertEqual(sum(w for _, w, _ in parts), 100)
        self.assertTrue(tips)


if __name__ == "__main__":
    unittest.main()
