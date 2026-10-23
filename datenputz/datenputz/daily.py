"""Täglicher Automatiklauf: alles Fällige erledigen und nur bei Wichtigem melden.

Reihenfolge: Antworten lesen → Anfragen/Erinnerungen senden → Leak-Prüfung →
Alias-Prüfung → Sperrlisten (wöchentlich) → Dashboard → Benachrichtigung.
Jeder Schritt läuft für sich; ein Fehler stoppt die anderen nicht. Es wird
nie auf eine Eingabe gewartet.
"""
import time

from . import aliases as AL
from . import breach as BR
from . import brokers as B
from . import engine as E
from . import inbox as I
from . import keystore as K
from . import mailer as M
from . import notify
from . import report as R
from . import shield as SH
from . import store as S

OK, WARN, BAD, SKIP = "ok", "warn", "bad", "skip"
ICON = {OK: "✔", WARN: "⚠", BAD: "✖", SKIP: "–"}


def _emails(st):
    return sorted({e.lower() for p in st.profiles() for e in p.get("emails", [])}
                  | {e.lower() for e in st.config().get("monitor_emails", [])}
                  | {a["alias"] for a in st.aliases()})


def run(st, send=True, log=None, only=None):
    """`only`: Menge von Schrittnamen, z. B. {"Leak-Prüfung"} – alle anderen werden übersprungen."""
    log = log or (lambda *_: None)
    cfg = st.config()
    steps, notable = [], {"findings": [], "replies": {}, "tasks": 0, "escalated": 0}

    def step(name, fn):
        if only and name not in only:
            return
        try:
            level, text = fn()
        except Exception as e:
            level, text = BAD, str(e)
        steps.append((name, level, text))
        log(f"{ICON[level]} {name}: {text}")

    # 1. Postfach einmal lesen, für Antworten und Aliase nutzen
    messages = []

    def read_inbox():
        if not cfg.get("imap"):
            return SKIP, "kein IMAP eingerichtet"
        messages.extend(I.fetch(cfg["imap"], days=cfg.get("inbox_days", 30)))
        found = I.process(st, E.Engine(st), messages, apply=True)
        for f in found:
            v = f["verdict"] or "unklar"
            notable["replies"][v] = notable["replies"].get(v, 0) + 1
        return OK, f"{len(messages)} Mails gelesen, {len(found)} Antworten zugeordnet"
    step("Antworten", read_inbox)

    # 2. Löschanträge, Erinnerungen, Beschwerdeentwürfe, neue Runden
    def requests():
        if not st.requests():
            return SKIP, "keine Anfragen geplant (`plan`)"
        if not send:
            return SKIP, "Versand abgeschaltet"
        if not cfg.get("smtp"):
            return WARN, "kein SMTP – nichts versendet (`smtp`)"
        if not K.get("smtp", st):
            return BAD, "SMTP-Passwort nicht im Schlüsselbund (`secret set smtp`)"
        stats = E.Engine(st, M.SMTPMailer(cfg["smtp"])).run()
        notable["tasks"] += stats["manual"]
        notable["escalated"] += stats["escalated"]
        return OK, (f"{stats['sent']} gesendet, {stats['reminded']} Erinnerungen, {stats['escalated']} Beschwerden, "
                    f"{stats['recurring']} neue Runden, {stats['deferred']} verschoben")
    step("Löschanträge", requests)

    # 3. Leak-Prüfung mit den freigegebenen Quellen
    def leaks():
        key = K.get("hibp", st)
        consent = set(cfg.get("darkweb_consent") or [])
        sources = [s for s in (cfg.get("darkweb_sources") or ["hibp"]) if s == "hibp" and key or s in consent]
        emails = _emails(st)
        if not sources or not emails:
            return SKIP, ("keine Adresse (`init`)" if not emails else
                          "keine Quelle freigegeben (`secret set hibp` oder `breach sources --enable …`)")
        new, errors = BR.monitor(st, emails, sources, key=key, domains=cfg.get("monitor_domains", []))
        notable["findings"] += new
        level = WARN if errors else OK
        return level, f"{len(emails)} Adressen, {len(new)} neue Funde" + (f"; {len(errors)} Hinweise" if errors else "")
    step("Leak-Prüfung", leaks)

    # 4. Weitergabe von Aliasen (gleiche Mails wie Schritt 1)
    def alias_scan():
        if not st.aliases() or not messages:
            return SKIP, "keine Aliase oder keine Mails"
        new = AL.scan(st, messages)
        notable["findings"] += new
        return OK, f"{len(new)} neue Weitergaben"
    step("Aliase", alias_scan)

    # 5. Sperrlisten wöchentlich auffrischen
    def lists():
        bl = SH.folder() / "blocklist.txt"
        if not bl.exists():
            return SKIP, "DNS-Filter nicht eingerichtet"
        if time.time() - bl.stat().st_mtime < 6.5 * 86400:
            return SKIP, "aktuell"
        counts = SH.update(list(SH.SOURCES))
        return OK, f"{sum(counts.values())} Domains"
    step("Sperrlisten", lists)

    # 6. Dashboard
    def dashboard():
        out = st.dir / "report.html"
        out.write_text(R.render(st, B.by_id()), encoding="utf-8")
        out.chmod(0o600)
        return OK, str(out)
    step("Dashboard", dashboard)

    if not only:  # nur vollständige Läufe zählen für den Selbsttest
        st.set_kv("daily_last", {"at": S.iso(S.now()), "steps": steps,
                                 "findings": len(notable["findings"]), "replies": notable["replies"]})

    # 7. Nur melden, wenn es etwas zu tun gibt
    message = summarize(st, steps, notable)
    if message:
        title, body, level = message
        for channel, err in notify.send(st, title, body, level):
            log(f"{'✔' if not err else '✖'} Benachrichtigung {channel}" + (f": {err}" if err else ""))
    return steps, notable


