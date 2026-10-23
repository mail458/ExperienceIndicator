import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from datenputz import brokers as B
from datenputz import cli
from datenputz import engine as E
from datenputz import inbox as I
from datenputz import letters as L
from datenputz import mailer as M
from datenputz import report as R
from datenputz import store as S

PROFILE = {
    "name": "Erika Mustermann", "aliases": ["Erika Gabler"], "emails": ["erika@example.org"],
    "addresses": ["Heidestraße 17\n51147 Köln", "Altweg 3\n10115 Berlin"], "phones": ["+49 170 1234567"],
    "country": "de", "language": "de",
}


class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def advance(self, days):
        self.t += timedelta(days=days)


class FakeSMTP:
    dry_run = False

    def __init__(self):
        self.sent = []

    def send(self, msg, name):
        self.sent.append(msg)
        return msg["Message-ID"]

    def close(self):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DATENPUTZ_HOME"] = self.tmp.name
        self.st = S.Store()
        self.p = self.st.add_profile("erika", PROFILE)
        self.clock = Clock()
        self.mail = FakeSMTP()

    def tearDown(self):
        self.tmp.cleanup()

    def engine(self):
        return E.Engine(self.st, self.mail, clock=self.clock)


class BrokerTests(unittest.TestCase):
    def test_directory_size_and_filters(self):
        de = {b["id"] for b in B.select("de")}
        self.assertGreater(len(de), 300)
        self.assertIn("schufa", de)
        self.assertIn("acxiom", de)
        self.assertNotIn("spokeo", de)  # US-Personensuche nur auf Wunsch
        self.assertIn("spokeo", {b["id"] for b in B.select("de", include_public=True)})
        self.assertIn("spokeo", {b["id"] for b in B.select("us")})

    def test_domains(self):
        self.assertIn("acxiom.com", B.domains(B.by_id()["acxiom"]))


class LetterTests(unittest.TestCase):
    def setUp(self):
        self.idx = B.by_id()
        self.t = datetime(2026, 1, 5, tzinfo=timezone.utc)

    def test_erasure_minimises_data(self):
        subject, body = L.render("erasure", PROFILE, self.idx["acxiom"], self.t)
        self.assertIn("Art. 17", subject)
        self.assertIn("Art. 21 Abs. 2", body)
        self.assertIn("Erika Gabler", body)
        self.assertIn("Altweg 3, 10115 Berlin", body)
        self.assertNotIn("+49 170", body)  # Telefon nicht verlangt → nicht senden
        self.assertIn("04.02.2026", body)  # Frist 30 Tage

    def test_phone_only_when_required(self):
        b = dict(self.idx["acxiom"], required=["phone"])
        self.assertIn("+49 170", L.render("erasure", PROFILE, b, self.t)[1])

    def test_credit_agency_gets_access_request(self):
        self.assertEqual(self.idx["schufa"]["default_request"], "access")
        subject, body = L.render("access", PROFILE, self.idx["schufa"], self.t)
        self.assertIn("Art. 15", subject)
        self.assertIn("Score", body)

    def test_ccpa_letter(self):
        subject, body = L.render("ccpa_delete", PROFILE, self.idx["spokeo"], self.t)
        self.assertIn("opt out", subject)
        self.assertIn("2026-02-19", body)  # 45 Tage

    def test_on_behalf(self):
        p = dict(PROFILE, on_behalf_of_by="Max Mustermann")
        body = L.render("erasure", p, self.idx["acxiom"], self.t)[1]
        self.assertIn("Vollmacht", body)
        self.assertTrue(body.rstrip().endswith("Max Mustermann"))


