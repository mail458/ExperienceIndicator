"""Antworten der Händler im Postfach (IMAP) finden und automatisch einordnen."""
import email
import imaplib
import json
import re
from datetime import timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr

from . import brokers as B
from . import store as S

# Reihenfolge ist wichtig: die erste passende Regel gewinnt.
RULES = [
    (S.BOUNCED, r"undeliverable|delivery status notification|mail delivery (failed|subsystem)|"
                r"unzustellbar|returned mail|nicht zugestellt|address not found"),
    (S.AWAITING_USER, r"ausweis|identit(ä|ae)t\w* (zu )?(nachweis|bestätig|prüf)|verify your identity|"
                      r"identity verification|proof of identity|bestätigungslink|verification link|"
                      r"confirm your (email|request)|klicken sie auf den link|click (on )?the link"),
    (S.NO_DATA, r"keine (personenbezogenen )?daten|keine daten (zu|über) ihre(r)? person|"
                r"nicht in unserer datenbank|no (personal )?(data|information|records?) (about|on|relating to|for) you|"
                r"we (do not|don't) hold any|could not (find|locate) any|not in our database"),
    (S.SUPPRESSED, r"sperrliste|werbesperr|robinson|suppression (list|file)|do[- ]not[- ](mail|contact) list|"
                   r"permanently suppressed"),
    (S.CONFIRMED, r"gelöscht|wurden entfernt|löschung (wurde )?(durchgeführt|vorgenommen|bestätigt|veranlasst)|"
                  r"(have|has) been (deleted|removed|erased)|successfully (deleted|removed)|"
                  r"request has been (completed|processed)|opt-?out (request )?(is|has been) (complete|processed)"),
    (S.REJECTED, r"können (ihrem antrag|wir ihrem) .{0,40}nicht|lehnen .{0,60}ab|cannot comply|"
                 r"unable to (delete|comply|process)|we decline"),
]
ACK = r"eingangsbestätigung|automatische antwort|auto-?reply|out of office|we have received your|" \
      r"wir haben ihre (anfrage|nachricht) erhalten|ticket"


def classify(text):
    t = text.lower()
    for status, pattern in RULES:
        if re.search(pattern, t):
            return status
    if re.search(ACK, t):
        return "acknowledged"
    return None


def _text(msg):
    parts = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_type() in ("text/plain", "text/html") and not part.get_filename():
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            t = payload.decode(charset, errors="replace")
            if part.get_content_type() == "text/html":
                t = re.sub(r"<[^>]+>", " ", t)
            parts.append(t)
    return "\n".join(parts)


def _header(msg, name):
    v = msg.get(name)
    return str(make_header(decode_header(v))) if v else ""


def match(store, msg, domain_index):
    """Zugehörige offene Anfrage finden: zuerst über Message-IDs, dann über die Absenderdomain."""
    refs = " ".join(filter(None, [msg.get("In-Reply-To"), msg.get("References")]))
    for mid in re.findall(r"<[^>]+>", refs):
        r = store.find_by_message_id(mid)
        if r:
            return r
    domain = parseaddr(msg.get("From", ""))[1].rsplit("@", 1)[-1].lower()
    candidates = domain_index.get(domain) or domain_index.get(".".join(domain.split(".")[-2:])) or []
    open_reqs = [r for bid in candidates for r in store.requests(broker_id=bid, statuses=S.OPEN)]
    if len(open_reqs) > 1:  # mehrere Profile → anhand des Namens im Text unterscheiden
        body = _text(msg).lower()
        named = [r for r in open_reqs if store.profile_by_id(r["profile_id"])["name"].lower() in body]
        open_reqs = named or open_reqs
    return open_reqs[0] if open_reqs else None


def domain_index(broker_index):
    idx = {}
    for b in broker_index.values():
        for d in B.domains(b):
            idx.setdefault(d, []).append(b["id"])
    return idx


def process(store, engine, messages, apply=False):
    """messages: Iterable aus email.message.Message. Gibt Liste von Funden zurück."""
    seen_path = store.dir / "inbox_seen.json"
    seen = set(json.loads(seen_path.read_text())) if seen_path.exists() else set()
    idx = domain_index(engine.brokers)
    found = []
    for msg in messages:
        mid = msg.get("Message-ID") or ""
        if mid in seen:
            continue
        r = match(store, msg, idx)
        if not r:
            continue
        verdict = classify(_header(msg, "Subject") + "\n" + _text(msg))
        found.append({"request": r["id"], "broker": r["broker_id"], "subject": _header(msg, "Subject"),
                      "verdict": verdict})
        if apply:
            store.log(r["id"], "reply", f"{_header(msg, 'Subject')} → {verdict or 'unklar'}")
            if verdict and verdict != "acknowledged":
                engine.mark(r["id"], verdict, note=f"automatisch erkannt: {_header(msg, 'Subject')}")
            seen.add(mid)
    if apply:
        seen_path.write_text(json.dumps(sorted(seen)))
    return found


def fetch(cfg, days=60):
    """Mails der letzten `days` Tage per IMAP holen (nur lesend)."""
    from . import keystore
    password = keystore.get("imap") or keystore.require("smtp", f"IMAP-Passwort für {cfg['user']}: ")
    conn = imaplib.IMAP4_SSL(cfg["host"], cfg.get("port", 993))
    conn.login(cfg["user"], password)
    try:
        conn.select(cfg.get("folder", "INBOX"), readonly=True)
        since = (S.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        _, data = conn.search(None, "SINCE", since)
        for num in data[0].split():
            _, parts = conn.fetch(num, "(BODY.PEEK[])")
            yield email.message_from_bytes(parts[0][1])
    finally:
        conn.logout()
