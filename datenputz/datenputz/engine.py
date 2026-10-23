"""Ablaufsteuerung: planen, versenden, erinnern, eskalieren, wiederholen.

Entspricht dem Incogni-Zyklus: Anfrage → Frist (30 Tage DSGVO / 45 Tage
CCPA) → Erinnerung → Beschwerde; nach Erledigung erneute Anfrage alle 60
(Personensuche) bzw. 90 Tage (übrige Händler), außer der Händler hat die
Person dauerhaft gesperrt.
"""
import json
import re
from datetime import timedelta

from . import brokers as B
from . import letters as L
from . import mailer as M
from . import store as S

RECUR_DAYS = {"public": 60, "private": 90}
DEFAULT_DAILY_LIMIT = 40


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:60]


class Engine:
    def __init__(self, store, mailer=None, clock=S.now, broker_index=None):
        self.s = store
        self.cfg = store.config()
        self.mailer = mailer or M.Outbox(store.dir / "outbox")
        self.clock = clock
        self.brokers = broker_index or B.by_id()
        self.log = []

    # ------------------------------------------------------------------
    def say(self, text):
        self.log.append(text)

    def law(self, broker):
        return "ccpa" if broker.get("default_request") == "ccpa_delete" else "gdpr"

    def sender(self, profile):
        smtp = self.cfg.get("smtp", {})
        return smtp.get("from") or (profile.get("emails") or ["datenputz@localhost"])[0]

    # ------------------------------------------------------------------
    def plan(self, profile, categories=None, search=None, include_public=None, only=None):
        """Legt für jeden passenden Händler ohne bisherige Anfrage eine an."""
        country = profile.get("country", "de")
        include_public = include_public if include_public is not None else profile.get("include_public")
        if only:
            chosen = [self.brokers[b] for b in only if b in self.brokers]
        else:
            chosen = B.select(country, categories=categories, search=search, include_public=include_public)
        skip = set(profile.get("exclude", []))
        n = 0
        for b in chosen:
            if b["id"] in skip or self.s.latest(profile["_id"], b["id"]):
                continue
            self.s.create_request(profile["_id"], b["id"], b["default_request"], self._channel(b))
            n += 1
        return n

    def add_custom(self, profile, broker, urls, identity=None):
        """Eigene Löschanfrage (wie Incognis „Custom Removals“) für beliebige Seiten."""
        self.brokers[broker["id"]] = broker
        return self.s.create_request(profile["_id"], broker["id"], "erasure", self._channel(broker), urls=urls,
                                     identity=identity)

    def _profile(self, r):
        p = self.s.profile_by_id(r["profile_id"])
        if r["identity"]:
            p = {**p, **json.loads(r["identity"])}
        return p

    @staticmethod
    def _channel(b):
        if b.get("channel") == "email" and b.get("email"):
            return "email"
        if b.get("webform"):
            return "webform"
        if b.get("email"):
            return "email"
        return "letter"

    # ------------------------------------------------------------------
    def run(self):
        now = self.clock()
        stats = {"recurring": 0, "sent": 0, "manual": 0, "reminded": 0, "escalated": 0, "deferred": 0}
        limit = self.cfg.get("daily_limit", DEFAULT_DAILY_LIMIT)
        budget = max(0, limit - (0 if self.mailer.dry_run else self.s.sent_today()))

        # 1. Wiederholungen fällig?
        for r in self.s.requests(statuses=(S.CONFIRMED, S.NO_DATA)):
            due = S.parse(r["next_round_at"])
            if due and due <= now and self.s.latest(r["profile_id"], r["broker_id"])["id"] == r["id"]:
                self.s.create_request(r["profile_id"], r["broker_id"], r["kind"], r["channel"],
                                      round_=r["round"] + 1, urls=_urls(r),
                                      identity=json.loads(r["identity"]) if r["identity"] else None)
                stats["recurring"] += 1

        # 2. Geplante Anfragen versenden bzw. an den Nutzer übergeben – wichtigste Händler zuerst
        pending = sorted(self.s.requests(statuses=(S.PENDING,)),
                         key=lambda r: (priority(self.brokers.get(r["broker_id"], {})), r["id"]))
        for r in pending:
            b = self.brokers.get(r["broker_id"])
            if not b:
                continue
            p = self._profile(r)
            if r["channel"] == "email":
                if budget <= 0:
                    stats["deferred"] += 1
                    continue
                self._send_initial(r, p, b, now)
                budget -= 1
                stats["sent"] += 1
            else:
                self._handover(r, p, b, now)
                stats["manual"] += 1

        # 3. Frist abgelaufen → Erinnerung
        for r in self.s.requests(statuses=(S.SENT,)):
            if S.parse(r["due_at"]) and S.parse(r["due_at"]) <= now:
                b, p = self.brokers.get(r["broker_id"]), self._profile(r)
                if not b:
                    continue
                if b.get("email"):
                    if budget <= 0:
                        stats["deferred"] += 1
                        continue
                    self._send_reminder(r, p, b, now)
                    budget -= 1
                else:
                    # Kein Mailkontakt: Nachfrist trotzdem setzen, Nutzer erinnert selbst
                    self.s.update(r["id"], status=S.REMINDED, reminded_at=now,
                                  due_at=now + timedelta(days=L.GRACE_DAYS))
                    self.s.log(r["id"], "reminder_manual", "Bitte beim Händler per Formular nachhaken.")
                stats["reminded"] += 1

        # 4. Nachfrist abgelaufen → Beschwerdeentwurf
        for r in self.s.requests(statuses=(S.REMINDED,)):
            if S.parse(r["due_at"]) and S.parse(r["due_at"]) <= now:
                b, p = self.brokers.get(r["broker_id"]), self._profile(r)
                if b:
                    self._escalate(r, p, b, now)
                    stats["escalated"] += 1
        self.mailer.close()
        return stats

    # ------------------------------------------------------------------
    def _send_initial(self, r, p, b, now):
        subject, body = L.render(r["kind"], p, b, now, urls=_urls(r), round_=r["round"])
        msg = M.build(self.sender(p), b["email"], subject, body, reply_to=_reply_to(p, self.sender(p)))
        where = self.mailer.send(msg, f"{r['id']:05d}-{b['id']}-r{r['round']}")
        self._archive(msg, r, "initial")
        self.s.update(r["id"], status=S.SENT, sent_at=now, due_at=L.due_date(now, self.law(b)),
                      message_id=msg["Message-ID"])
        self.s.log(r["id"], "sent", f"an {b['email']} ({where})")

    def _send_reminder(self, r, p, b, now):
        first = S.parse(r["sent_at"])
        _, original = L.render(r["kind"], p, b, first, urls=_urls(r), round_=r["round"])
        subject, body = L.reminder(p, b, r["kind"], first, now)
        msg = M.build(self.sender(p), b["email"], subject, body, reply_to=_reply_to(p, self.sender(p)),
                      in_reply_to=r["message_id"], quote=original)
        where = self.mailer.send(msg, f"{r['id']:05d}-{b['id']}-r{r['round']}-erinnerung")
        self._archive(msg, r, "reminder")
        self.s.update(r["id"], status=S.REMINDED, reminded_at=now, due_at=now + timedelta(days=L.GRACE_DAYS))
        self.s.log(r["id"], "reminder_sent", f"an {b['email']} ({where})")

    def _handover(self, r, p, b, now):
        """Webformular oder Brief: Text vorbereiten, Nutzer schickt ab und meldet `mark … sent`."""
        subject, body = L.render(r["kind"], p, b, now, urls=_urls(r), round_=r["round"])
        folder = self.s.dir / ("letters" if r["channel"] == "letter" else "forms")
        folder.mkdir(exist_ok=True)
        path = folder / f"{r['id']:05d}-{b['id']}.txt"
        head = []
        if r["channel"] == "letter":
            head = [p["name"], *(p.get("addresses") or [""])[:1], "", b["name"], b.get("address") or "", "", ""]
        else:
            head = [f"Formular: {b.get('webform')}", f"Betreff: {subject}", "", "Text zum Einfügen:", ""]
        path.write_text("\n".join(head) + body, encoding="utf-8")
        self.s.update(r["id"], status=S.AWAITING_USER, note=str(path))
        self.s.log(r["id"], "handover", f"{r['channel']}: {path}")

    def _escalate(self, r, p, b, now):
        auth = self.authority(p)
        lang = (auth or {}).get("complaint-language") or ("de" if p.get("language", "de") == "de" else "en")
        text = L.complaint(p, b, r["kind"], S.parse(r["sent_at"]) or now, S.parse(r["reminded_at"]), auth, lang)
        folder = self.s.dir / "complaints"
        folder.mkdir(exist_ok=True)
        path = folder / f"{r['id']:05d}-{b['id']}-beschwerde.txt"
        path.write_text(text, encoding="utf-8")
        self.s.update(r["id"], status=S.ESCALATED, escalated_at=now, note=str(path))
        self.s.log(r["id"], "escalated", str(path))

    def authority(self, p):
        auths = B.authorities()
        if p.get("authority"):
            return next((a for a in auths if a["slug"] == p["authority"]), None)
        cands = [a for a in auths if p.get("country", "de") in (a.get("relevant-countries") or [])]
        return cands[0] if len(cands) == 1 else None

    def _archive(self, msg, r, label):
        folder = self.s.dir / "sent"
        folder.mkdir(exist_ok=True)
        (folder / f"{r['id']:05d}-{r['broker_id']}-r{r['round']}-{label}.eml").write_bytes(bytes(msg))

    # ------------------------------------------------------------------
    def mark(self, request_id, status, note=None):
        r = self.s.request(request_id)
        if not r:
            raise KeyError(request_id)
        now = self.clock()
        b = self.brokers.get(r["broker_id"], {})
        fields = {"status": status}
        if status == S.SENT:  # z. B. Webformular abgeschickt
            fields.update(sent_at=now, due_at=L.due_date(now, self.law(b)) if b else None)
        if status in S.DONE:
            fields["closed_at"] = now
            if status in (S.CONFIRMED, S.NO_DATA):
                fields["next_round_at"] = now + timedelta(days=RECUR_DAYS.get(b.get("type", "private"), 90))
        if note:
            fields["note"] = note
        self.s.update(request_id, **fields)
        self.s.log(request_id, "status", f"{status}" + (f": {note}" if note else ""))


def priority(b):
    """Adresshändler und eigene Einträge zuerst, dann Auskunfteien, dann Werbenetzwerke."""
    cats = set(b.get("categories", []))
    if b.get("custom"):
        return 0
    if cats & {"addresses", "people search"}:
        return 1
    if cats & {"credit agency", "collection agency"}:
        return 2
    return 3 if "all" not in (b.get("countries") or []) else 4


def _urls(r):
    return json.loads(r["urls"]) if r["urls"] else None


def _reply_to(profile, sender):
    own = (profile.get("emails") or [None])[0]
    return own if own and own != sender else None