class LifecycleTests(Base):
    def test_full_cycle_reminder_and_complaint(self):
        eng = self.engine()
        self.assertEqual(eng.plan(self.p, only=["acxiom", "adform"]), 2)
        stats = eng.run()
        self.assertEqual((stats["sent"], stats["manual"]), (1, 1))
        email_req = self.st.latest(self.p["_id"], "acxiom")
        form_req = self.st.latest(self.p["_id"], "adform")
        self.assertEqual(email_req["status"], S.SENT)
        self.assertEqual(form_req["status"], S.AWAITING_USER)
        self.assertTrue(Path(form_req["note"]).exists())
        self.assertEqual(self.mail.sent[0]["To"], "datenschutz@acxiom.com")

        self.clock.advance(31)
        self.assertEqual(self.engine().run()["reminded"], 1)
        reminder = self.mail.sent[-1]
        self.assertEqual(reminder["In-Reply-To"], email_req["message_id"])
        self.assertIn("Erinnerung", reminder["Subject"])
        self.assertEqual(self.st.request(email_req["id"])["status"], S.REMINDED)

        self.clock.advance(15)
        self.assertEqual(self.engine().run()["escalated"], 1)
        r = self.st.request(email_req["id"])
        self.assertEqual(r["status"], S.ESCALATED)
        self.assertIn("Art. 77", Path(r["note"]).read_text(encoding="utf-8"))

    def test_recurring_rounds(self):
        eng = self.engine()
        eng.plan(self.p, only=["acxiom"])
        eng.run()
        rid = self.st.latest(self.p["_id"], "acxiom")["id"]
        eng.mark(rid, S.CONFIRMED)
        self.clock.advance(89)
        self.assertEqual(self.engine().run()["recurring"], 0)
        self.clock.advance(2)
        self.assertEqual(self.engine().run()["recurring"], 1)
        latest = self.st.latest(self.p["_id"], "acxiom")
        self.assertEqual((latest["round"], latest["status"]), (2, S.SENT))
        self.assertIn("bereits früher", self.mail.sent[-1].get_content())

    def test_suppressed_is_not_repeated(self):
        eng = self.engine()
        eng.plan(self.p, only=["acxiom"])
        eng.run()
        eng.mark(self.st.latest(self.p["_id"], "acxiom")["id"], S.SUPPRESSED)
        self.clock.advance(400)
        self.assertEqual(self.engine().run()["recurring"], 0)

    def test_daily_limit(self):
        self.st.save_config({"daily_limit": 2})
        eng = self.engine()
        eng.plan(self.p, only=["acxiom", "schufa", "az-direct"])
        stats = eng.run()
        self.assertEqual((stats["sent"], stats["deferred"]), (2, 1))
        self.assertEqual(self.engine().run()["sent"], 0)  # Tageslimit schon erreicht

    def test_custom_removal(self):
        eng = self.engine()
        b = B.make_custom("https://www.example-people.com/erika", email="privacy@example-people.com")
        eng.add_custom(self.p, b, ["https://www.example-people.com/erika"])
        eng.run()
        self.assertIn("https://www.example-people.com/erika", self.mail.sent[0].get_content())


class InboxTests(Base):
    def test_classify(self):
        self.assertEqual(I.classify("Ihre Daten wurden gelöscht."), S.CONFIRMED)
        self.assertEqual(I.classify("We do not hold any personal data about you."), S.NO_DATA)
        self.assertEqual(I.classify("Bitte senden Sie uns eine Kopie Ihres Ausweises."), S.AWAITING_USER)
        self.assertEqual(I.classify("Wir haben Sie in unsere Werbesperrdatei aufgenommen."), S.SUPPRESSED)
        self.assertEqual(I.classify("Mail delivery failed: returning message"), S.BOUNCED)
        self.assertEqual(I.classify("Automatische Antwort: Wir haben Ihre Anfrage erhalten"), "acknowledged")
        self.assertIsNone(I.classify("Hallo"))

    def test_reply_matched_and_applied(self):
        eng = self.engine()
        eng.plan(self.p, only=["acxiom", "az-direct"])
        eng.run()
        acx = self.st.latest(self.p["_id"], "acxiom")
        reply = EmailMessage()
        reply["From"] = "Datenschutz <noreply@acxiom.com>"
        reply["Subject"] = "Re: Antrag auf Löschung"
        reply["Message-ID"] = "<abc@acxiom.com>"
        reply.set_content("Sehr geehrte Frau Mustermann, Ihre Daten wurden gelöscht.")
        found = I.process(self.st, eng, [reply], apply=True)
        self.assertEqual(found[0]["verdict"], S.CONFIRMED)
        r = self.st.request(acx["id"])
        self.assertEqual(r["status"], S.CONFIRMED)
        self.assertIsNotNone(r["next_round_at"])
        self.assertEqual(I.process(self.st, eng, [reply], apply=True), [])  # nicht doppelt


class CliTests(Base):
    def test_preview_keeps_state_and_report(self):
        cli.main(["plan", "--only", "acxiom"])
        cli.main(["run"])
        self.assertEqual(self.st.latest(self.p["_id"], "acxiom")["status"], S.PENDING)
        self.assertTrue(any((Path(self.tmp.name) / "preview" / "outbox").glob("*.eml")))
        cli.main(["run", "--outbox"])
        self.assertEqual(self.st.latest(self.p["_id"], "acxiom")["status"], S.SENT)
        out = Path(self.tmp.name) / "r.html"
        cli.main(["report", "-o", str(out)])
        self.assertIn("Acxiom", out.read_text(encoding="utf-8"))

    def test_mark_alias(self):
        cli.main(["plan", "--only", "acxiom"])
        rid = self.st.latest(self.p["_id"], "acxiom")["id"]
        cli.main(["mark", "keine-daten", str(rid)])
        self.assertEqual(self.st.request(rid)["status"], S.NO_DATA)


class MailerTests(unittest.TestCase):
    def test_reply_threading(self):
        m = M.build("a@x.de", "b@y.de", "Betreff", "Text", reply_to="c@x.de", in_reply_to="<1@x>", quote="alt")
        self.assertEqual(m["References"], "<1@x>")
        self.assertIn("> alt", m.get_content())


class ReportTests(Base):
    def test_render_empty(self):
        self.assertIn("<!doctype html>", R.render(self.st, B.by_id()))


if __name__ == "__main__":
    unittest.main()
