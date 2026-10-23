"""Versand: SMTP oder Entwurfsordner (.eml-Dateien zum Prüfen/Versenden im Mailprogramm)."""
import re
import smtplib
import ssl
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path


def build(sender, to, subject, body, reply_to=None, in_reply_to=None, quote=None):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = format_datetime(datetime.now().astimezone())
    domain = sender.rsplit("@", 1)[-1].strip("> ") if "@" in sender else None
    msg["Message-ID"] = make_msgid(domain=domain)
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    if quote:
        body += "\n\n" + "\n".join("> " + line for line in quote.splitlines())
    msg.set_content(body)
    return msg


class Outbox:
    """Schreibt Nachrichten als .eml – nichts verlässt den Rechner."""

    dry_run = True

    def __init__(self, directory):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, msg, name):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
        path = self.dir / f"{safe}.eml"
        path.write_bytes(bytes(msg))
        return str(path)

    def close(self):
        pass


class SMTPMailer:
    dry_run = False

    def __init__(self, cfg, delay=None):
        self.cfg = cfg
        self.delay = cfg.get("delay_seconds", 20) if delay is None else delay
        self.conn = None
        self._last = 0.0

    def _connect(self):
        c = self.cfg
        from . import keystore
        password = keystore.require("smtp", f"SMTP-Passwort für {c['user']}: ")
        ctx = ssl.create_default_context()
        if c.get("security", "starttls") == "ssl":
            conn = smtplib.SMTP_SSL(c["host"], c.get("port", 465), context=ctx, timeout=60)
        else:
            conn = smtplib.SMTP(c["host"], c.get("port", 587), timeout=60)
            conn.starttls(context=ctx)
        conn.login(c["user"], password)
        self.conn = conn

    def send(self, msg, name):
        if self.conn is None:
            self._connect()
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:  # Abstand zwischen Mails, damit der Anbieter das Konto nicht sperrt
            time.sleep(wait)
        self.conn.send_message(msg)
        self._last = time.monotonic()
        return msg["Message-ID"]

    def close(self):
        if self.conn:
            try:
                self.conn.quit()
            except smtplib.SMTPException:
                pass
