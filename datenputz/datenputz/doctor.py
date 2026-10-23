"""Selbsttest: prüft Einrichtung, Zugänge und alle Online-Dienste mit einer Ampel.

Es werden nur Test- oder öffentliche Werte abgefragt (test@example.com,
ein festes Hash-Präfix, example.com) – keine persönlichen Daten.
"""
import imaplib
import shutil
import smtplib
import ssl
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import breach as BR
from . import brokers as B
from . import keystore as K
from . import net
from . import shield as SH
from . import store as S
from . import vpn as V

OK, WARN, BAD, INFO = "ok", "warn", "bad", "info"
ICON = {OK: "✔", WARN: "⚠", BAD: "✖", INFO: "ℹ"}
TEST_EMAIL = "test@example.com"


def _perm(path, want):
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        return None
    return mode & ~want == 0


# --- lokale Prüfungen --------------------------------------------------------
def local_checks(st):
    out = []
    v = sys.version_info
    out.append((OK if v >= (3, 9) else BAD, "Python", f"{v.major}.{v.minor}.{v.micro}"))
    for path, want, label in ((st.dir, 0o700, "Datenordner"), (st.dir / "datenputz.db", 0o600, "Datenbank"),
                              (st.config_path, 0o600, "Konfiguration")):
        res = _perm(path, want)
        if res is not None:
            out.append((OK if res else BAD, label,
                        f"{path} ({'nur du hast Zugriff' if res else 'auch für andere lesbar – chmod ' + oct(want)[2:]})"))
    profiles = st.profiles()
    out.append((OK if profiles else WARN, "Profile", f"{len(profiles)} angelegt" if profiles else "keins – `init`"))
    out.append((OK, "Händlerdatenbank", f"{len(B.all_brokers())} Einträge"))
    backend = K.backend()
    out.append((OK if backend else WARN, "Schlüsselbund",
                backend or "nicht gefunden – Geheimnisse liegen in config.json (Rechte 600)"))
    if (st.config().get("secrets") or {}) and backend:
        out.append((WARN, "Geheimnisse", "liegen noch in config.json – mit `secret set …` in den Schlüsselbund holen"))
    bl = SH.folder() / "blocklist.txt"
    if bl.exists():
        age = (time.time() - bl.stat().st_mtime) / 86400
        out.append((OK if age < 8 else WARN, "Sperrlisten", f"{age:.0f} Tage alt" + ("" if age < 8 else " – `shield update`")))
    vs = V.load()
    if vs:
        out.append((OK if shutil.which("wg") else INFO, "VPN", f"{len(vs['peers'])} Geräte; "
                    + ("WireGuard installiert" if shutil.which("wg") else "WireGuard-Werkzeug nicht auf diesem Rechner")))
    sched = st.get_kv("schedule")
    out.append((OK if sched else WARN, "Zeitsteuerung", f"{sched['kind']}, täglich {sched['time']}" if sched
                else "nicht eingerichtet – `schedule install`"))
    last = st.get_kv("daily_last")
    if last:
        when = S.parse(last["at"])
        hours = (S.now() - when).total_seconds() / 3600
        failed = [s for s in last.get("steps", []) if s[1] == BAD]
        out.append((BAD if failed else OK if hours < 30 else WARN, "Letzter Automatiklauf",
                    f"vor {hours:.0f} h" + (f", Fehler in: {', '.join(s[0] for s in failed)}" if failed else "")))
    chans = st.config().get("notify", {}).get("channels", [])
    out.append((OK if chans else WARN, "Benachrichtigung",
                ", ".join(c["type"] for c in chans) if chans else "keine – `notify setup ntfy`"))
    return out


# --- Online-Prüfungen ---------------------------------------------------------
def _hibp(st):
    key = K.get("hibp", st)
    if not key:
        return WARN, "Have I Been Pwned", "kein API-Schlüssel – `secret set hibp` (sonst nur freie Quellen)"
    s = BR.subscription(key)
    until = s.get("SubscribedUntil")
    level, note = OK, ""
    if until:
        days = (datetime.fromisoformat(until.replace("Z", "+00:00")) - datetime.now(timezone.utc)).days
        if days < 14:
            level, note = WARN, f" – läuft in {days} Tagen ab"
    return level, "Have I Been Pwned", f"{s.get('SubscriptionName')} · {s.get('Rpm')} Abfragen/min{note}"


