"""Alias-Verzeichnis: eine eigene E-Mail-Adresse pro Dienst, damit Leaks und Weitergaben auffallen.

Erhält ein Alias, den nur Dienst A kennt, Post von Firma B – oder taucht er im
Leak von B auf –, hat A die Adresse weitergegeben oder verloren.
"""
from email.utils import getaddresses, parseaddr

from . import checker

RECIPIENT_HEADERS = ("To", "Cc", "Delivered-To", "X-Original-To", "Envelope-To", "X-Delivered-To")
IGNORE_SENDERS = ("mailer-daemon", "postmaster", "noreply-dmarc", "dmarc")


def _own(alias):
    return {checker.registrable(alias["service"]), *(checker.registrable(r) for r in alias["related"])}


def scan(store, messages):
    """Mails an Aliase von fremden Absendern finden. Gibt neue Funde zurück."""
    aliases = {a["alias"]: a for a in store.aliases()}
    if not aliases:
        return []
    new = []
    for msg in messages:
        rcpts = {addr.lower() for _, addr in getaddresses(
            [v for h in RECIPIENT_HEADERS for v in (msg.get_all(h) or [])])}
        sender = parseaddr(msg.get("From", ""))[1].lower()
        if not sender or sender.split("@")[0] in IGNORE_SENDERS:
            continue
        sender_domain = checker.registrable(sender.rsplit("@", 1)[-1])
        for rcpt in rcpts & set(aliases):
            a = aliases[rcpt]
            if sender_domain in _own(a) or sender in aliases:
                continue
            f = {"kind": "alias_leak", "subject": rcpt, "key": sender_domain, "source": "inbox",
                 "severity": "hoch", "title": f"Post von {sender_domain} an deinen Alias für {a['service']}",
                 "domain": sender_domain, "date": None, "classes": ["Email addresses"],
                 "alias_service": a["service"],
                 "actions": [("hoch", f"{a['service']} hat deinen Alias weitergegeben oder verloren. Auskunft und "
                                      f"Löschung verlangen: `alias request {rcpt}`; Alias ggf. deaktivieren."),
                             ("mittel", f"Ist {sender_domain} ein legitimer Partner von {a['service']}, mit "
                                        f"`alias add {rcpt} {a['service']} --related {sender_domain}` freigeben.")]}
            if store.add_finding(f):
                new.append(f)
    return new