def summarize(st, steps, notable):
    """(titel, text, stufe) oder None, wenn nichts Wichtiges passiert ist."""
    fs = notable["findings"]
    worst = min((f["severity"] for f in fs), key=BR.RANK.get) if fs else None
    errors = [s for s in steps if s[1] == BAD]
    confirmed = notable["replies"].get(S.CONFIRMED, 0) + notable["replies"].get(S.NO_DATA, 0) \
        + notable["replies"].get(S.SUPPRESSED, 0)
    action = notable["replies"].get(S.AWAITING_USER, 0) + notable["tasks"] + notable["escalated"]
    important = (worst and BR.RANK[worst] <= BR.RANK["hoch"]) or errors or action
    if not important and not confirmed:
        return None
    lines = []
    if fs:
        counts = {s: sum(1 for f in fs if f["severity"] == s) for s in BR.SEVERITIES}
        lines.append("Neue Leak-Funde: " + ", ".join(f"{v} {k}" for k, v in counts.items() if v))
        if notify.detail(st) == "full":
            lines += [f"  · {f['subject']}: {BR.describe(f)}" for f in sorted(fs, key=lambda f: BR.RANK[f["severity"]])[:8]]
    if confirmed:
        lines.append(f"{confirmed} Händler haben Löschung bestätigt oder keine Daten")
    if action:
        lines.append(f"{action} Aufgabe(n) warten auf dich (Formular, Ausweisanfrage, Beschwerde)")
    for name, _, text in errors:
        lines.append(f"Fehler bei {name}: {text}")
    level = worst if worst and BR.RANK[worst] <= BR.RANK["hoch"] else ("hoch" if errors else "mittel")
    title = "Datenputz: " + ("kritischer Fund" if worst == "kritisch" else "Fehler im Automatiklauf" if errors
                             and not fs else "es gibt etwas zu tun" if action or fs else "Fortschritt")
    return title, "\n".join(lines) + "\nDetails im Dashboard.", level