def _pwned(st):
    status, body = net.fetch(BR.PWNED_RANGE + "21BD1", headers={"Add-Padding": "true"}, timeout=10)
    return (OK if status == 200 and b":" in body else BAD), "Pwned Passwords", "erreichbar (k-Anonymität)"


def _source(name, fn):
    label = BR.SOURCES[name][0].split(" – ")[0]

    def check(st):
        fn(TEST_EMAIL)
        return OK, label, "erreichbar"
    check.label = label
    return check


def _doh(st):
    upstream = SH.DEFAULT_UPSTREAM
    _, resp = net.fetch(upstream, data=SH.build_query("example.com"), method="POST", timeout=10,
                        headers={"Content-Type": "application/dns-message", "Accept": "application/dns-message"})
    rcode = resp[3] & 0x0F
    answers = struct.unpack(">H", resp[6:8])[0]
    return (OK if rcode == 0 and answers else BAD), "Verschlüsseltes DNS (DoH)", f"{upstream} antwortet"


def _smtp(st):
    c = st.config().get("smtp")
    if not c:
        return INFO, "SMTP (Versand)", "nicht eingerichtet – Anfragen nur als Entwurf"
    pw = K.get("smtp", st)
    if not pw:
        return WARN, "SMTP (Versand)", "Passwort nicht im Schlüsselbund – Automatik kann nicht senden (`secret set smtp`)"
    ctx = ssl.create_default_context()
    if c.get("security", "starttls") == "ssl":
        conn = smtplib.SMTP_SSL(c["host"], c.get("port", 465), context=ctx, timeout=15)
    else:
        conn = smtplib.SMTP(c["host"], c.get("port", 587), timeout=15)
        conn.starttls(context=ctx)
    try:
        conn.login(c["user"], pw)
    finally:
        conn.quit()
    return OK, "SMTP (Versand)", f"Anmeldung bei {c['host']} erfolgreich"


def _imap(st):
    c = st.config().get("imap")
    if not c:
        return INFO, "IMAP (Antworten)", "nicht eingerichtet – Antworten von Hand mit `mark` eintragen"
    pw = K.get("imap", st) or K.get("smtp", st)
    if not pw:
        return WARN, "IMAP (Antworten)", "Passwort nicht hinterlegt (`secret set imap`)"
    conn = imaplib.IMAP4_SSL(c["host"], c.get("port", 993), timeout=15)
    try:
        conn.login(c["user"], pw)
        conn.select(c.get("folder", "INBOX"), readonly=True)
    finally:
        conn.logout()
    return OK, "IMAP (Antworten)", f"Anmeldung bei {c['host']} erfolgreich"


def online_checks(st, login=True):
    checks = [_hibp, _pwned, _doh]
    enabled = set(st.config().get("darkweb_sources") or []) & set(st.config().get("darkweb_consent") or [])
    for name in ("xposedornot", "leakcheck", "hudsonrock"):
        if name in enabled:
            checks.append(_source(name, BR.EXTRA[name][0]))
    if login:
        checks += [_smtp, _imap]

    def run(fn):
        try:
            return fn(st)
        except Exception as e:  # jede Prüfung einzeln: ein Ausfall verdeckt die anderen nicht
            return BAD, getattr(fn, "label", LABELS.get(fn.__name__, fn.__name__)), f"Fehler: {e}"
    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(run, checks))


LABELS = {"_hibp": "Have I Been Pwned", "_pwned": "Pwned Passwords", "_doh": "Verschlüsseltes DNS (DoH)",
          "_smtp": "SMTP (Versand)", "_imap": "IMAP (Antworten)"}


def run(st, online=True, login=True):
    out = local_checks(st)
    if online:
        out += online_checks(st, login)
    return out
