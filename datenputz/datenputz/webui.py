"""Seiten der Web-Oberfläche (serverseitig gerendert, ohne Inline-Skripte oder -Styles)."""
import html
import json
import re
from datetime import datetime

from . import breach as BR
from . import brokers as B
from . import checker as C
from . import keystore as K
from . import letters as L
from . import notify as N
from . import qr
from . import report as R
from . import score as SC
from . import shield as SH
from . import store as S
from . import vpn as V
from .webassets import icon

E = html.escape
SEV_TONE = {"kritisch": "bad", "hoch": "warn", "mittel": "info", "info": "muted"}
LEVEL_TONE = {"ok": "good", "warn": "warn", "bad": "bad", "info": "muted", "skip": "muted"}
PAGE_SIZE = 50

NAV = [("/heute", "Heute", "heute"), ("/", "Übersicht", "uebersicht"), ("/anfragen", "Anfragen", "anfragen"),
       ("/leaks", "Leaks", "leaks"), ("/pruefen", "Prüfen", "pruefen")]
SETUP_STEPS = [("profil", "Profil"), ("mail", "Mail"), ("leaks", "Leak-Quellen"), ("push", "Handy"), ("auto", "Automatik")]

MAIL_PRESETS = {
    "gmail": {"label": "Gmail", "smtp_host": "smtp.gmail.com", "smtp_port": "587", "smtp_security": "starttls",
              "imap_host": "imap.gmail.com", "imap_port": "993",
              "hint": "Gmail braucht ein App-Passwort (Google-Konto → Sicherheit → App-Passwörter, 2FA nötig)."},
    "outlook": {"label": "Outlook / Microsoft 365", "smtp_host": "smtp-mail.outlook.com", "smtp_port": "587",
                "smtp_security": "starttls", "imap_host": "outlook.office365.com", "imap_port": "993",
                "hint": "Bei aktivierter Zwei-Faktor-Anmeldung ein App-Kennwort verwenden."},
    "gmx": {"label": "GMX", "smtp_host": "mail.gmx.net", "smtp_port": "587", "smtp_security": "starttls",
            "imap_host": "imap.gmx.net", "imap_port": "993", "hint": "In den GMX-Einstellungen POP3/IMAP-Zugriff erlauben."},
    "webde": {"label": "WEB.DE", "smtp_host": "smtp.web.de", "smtp_port": "587", "smtp_security": "starttls",
              "imap_host": "imap.web.de", "imap_port": "993", "hint": "In den WEB.DE-Einstellungen IMAP/SMTP erlauben."},
    "tonline": {"label": "T-Online", "smtp_host": "securesmtp.t-online.de", "smtp_port": "465", "smtp_security": "ssl",
                "imap_host": "secureimap.t-online.de", "imap_port": "993",
                "hint": "Eigenes E-Mail-Passwort für Mailprogramme im Kundencenter anlegen."},
    "icloud": {"label": "iCloud", "smtp_host": "smtp.mail.me.com", "smtp_port": "587", "smtp_security": "starttls",
               "imap_host": "imap.mail.me.com", "imap_port": "993", "hint": "App-spezifisches Passwort unter appleid.apple.com erzeugen."},
    "posteo": {"label": "Posteo", "smtp_host": "posteo.de", "smtp_port": "587", "smtp_security": "starttls",
               "imap_host": "posteo.de", "imap_port": "993", "hint": ""},
    "mailboxorg": {"label": "mailbox.org", "smtp_host": "smtp.mailbox.org", "smtp_port": "587", "smtp_security": "starttls",
                   "imap_host": "imap.mailbox.org", "imap_port": "993", "hint": ""},
    "ionos": {"label": "IONOS", "smtp_host": "smtp.ionos.de", "smtp_port": "587", "smtp_security": "starttls",
              "imap_host": "imap.ionos.de", "imap_port": "993", "hint": ""},
}

EVENT_LABEL = {
    "created": "Geplant", "sent": "Antrag gesendet", "reminder_sent": "Erinnerung gesendet",
    "reminder_manual": "Frist abgelaufen – bitte über das Formular nachhaken", "handover": "Formular/Brief vorbereitet",
    "reply": "Antwort erhalten", "status": "Status geändert", "escalated": "Beschwerdeentwurf erstellt",
    "complaint_filed": "Beschwerde eingereicht",
}


# --- Bausteine ----------------------------------------------------------------
class Ctx:
    def __init__(self, csrf, job=None, flash=None, remote=False, login_url=""):
        self.csrf, self.job, self.flash, self.remote, self.login_url = csrf, job or {}, flash, remote, login_url

    def hidden(self, **fields):
        out = f'<input type="hidden" name="csrf" value="{E(self.csrf)}">'
        return out + "".join(f'<input type="hidden" name="{E(k)}" value="{E(str(v))}">' for k, v in fields.items())

    def button(self, action, label, primary=False, confirm=None, cls="", **fields):
        classes = " ".join(x for x in ("primary" if primary else "", cls) if x)
        attr = f' class="{classes}"' if classes else ""
        conf = f' data-confirm="{E(confirm)}"' if confirm else ""
        return (f'<form class="inline" method="post" action="{E(action)}"{conf}>{self.hidden(**fields)}'
                f'<button{attr}>{E(label)}</button></form>')

    def job_button(self, name, label, back="/", primary=False, confirm=None):
        return self.button("/job", label, primary, confirm, name=name, back=back)


def layout(ctx, title, body, active, counts=None):
    counts = counts or {}

    def nav_link(path, label, ic, bottom=False):
        cur = ' aria-current="page"' if path == active else ""
        badge = f'<span class="badge">{counts[path]}</span>' if counts.get(path) else ""
        if bottom:
            return f'<a href="{path}"{cur}>{icon(ic)}<span>{E(label)}{badge}</span></a>'
        return f'<a href="{path}"{cur}>{E(label)}{badge}</a>'
    top = "".join(nav_link(p, n, i) for p, n, i in NAV)
    bottom = "".join(nav_link(p, n, i, True) for p, n, i in NAV)
    links = "".join(
        f'<a href="{p}"{" aria-current=page" if p == active else ""} title="{n}">{icon(i)}<span class="label">{n}</span></a>'
        for p, n, i in (("/einrichten", "Einrichten", "einrichten"), ("/system", "System", "system")))
    toast = f'<div id="toast" class="toast" role="status">{E(ctx.flash)}</div>' if ctx.flash else ""
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#2f6f5e"><meta name="color-scheme" content="light dark">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Datenputz">
<link rel="manifest" href="/manifest.webmanifest"><link rel="icon" href="/static/icon-192.png">
<link rel="apple-touch-icon" href="/static/apple-180.png"><link rel="stylesheet" href="/static/app.css">
<title>{E(title)} · Datenputz</title></head><body>
<a class="skip" href="#main">Zum Inhalt springen</a>
<header><div class="bar"><a class="brand" href="/heute"><img src="/static/icon-192.png" alt="">Datenputz</a>
<nav class="top" aria-label="Hauptnavigation">{top}</nav><div class="toplinks">{links}</div></div></header>
<main id="main">{job_box(ctx)}{body}</main>
<nav class="bottom" aria-label="Hauptnavigation">{bottom}</nav>{toast}
<script src="/static/app.js"></script></body></html>"""


def bare(title, body):
    """Seite ohne Navigation (Anmeldung, offline)."""
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">'
            f'<link rel="stylesheet" href="/static/app.css"><link rel="icon" href="/static/icon-192.png">'
            f'<title>{E(title)} · Datenputz</title></head><body><main id="main" class="login">{body}</main></body></html>')


def job_box(ctx):
    j = ctx.job
    if not j.get("title"):
        return ""
    running = j.get("running")
    return (f'<section id="job" class="job" data-running="{1 if running else 0}" aria-live="polite">'
            f'<b>{E(j["title"])}</b>: <span class="state">{"läuft …" if running else "fertig"}</span>'
            f'<pre>{E(chr(10).join(j.get("log", [])[-60:]))}</pre></section>')


def pill(tone, text):
    return f'<span class="pill {tone}">{E(text)}</span>'


def textarea(tid, text, rows=10):
    return f'<textarea id="{tid}" readonly rows="{rows}" aria-label="Text">{E(text)}</textarea>'


def copy_button(tid, label="Text kopieren"):
    return f'<button type="button" data-copy="{tid}">{E(label)}</button>'


def qr_block(text, title, level="M"):
    return f'<div class="qr">{qr.QR(text, level).svg(scale=1, title=title)}</div>'


def _d(s):
    return R._d(s)


# --- Status der Einrichtung ---------------------------------------------------
def setup_status(st):
    cfg = st.config()
    consent = set(cfg.get("darkweb_consent") or []) & set(cfg.get("darkweb_sources") or [])
    return {
        "profil": bool(st.profiles()),
        "mail": bool(cfg.get("smtp")) and bool(K.get("smtp", st)),
        "leaks": bool(K.get("hibp", st) or consent),
        "push": bool(N.channels(st)),
        "auto": bool(st.get_kv("schedule")),
    }


# --- Heute für dich -------------------------------------------------------------
def _last_status_detail(st, rid):
    for e in reversed(st.events(rid)):
        if e["type"] in ("status", "reply"):
            return e["detail"] or ""
    return ""


def today_cards(st):
    """Liste von Karten: dict(key, kind, tone, title, html_fn(ctx), …)."""
    cards = []
    status = setup_status(st)
    for step, label in SETUP_STEPS[:3]:
        if not status[step]:
            cards.append({"key": f"setup:{step}", "kind": "Einrichtung", "tone": "info",
                          "title": f"Einrichtung: {label}",
                          "text": {"profil": "Lege dein Profil an – danach plant Datenputz Löschanträge an alle passenden Händler.",
                                   "mail": "Verbinde dein Postfach, damit Anträge und Erinnerungen automatisch versendet werden.",
                                   "leaks": "Wähle Quellen für die Leak-Überwachung (HIBP-Schlüssel oder freie Quellen)."}[step],
                          "link": (f"/einrichten?s={step}", "Jetzt einrichten")})
            break
    idx = B.by_id()
    filed = set(st.get_kv("complaints_filed", []))
    for r in st.requests(statuses=(S.AWAITING_USER,)):
        b = idx.get(r["broker_id"], {"name": r["broker_id"]})
        detail = _last_status_detail(st, r["id"]).lower()
        if re.search(r"ausweis|identit|verify your identity|proof of identity", detail):
            cards.append({"key": f"req:{r['id']}", "kind": "Ausweis verlangt", "tone": "warn", "req": r, "broker": b,
                          "title": f"{b['name']} verlangt eine Ausweiskopie",
                          "text": "Das ist meist unzulässig (Art. 12 Abs. 6 DSGVO). Schicke diese Antwort als Antwort auf "
                                  "die Mail des Händlers.",
                          "letter": L.id_rebuttal(st.profile_by_id(r["profile_id"]), b),
                          "done": (S.SENT, "Antwort gesendet")})
        elif r["channel"] == "webform":
            cards.append({"key": f"req:{r['id']}", "kind": "Formular", "tone": "warn", "req": r, "broker": b,
                          "title": f"Formular bei {b['name']} ausfüllen",
                          "text": "Öffne das Formular, kopiere den Text hinein und schicke es ab.",
                          "letter": _strip_head(_read_note(st, r)), "open": b.get("webform"),
                          "done": (S.SENT, "Abgeschickt")})
        else:
            cards.append({"key": f"req:{r['id']}", "kind": "Brief", "tone": "warn", "req": r, "broker": b,
                          "title": f"Brief an {b['name']} senden",
                          "text": f"Ausdrucken, unterschreiben und an {(b.get('address') or '').replace(chr(10), ', ')} schicken.",
                          "letter": _read_note(st, r), "done": (S.SENT, "Abgeschickt")})
    for r in st.requests(statuses=(S.ESCALATED,)):
        if r["id"] in filed:
            continue
        b = idx.get(r["broker_id"], {"name": r["broker_id"]})
        cards.append({"key": f"complaint:{r['id']}", "kind": "Beschwerde", "tone": "bad", "req": r, "broker": b,
                      "title": f"Beschwerde gegen {b['name']} einreichen",
                      "text": "Die Frist ist verstrichen. Prüfe den Entwurf und reiche ihn bei der Aufsichtsbehörde ein "
                              "(Formular oder Mail), Kopien aus dem Ordner sent/ anhängen.",
                      "letter": _read_note(st, r), "complaint": True})
    from .darkweb_cli import action_plan
    done = set(st.get_kv("plan_done", []))
    for sev, text, subject in action_plan(st.findings()):
        if BR.RANK[sev] <= BR.RANK["hoch"] and SC.plan_hash(text) not in done:
            cards.append({"key": f"plan:{SC.plan_hash(text)}", "kind": f"Leak · {sev}", "tone": SEV_TONE[sev],
                          "title": text, "text": f"Betrifft {subject}.", "plan": SC.plan_hash(text)})
    if BR.manual_due(st) and st.profiles():
        cards.append({"key": "manual", "kind": "Vierteljährlich", "tone": "info",
                      "title": "Handprüfung bei HPI, Uni Bonn und Co.",
                      "text": "Diese Dienste schicken das Ergebnis nur an die geprüfte Adresse – deshalb einmal im Quartal von Hand.",
                      "links": BR.MANUAL_CHECKS, "manual": True})
    if not st.get_kv("vault_audit") and st.profiles():
        cards.append({"key": "vault", "kind": "Passwörter", "tone": "info", "title": "Alle Passwörter prüfen",
                      "text": "Exportiere deinen Passwortmanager als CSV und führe im Terminal aus: "
                              "python -m datenputz breach vault export.csv --shred"})
    return cards


def _read_note(st, r):
    from pathlib import Path
    if not r["note"]:
        return ""
    p = Path(r["note"]).resolve()
    try:
        p.relative_to(st.dir.resolve())
    except ValueError:
        return ""
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def _strip_head(text):
    return text.split("Text zum Einfügen:\n", 1)[-1].lstrip()


def ordered_cards(st):
    cards = today_cards(st)
    skip = st.get_kv("today_skip") or {}
    skipped = set(skip.get("keys", [])) if skip.get("d") == S.now().date().isoformat() else set()
    return [c for c in cards if c["key"] not in skipped] + [c for c in cards if c["key"] in skipped]


def page_today(ctx, st, q):
    cards = ordered_cards(st)
    if not cards:
        body = ('<h1>Heute für dich</h1><div class="card empty"><div class="big-icon">✓</div><h2>Alles erledigt</h2>'
                '<p class="lead">Datenputz arbeitet im Hintergrund weiter und meldet sich, wenn es etwas zu tun gibt.</p>'
                '<a class="btn" href="/">Zur Übersicht</a></div>')
        return "Heute", body
    c = cards[0]
    n = len(cards)
    tid = "letter"
    parts = [f'<p class="kind">{pill(c["tone"], c["kind"])}</p><h2>{E(c["title"])}</h2><p>{E(c["text"])}</p>']
    if c.get("links"):
        parts.append('<ul class="plain">' + "".join(
            f'<li><a href="{E(u)}" target="_blank" rel="noopener noreferrer">{E(name)} ↗</a><div class="sub">{E(note)}</div></li>'
            for name, u, note in c["links"]) + "</ul>")
    if c.get("letter"):
        parts.append(textarea(tid, c["letter"], 12))
    actions = []
    if c.get("link"):
        actions.append(f'<a class="btn primary big" href="{E(c["link"][0])}">{E(c["link"][1])}</a>')
    if c.get("open"):
        actions.append(f'<a class="btn primary big" href="{E(c["open"])}" target="_blank" rel="noopener noreferrer">Formular öffnen ↗</a>')
    if c.get("letter"):
        actions.append(copy_button(tid))
    if c.get("done"):
        status, label = c["done"]
        actions.append(ctx.button("/mark", label, primary=not c.get("open"), id=c["req"]["id"], status=status,
                                  back="/heute", note=f"über „Heute“: {label}"))
    if c.get("req") and not c.get("complaint"):
        actions.append(ctx.button("/mark", "Hat sich erledigt", id=c["req"]["id"], status=S.NO_DATA, back="/heute"))
    if c.get("complaint"):
        actions.append(ctx.button("/complaint-filed", "Eingereicht", primary=True, id=c["req"]["id"]))
    if c.get("plan"):
        actions.append(ctx.button("/plan", "Erledigt", primary=True, h=c["plan"], back="/heute"))
    if c.get("manual"):
        actions.append(ctx.button("/manual-done", "Alle geprüft", primary=True))
    actions.append(ctx.button("/heute/skip", "Später", key=c["key"]))
    detail = f'<a href="/anfrage/{c["req"]["id"]}">Verlauf ansehen</a>' if c.get("req") else ""
    pct = round(100 / n) if n else 100
    body = (f'<div class="spread"><h1>Heute für dich</h1><a href="/aufgaben">Alle {n} Aufgaben als Liste</a></div>'
            f'<p class="lead">Schritt 1 von {n} – immer nur eine Sache auf einmal.</p>'
            f'<div class="progress" data-w="{pct}"><span></span></div>'
            f'<article class="card focus-card">{"".join(parts)}<div class="row">{"".join(actions)}</div>'
            f'<p class="sub">{detail}</p></article>')
    return "Heute", body


# --- Übersicht ------------------------------------------------------------------
def chart_svg(history):
    if len(history) < 2:
        return ""
    w, h, l, r, t, b = 900, 260, 64, 14, 14, 34
    n = len(history)
    xs = [l + (w - l - r) * i / (n - 1) for i in range(n)]

    def y(v):
        return t + (h - t - b) * (1 - v / 100)
    pts = [{"x": round(xs[i], 1), "y": round(y(hh["score"]), 1), "label": _date(hh["d"]),
            "value": f"{hh['score']} Punkte · {hh['done']}/{hh['total']} Händler erledigt"} for i, hh in enumerate(history)]
    grid = "".join(f'<line class="gridline" vector-effect="non-scaling-stroke" x1="{l}" x2="{w - r}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                   f'<text class="axis" x="{l - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>' for v in (0, 50, 100))
    ticks = sorted({0, n // 2, n - 1})
    xl = "".join(f'<text class="axis" x="{xs[i]:.1f}" y="{h - 8}" text-anchor="{"start" if i == 0 else "end" if i == n - 1 else "middle"}">'
                 f'{E(_date(history[i]["d"]))}</text>' for i in ticks)
    path = "M" + " L".join(f"{p['x']},{p['y']}" for p in pts)
    dots = "".join(f'<circle class="pt" cx="{p["x"]}" cy="{p["y"]}" r="4"/>' for p in pts) if n <= 31 else ""
    last = pts[-1]
    return (f'<div class="chart-box"><svg class="chart" viewBox="0 0 {w} {h}" tabindex="0" role="img" '
            f'aria-label="Privatsphäre-Wert von {E(pts[0]["label"])} bis {E(last["label"])}: zuletzt {history[-1]["score"]} Punkte" '
            f'data-points="{E(json.dumps(pts))}">{grid}{xl}<line class="xh" vector-effect="non-scaling-stroke" x1="0" x2="0" y1="{t}" y2="{h - b}"/>'
            f'<path class="line" vector-effect="non-scaling-stroke" d="{path}"/>{dots}<circle class="focus" r="6" cx="{last["x"]}" cy="{last["y"]}"/></svg>'
            f'<div class="tip" aria-hidden="true"></div></div>')


def _date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def page_overview(ctx, st, q):
    if not st.profiles():
        body = ('<div class="card empty hero"><img src="/static/icon-192.png" alt="" width="72" height="72">'
                '<h1>Willkommen bei Datenputz</h1><p class="lead">In fünf kurzen Schritten bist du startklar: Profil, Mail, '
                'Leak-Quellen, Handy-Benachrichtigung, Automatik.</p><a class="btn primary big" href="/einrichten">'
                'Einrichtung starten</a></div>')
        return "Übersicht", body
    SC.record(st)
    items = R.rows(st, B.by_id())
    findings = st.findings()
    score, parts, tips = SC.privacy_score(st, items, findings)
    _, done = R.summary(items)
    cards = ordered_cards(st)
    crit = sum(1 for f in findings if f["severity"] == "kritisch")
    hist = st.get_kv("history", [])
    last = st.get_kv("daily_last")
    parts_html = "".join(f"<li>{E(n)}: <b>{round(v * 100)} %</b> <span class=sub>(Gewicht {w})</span></li>"
                         for n, w, v in parts)
    tips_html = "".join(f"<li>{E(t)}</li>" for t in tips) or "<li>Alles eingerichtet – weiter so.</li>"
    tiles = [("/anfragen?f=erledigt", "Händler erledigt", f"{done}/{len(items)}"),
             ("/heute", "Aufgaben für dich", len(cards)), ("/leaks", "Leak-Funde", len(findings)),
             ("/leaks", "davon kritisch", crit)]
    tiles_html = "".join(f'<a class="tile" href="{p}"><div class="v">{E(str(v))}</div><div class="k">{E(k)}</div></a>'
                         for p, k, v in tiles)
    cta = (f'<a class="card spread" href="/heute"><span><b>Heute für dich:</b> {len(cards)} Schritt'
           f'{"e" if len(cards) != 1 else ""} – {E(cards[0]["title"])}</span><span class="btn primary">Los geht’s</span></a>'
           if cards else '<div class="card">✓ Heute ist nichts zu tun.</div>')
    chart = chart_svg(hist)
    table = "".join(f"<tr><td>{E(_date(h['d']))}</td><td class=num>{h['score']}</td><td class=num>{h['done']}/{h['total']}</td>"
                    f"<td class=num>{h['serious']}</td></tr>" for h in reversed(hist[-60:]))
    chart_card = (f'<div class="card"><h3>Privatsphäre-Wert im Verlauf</h3>{chart}'
                  f'<details><summary>Als Tabelle</summary><div class="wrap"><table><thead><tr><th>Tag</th><th>Wert</th>'
                  f'<th>Händler erledigt</th><th>Offene ernste Leaks</th></tr></thead><tbody>{table}</tbody></table></div></details></div>'
                  if chart else '<div class="card"><h3>Verlauf</h3><p class="sub">Der Verlauf erscheint ab dem zweiten Tag.</p></div>')
    last_html = f"Letzter Automatiklauf: {E(_d(last['at']))}" if last else "Noch kein Automatiklauf – unter Einrichten → Automatik einschalten."
    body = f"""<h1>Übersicht</h1><p class="lead">{last_html}</p>
<div class="card hero score"><div class="ring" data-p="{score}"><span>{score}</span></div>
<div><b>Privatsphäre-Wert</b><ul>{parts_html}</ul></div><div><b>Als Nächstes</b><ul>{tips_html}</ul></div></div>
{cta}<div class="grid">{tiles_html}</div>{chart_card}
<h2>Aktionen</h2><div class="row">{ctx.job_button("daily", "Jetzt alles erledigen", "/", True,
    "Jetzt Antworten lesen, fällige Anträge und Erinnerungen versenden und Leaks prüfen?")}
{ctx.job_button("leaks", "Nur Leaks prüfen")}{ctx.job_button("replies", "Antworten lesen")}</div>"""
    return "Übersicht", body


# --- Aufgaben (Liste) -----------------------------------------------------------
def page_tasks(ctx, st, q):
    cards = ordered_cards(st)
    out = []
    for i, c in enumerate(cards):
        tid = f"t{i}"
        letter = (f'<details><summary>Text anzeigen</summary>{textarea(tid, c["letter"], 10)}'
                  f'<div class="row">{copy_button(tid)}</div></details>' if c.get("letter") else "")
        link = (f'<a href="{E(c["open"])}" target="_blank" rel="noopener noreferrer">Formular öffnen ↗</a>' if c.get("open")
                else f'<a href="{E(c["link"][0])}">{E(c["link"][1])}</a>' if c.get("link") else "")
        acts = []
        if c.get("done"):
            acts.append(ctx.button("/mark", c["done"][1], id=c["req"]["id"], status=c["done"][0], back="/aufgaben"))
        if c.get("plan"):
            acts.append(ctx.button("/plan", "Erledigt", h=c["plan"], back="/aufgaben"))
        if c.get("complaint"):
            acts.append(ctx.button("/complaint-filed", "Eingereicht", id=c["req"]["id"], back="/aufgaben"))
        out.append(f'<div class="card"><div class="spread"><span>{pill(c["tone"], c["kind"])} <b>{E(c["title"])}</b></span>'
                   f'{link}</div><p class="sub">{E(c["text"])}</p>{letter}<div class="row">{"".join(acts)}</div></div>')
    body = ('<div class="spread"><h1>Aufgaben</h1><a class="btn" href="/heute">Eine nach der anderen</a></div>'
            '<p class="lead">Schritte, die nur du erledigen kannst.</p>' + ("".join(out) or '<div class="card">✓ Keine offenen Aufgaben.</div>'))
    return "Aufgaben", body


# --- Löschanfragen --------------------------------------------------------------
FILTERS = [("alle", "Alle", None), ("du", "Braucht dich", (S.AWAITING_USER, S.ESCALATED)),
           ("laeuft", "Läuft", (S.PENDING, S.SENT, S.REMINDED)), ("erledigt", "Erledigt", S.DONE)]


def page_requests(ctx, st, q):
    items = R.rows(st, B.by_id())
    f = (q.get("f") or ["alle"])[0]
    term = (q.get("q") or [""])[0].strip().lower()
    page = max(1, int((q.get("page") or ["1"])[0]) if (q.get("page") or ["1"])[0].isdigit() else 1)
    statuses = dict((k, s) for k, _, s in FILTERS).get(f)
    tabs = "".join(
        f'<a href="/anfragen?f={k}"{" aria-current=page" if k == f else ""}>{E(n)} '
        f'<span class="num">{sum(1 for x in items if s is None or x["r"]["status"] in s)}</span></a>' for k, n, s in FILTERS)
    sel = [x for x in items if (statuses is None or x["r"]["status"] in statuses)
           and (not term or term in (x["b"]["name"] + " " + x["b"].get("id", "") + " " + x["p"]["name"]).lower())]
    pages = max(1, -(-len(sel) // PAGE_SIZE))
    page = min(page, pages)
    rows = []
    for x in sel[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
        r, b = x["r"], x["b"]
        rows.append(f'<tr><td><a href="/anfrage/{r["id"]}">{E(b["name"])}</a><div class="sub">{E(", ".join(b.get("categories", [])))}</div></td>'
                    f'<td class="hide-sm">{E(x["p"]["name"])}</td><td>{pill(R.TONE[r["status"]], R.LABEL[r["status"]])}</td>'
                    f'<td class="num hide-sm">{_d(r["sent_at"])}</td><td class="num">{_d(r["due_at"]) if r["status"] in S.OPEN else ""}</td></tr>')

    def pg(n, label):
        return f'<a class="btn" href="/anfragen?f={E(f)}&amp;q={E(term)}&amp;page={n}">{label}</a>'
    pager = ""
    if pages > 1:
        pager = (f'<nav class="pager" aria-label="Seiten">{pg(page - 1, "‹ Zurück") if page > 1 else ""}'
                 f'<span class="btn" aria-current="page">Seite {page} von {pages}</span>{pg(page + 1, "Weiter ›") if page < pages else ""}</nav>')
    _, done = R.summary(items)
    body = f"""<h1>Löschanfragen</h1><p class="lead">{done} von {len(items)} Händlern erledigt.</p>
<div class="tabs" role="navigation" aria-label="Filter">{tabs}</div>
<form method="get" action="/anfragen" class="row mb"><input type="hidden" name="f" value="{E(f)}">
<input name="q" value="{E(term)}" placeholder="Händler oder Person suchen …" aria-label="Suche"><button>Suchen</button></form>
<div class="wrap"><table><thead><tr><th>Händler</th><th class="hide-sm">Person</th><th>Status</th><th class="hide-sm">Gesendet</th>
<th>Frist</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan=5>Keine Einträge.</td></tr>'}</tbody></table></div>{pager}"""
    return "Löschanfragen", body


def page_request_detail(ctx, st, rid):
    r = st.request(rid)
    if not r:
        return None
    b = B.by_id().get(r["broker_id"], {"name": r["broker_id"], "categories": []})
    p = st.profile_by_id(r["profile_id"])
    if r["identity"]:
        p = {**p, **json.loads(r["identity"])}
    rounds = st.requests(profile_id=r["profile_id"], broker_id=r["broker_id"])
    events = sorted((e for rr in rounds for e in st.events(rr["id"])), key=lambda e: e["ts"], reverse=True)
    tl = "".join(f'<li><time>{E(_dt(e["ts"]))}</time><b>{E(EVENT_LABEL.get(e["type"], e["type"]))}</b>'
                 f'{f"<div class=sub>{E(_event_text(e))}</div>" if _event_text(e) else ""}</li>' for e in events)
    links = []
    for key, label in (("webform", "Formular"), ("web", "Website")):
        if b.get(key):
            links.append(f'<a href="{E(b[key])}" target="_blank" rel="noopener noreferrer">{label} ↗</a>')
    if b.get("email"):
        links.append(f'<span class="sub">{E(b["email"])}</span>')
    hints = "".join(f"<li>{E(c)}</li>" for c in b.get("comments", []))
    opts = "".join(f'<option value="{k}"{" selected" if k == r["status"] else ""}>{v}</option>' for k, v in R.LABEL.items())
    status_form = (f'<form method="post" action="/mark" class="row">{ctx.hidden(id=r["id"], back=f"/anfrage/{r["id"]}")}'
                   f'<label class="sr" for="st">Status</label><select id="st" name="status">{opts}</select>'
                   f'<input name="note" placeholder="Notiz (optional)" aria-label="Notiz"><button class="primary">Speichern</button></form>')
    sent = S.parse(r["sent_at"]) or S.now()
    try:
        subject, letter = L.render(r["kind"], p, b, sent, urls=json.loads(r["urls"]) if r["urls"] else None, round_=r["round"])
    except Exception:
        subject, letter = "", ""
    id_card = ""
    if r["status"] == S.AWAITING_USER and re.search(r"ausweis|identit", _last_status_detail(st, r["id"]).lower()):
        id_card = (f'<div class="card"><h3>Ausweis verlangt – Antwortvorlage</h3>{textarea("idr", L.id_rebuttal(p, b), 10)}'
                   f'<div class="row">{copy_button("idr")}</div></div>')
    due = f" · Frist {_d(r['due_at'])}" if r["status"] in S.OPEN and r["due_at"] else ""
    body = f"""<p><a href="/anfragen">‹ Alle Anfragen</a></p><div class="spread"><h1>{E(b['name'])}</h1>
{pill(R.TONE[r['status']], R.LABEL[r['status']])}</div>
<p class="lead">{E(R.KIND.get(r['kind'], r['kind']))} für {E(p['name'])} · Runde {r['round']}{due} · {E(', '.join(b.get('categories', [])))}</p>
<div class="row">{' · '.join(links)}</div>
{f'<div class="card"><h3>Hinweise</h3><ul>{hints}</ul></div>' if hints else ''}{id_card}
<div class="card"><h3>Status ändern</h3>{status_form}</div>
<h2>Verlauf</h2><div class="card"><ol class="timeline">{tl or '<li>Noch keine Ereignisse.</li>'}</ol></div>
<details class="card"><summary>Antrag: {E(subject)}</summary>{textarea("letter", letter, 16)}<div class="row">{copy_button("letter")}</div></details>"""
    return b["name"], body


def _dt(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return ts


def _event_text(e):
    d = e["detail"] or ""
    if e["type"] in ("sent", "reminder_sent"):
        return d.split(" (")[0]  # Empfänger ohne Dateipfad
    if e["type"] in ("handover", "escalated", "created"):
        return ""
    return d


# --- Leaks ------------------------------------------------------------------------
def page_leaks(ctx, st, q):
    from .darkweb_cli import action_plan
    findings = st.findings()
    done = set(st.get_kv("plan_done", []))
    plan = action_plan(findings)
    items = []
    for sev, t, subj in plan:
        h = SC.plan_hash(t)
        is_done = h in done
        items.append(f'<li class="spread{" done-item" if is_done else ""}"><span>{pill(SEV_TONE[sev], sev)} '
                     f'<span class="t">{E(t)}</span> <span class="sub">({E(subj)})</span></span>'
                     f'{ctx.button("/plan", "Wieder öffnen" if is_done else "Erledigt", h=h, back="/leaks#plan")}</li>')
    rows = "".join(
        f'<tr><td>{pill(SEV_TONE[f["severity"]], f["severity"])}</td><td>{E(BR.describe(f))}'
        f'<div class="sub">{E((f.get("actions") or [("", "")])[0][1])}</div></td><td>{E(f["subject"])}</td>'
        f'<td class="hide-sm">{E(f["source"])}</td><td class="num hide-sm">{E(f["found"][:10])}</td></tr>'
        for f in sorted(findings, key=lambda f: (BR.RANK[f["severity"]], f["subject"])))
    last = st.get_kv("breach_last_check")
    open_n = sum(1 for sev, t, _ in plan if SC.plan_hash(t) not in done)
    body = f"""<h1>Leaks</h1><p class="lead">Letzte Prüfung: {E(_d(last)) if last else 'noch nie'} ·
Quellen: {E(', '.join(st.config().get('darkweb_sources') or ['hibp']))} · <a href="/einrichten?s=leaks">ändern</a></p>
<div class="row">{ctx.job_button("leaks", "Jetzt prüfen", "/leaks", True)}</div>
<h2 id="plan">Maßnahmenplan <span class="sub">({open_n} offen)</span></h2><div class="card"><ul class="plain">{''.join(items) or '<li>Keine Maßnahmen offen.</li>'}</ul></div>
<h2>Alle Funde</h2><div class="wrap"><table><thead><tr><th>Stufe</th><th>Fund</th><th>Adresse</th><th class="hide-sm">Quelle</th><th class="hide-sm">Gefunden</th></tr></thead>
<tbody>{rows or '<tr><td colspan=5>Keine Funde.</td></tr>'}</tbody></table></div>"""
    return "Leaks", body


# --- Prüfen -----------------------------------------------------------------------
def verdict_card(verdict, title, reasons, extra=""):
    tone = {"unauffällig": "good", "verdächtig": "warn", "gefährlich": "bad"}[verdict]
    items = "".join(f"<li>{E(r)}</li>" for r in reasons)
    return f'<div class="card">{pill(tone, verdict)} <b>{E(title)}</b><ul>{items}</ul>{extra}</div>'


def page_check(ctx, st, q, text=""):
    result = ""
    if text.strip():
        single = not re.search(r"\s", text.strip())
        r = {"links": [C.check_url(text.strip())]} if single else C.check_text(text)
        parts = []
        if "verdict" in r:
            parts.append(verdict_card(r["verdict"], "Nachricht", r["reasons"]))
        for x in r["links"]:
            parts.append(verdict_card(x["verdict"], x["url"], x["reasons"],
                                      f'<p class="sub">Ohne Tracking: {E(x["clean"])}</p>' if x.get("clean") else ""))
        result = "".join(parts) or '<div class="card">Keine Links gefunden.</div>'
    body = f"""<h1>Prüfen</h1><p class="lead">Link, SMS oder Mail einfügen – geprüft wird nur auf diesem Gerät bzw. deinem Server.</p>
<form method="post" action="/pruefen" class="card">{ctx.hidden()}<label for="txt">Text oder Link</label>
<textarea id="txt" name="text" placeholder="https://… oder Nachrichtentext">{E(text)}</textarea>
<div class="row"><button class="primary">Prüfen</button></div></form>{result}"""
    return "Prüfen", body


# --- System -------------------------------------------------------------------------
def page_system(ctx, st, q):
    last = st.get_kv("daily_last")
    steps = "".join(f'<li>{pill(LEVEL_TONE.get(lv, "muted"), lv)} <b>{E(n)}</b>: {E(t)}</li>'
                    for n, lv, t in (last or {}).get("steps", []))
    secrets_html = "".join(f"<li>{E(label)}: <b>{E(where)}</b></li>" for _, label, where in K.status(st))
    sched = st.get_kv("schedule")
    stats = SH.folder() / "stats.json"
    dns = ""
    if stats.exists():
        s = json.loads(stats.read_text())
        dns = f'<div class="card"><h3>DNS-Filter</h3><p>{s["blocked"]} blockiert · {s["allowed"]} erlaubt</p></div>'
    phone = ""
    if ctx.remote:
        phone = (f'<details class="card"><summary>Auf dem Handy öffnen (QR-Code)</summary><p class="sub">Der Code enthält deinen '
                 f'Zugangsschlüssel – nur selbst scannen, nicht fotografieren lassen.</p>{qr_block(ctx.login_url, "Login-Link")}</details>')
    vpn = V.load()
    vpn_html = ""
    if vpn:
        peers = "".join(
            f'<details><summary>{E(pp["name"])} · {E(pp["mode"])} · {E(pp["address"])}</summary><p class="sub">Enthält den privaten '
            f'Schlüssel des Geräts – in der WireGuard-App „Aus QR-Code erstellen“.</p>{qr_block(V.client_conf(vpn, pp), "WireGuard " + pp["name"], "L")}</details>'
            for pp in vpn["peers"])
        vpn_html = f'<h2>VPN-Geräte</h2><div class="card">{peers or "Noch keine Geräte (`vpn add`)."}</div>'
    body = f"""<h1>System</h1>
<div class="row">{ctx.job_button("doctor", "Selbsttest starten", "/system", True)}{ctx.job_button("notifytest", "Testnachricht ans Handy", "/system")}</div>
<h2>Letzter Automatiklauf</h2><div class="card"><ul class="plain">{steps or '<li>noch keiner</li>'}</ul></div>
<h2>Zeitsteuerung</h2><div class="card">{E(f"{sched['kind']}, täglich {sched['time']}") if sched else
'Nicht eingerichtet – <a href="/einrichten?s=auto">jetzt einrichten</a>'}</div>{dns}{phone}{vpn_html}
<h2>Geheimnisse</h2><div class="card"><ul>{secrets_html}</ul><p class="sub">Werte werden hier nie angezeigt.</p></div>"""
    return "System", body


# --- Einrichtung ----------------------------------------------------------------------
def page_setup(ctx, st, q):
    status = setup_status(st)
    step = (q.get("s") or [next((k for k, _ in SETUP_STEPS if not status[k]), "profil")])[0]
    if step not in dict(SETUP_STEPS):
        step = "profil"
    nav = "".join(
        f'<li><a href="/einrichten?s={k}"{" aria-current=step" if k == step else ""} class="{"ok" if status[k] else ""}">'
        f'<span class="n">{"✓" if status[k] else i}</span>{E(n)}</a></li>' for i, (k, n) in enumerate(SETUP_STEPS, 1))
    form = {"profil": _setup_profile, "mail": _setup_mail, "leaks": _setup_leaks, "push": _setup_push,
            "auto": _setup_auto}[step](ctx, st, q)
    order = [k for k, _ in SETUP_STEPS]
    nxt = order[order.index(step) + 1] if step != order[-1] else None
    skip = f'<a href="/einrichten?s={nxt}">Überspringen ›</a>' if nxt else '<a href="/heute">Fertig – zu „Heute“ ›</a>'
    body = (f'<h1>Einrichten</h1><p class="lead">{sum(status.values())} von {len(SETUP_STEPS)} Schritten erledigt. '
            f'Jeder Schritt lässt sich später ändern.</p><ol class="steps">{nav}</ol>{form}<p class="row end">{skip}</p>')
    return "Einrichten", body


def _setup_profile(ctx, st, q):
    profiles = st.profiles()
    key = (q.get("p") or [profiles[0]["_key"] if profiles else "neu"])[0]
    p = next((x for x in profiles if x["_key"] == key), {}) if key != "neu" else {}
    others = "".join(f'<a href="/einrichten?s=profil&amp;p={E(x["_key"])}"{" aria-current=page" if x["_key"] == key else ""}>'
                     f'{E(x["name"])}</a>' for x in profiles)
    tabs = f'<div class="tabs">{others}<a href="/einrichten?s=profil&amp;p=neu"{" aria-current=page" if key == "neu" else ""}>+ Weitere Person</a></div>' if profiles else ""
    v = lambda k, default="": E(", ".join(p[k]) if isinstance(p.get(k), list) else str(p.get(k, default)))  # noqa: E731
    addresses = E("\n".join(a.replace("\n", ", ") for a in p.get("addresses", [])))
    is_primary = not profiles or bool(p) and p.get("_id") == profiles[0]["_id"]
    family = "" if is_primary else f"""
<label for="obo">Du handelst für diese Person? Dein Name</label><input id="obo" name="on_behalf_of_by" value="{v('on_behalf_of_by')}">
<label class="check"><input type="checkbox" name="consent" value="1"{' checked' if p.get('on_behalf_of_by') else ''}>
<span>Die Person hat zugestimmt (bei Kindern: ich bin sorgeberechtigt).</span></label>"""
    plan_box = "" if p else '<label class="check"><input type="checkbox" name="plan_now" value="1" checked><span>Löschanträge an alle passenden Händler gleich planen</span></label>'
    return f"""{tabs}<form method="post" action="/einrichten/profil" class="card">{ctx.hidden(key=key)}
<p class="sub">Es werden nur Angaben verschickt, die zur Identifikation nötig sind. Telefon und Geburtsdatum nur, wenn ein Händler sie verlangt.</p>
<div class="form-grid"><div><label for="name">Vollständiger Name *</label><input id="name" name="name" required value="{v('name')}" autocomplete="name"></div>
<div><label for="aliases">Frühere/weitere Namen</label><input id="aliases" name="aliases" value="{v('aliases')}" placeholder="z. B. Geburtsname"></div></div>
<label for="emails">E-Mail-Adressen * <span class="sub">(kommagetrennt)</span></label><input id="emails" name="emails" required value="{v('emails')}" autocomplete="email">
<label for="addr">Anschriften <span class="sub">(eine pro Zeile, aktuelle zuerst)</span></label>
<textarea id="addr" name="addresses" rows="3" placeholder="Heidestraße 17, 51147 Köln">{addresses}</textarea>
<div class="form-grid"><div><label for="phones">Telefon (optional)</label><input id="phones" name="phones" value="{v('phones')}" autocomplete="tel"></div>
<div><label for="bd">Geburtsdatum (optional)</label><input id="bd" name="birthdate" value="{v('birthdate')}" placeholder="TT.MM.JJJJ"></div>
<div><label for="country">Land</label><input id="country" name="country" value="{v('country', 'de')}" maxlength="2"></div>
<div><label for="lang">Briefsprache</label><select id="lang" name="language"><option value="de">Deutsch</option>
<option value="en"{' selected' if p.get('language') == 'en' else ''}>Englisch</option></select></div></div>
<label class="check"><input type="checkbox" name="include_public" value="1"{' checked' if p.get('include_public') else ''}>
<span>US-Personensuchseiten einbeziehen (Spokeo, Whitepages …)</span></label>{family}{plan_box}
<div class="row end"><button class="primary big">Speichern & weiter</button></div></form>"""


def _setup_mail(ctx, st, q):
    cfg = st.config()
    sm, im = cfg.get("smtp", {}), cfg.get("imap", {})
    has_pw, has_ipw = bool(K.get("smtp", st)), bool(K.get("imap", st))
    presets = {k: {kk: vv for kk, vv in v.items() if kk != "label"} for k, v in MAIL_PRESETS.items()}
    opts = '<option value="">Anbieter wählen …</option>' + "".join(
        f'<option value="{k}">{E(v["label"])}</option>' for k, v in MAIL_PRESETS.items()) + '<option value="">Anderer Anbieter</option>'
    sec = sm.get("security", "starttls")
    return f"""<form method="post" action="/einrichten/mail" class="card">{ctx.hidden()}
<p class="sub">Anträge gehen von deinem eigenen Postfach raus – kein Dritter liest mit. Passwörter landen im Schlüsselbund des Systems.</p>
<label for="prov">Anbieter</label><select id="prov" name="provider" data-presets="{E(json.dumps(presets))}">{opts}</select>
<p class="hint" id="preset-hint" aria-live="polite"></p>
<h3>Versand (SMTP)</h3><div class="form-grid">
<div><label for="sh">Server</label><input id="sh" name="smtp_host" value="{E(sm.get('host', ''))}" placeholder="smtp.example.org"></div>
<div><label for="sp">Port</label><input id="sp" name="smtp_port" value="{E(str(sm.get('port', 587)))}" inputmode="numeric"></div>
<div><label for="ss">Verschlüsselung</label><select id="ss" name="smtp_security"><option value="starttls">STARTTLS</option>
<option value="ssl"{' selected' if sec == 'ssl' else ''}>SSL/TLS</option></select></div>
<div><label for="su">Benutzername</label><input id="su" name="smtp_user" value="{E(sm.get('user', ''))}" autocomplete="username"></div>
<div><label for="sf">Absender</label><input id="sf" name="smtp_from" value="{E(sm.get('from', ''))}" placeholder="gleich wie Benutzername"></div>
<div><label for="pw">Passwort {('<span class="good">✓ hinterlegt</span>' if has_pw else '')}</label>
<input id="pw" name="smtp_password" type="password" autocomplete="new-password" placeholder="{'leer lassen = unverändert' if has_pw else 'App-Passwort'}"></div></div>
<h3>Antworten lesen (IMAP)</h3><div class="form-grid">
<div><label for="ih">Server</label><input id="ih" name="imap_host" value="{E(im.get('host', ''))}" placeholder="imap.example.org"></div>
<div><label for="ip">Port</label><input id="ip" name="imap_port" value="{E(str(im.get('port', 993)))}" inputmode="numeric"></div>
<div><label for="iu">Benutzername</label><input id="iu" name="imap_user" value="{E(im.get('user', ''))}" placeholder="gleich wie SMTP"></div>
<div><label for="ipw">Passwort {('<span class="good">✓ hinterlegt</span>' if has_ipw else '')}</label>
<input id="ipw" name="imap_password" type="password" autocomplete="new-password" placeholder="leer = SMTP-Passwort"></div></div>
<div class="form-grid"><div><label for="dl">Maximal Mails pro Tag</label><input id="dl" name="daily_limit" value="{E(str(cfg.get('daily_limit', 40)))}" inputmode="numeric"></div></div>
<div class="row end"><button name="action" value="save">Speichern</button><button class="primary big" name="action" value="test">Speichern & Verbindung testen</button></div></form>"""


def _setup_leaks(ctx, st, q):
    cfg = st.config()
    active = set(cfg.get("darkweb_sources") or ["hibp"]) & (set(cfg.get("darkweb_consent") or []) | {"hibp"})
    has_key = bool(K.get("hibp", st))
    free = "".join(
        f'<label class="check"><input type="checkbox" name="src_{k}" value="1"{" checked" if k in active else ""}>'
        f'<span><b>{E(label)}</b><br><span class="sub">{E(note)}</span></span></label>'
        for k, (label, note) in BR.SOURCES.items() if k != "hibp")
    return f"""<form method="post" action="/einrichten/leaks" class="card">{ctx.hidden()}
<h3>Have I Been Pwned</h3><p class="sub">Leaks, Pastes und – im passenden Tarif – Stealer Logs. Schlüssel gibt es unter
<a href="https://haveibeenpwned.com/API/Key" target="_blank" rel="noopener noreferrer">haveibeenpwned.com/API/Key ↗</a>.</p>
<label for="hk">API-Schlüssel {('<span class="good">✓ hinterlegt</span>' if has_key else '')}</label>
<input id="hk" name="hibp_key" type="password" autocomplete="off" placeholder="{'leer lassen = unverändert' if has_key else '32 Zeichen'}">
<h3>Kostenlose Quellen</h3><p class="sub">Mit dem Häkchen stimmst du zu, dass die Quelle deine Adressen erfährt.</p>{free}
<label for="me">Weitere Adressen überwachen <span class="sub">(alte, berufliche – eine pro Zeile)</span></label>
<textarea id="me" name="monitor_emails" rows="3">{E(chr(10).join(cfg.get('monitor_emails', [])))}</textarea>
<label for="md">Eigene Domains <span class="sub">(müssen bei HIBP bestätigt sein)</span></label>
<textarea id="md" name="monitor_domains" rows="2">{E(chr(10).join(cfg.get('monitor_domains', [])))}</textarea>
<div class="row end"><button class="primary big">Speichern & weiter</button></div></form>"""


def _setup_push(ctx, st, q):
    chans = N.channels(st)
    cur = chans[0] if chans else {"type": "ntfy"}
    t = cur["type"]
    qr_html = ""
    if t == "ntfy" and cur.get("topic"):
        url = f"{cur.get('server', 'https://ntfy.sh').rstrip('/')}/{cur['topic']}"
        qr_html = (f'<div class="card"><h3>Mit dem Handy abonnieren</h3><div class="row">{qr_block(url, "ntfy-Abo")}<div>'
                   f'<p>1. ntfy-App installieren (Android/iOS)<br>2. „Thema abonnieren“ → Server und Thema eintragen<br>'
                   f'oder diesen Code scannen.</p><p class="sub">Server: {E(cur.get("server", "https://ntfy.sh"))}<br>Thema: '
                   f'<code>{E(cur["topic"])}</code></p><p class="sub">Das Thema ist geheim zu halten.</p></div></div>'
                   f'<div class="row">{ctx.job_button("notifytest", "Testnachricht senden", "/einrichten?s=push", True)}</div></div>')
    radio = lambda v, label: f'<label class="check"><input type="radio" name="channel" value="{v}"{" checked" if t == v else ""}><span>{label}</span></label>'  # noqa: E731
    return f"""<form method="post" action="/einrichten/push" class="card">{ctx.hidden()}
<p class="sub">Datenputz meldet sich nur, wenn es etwas zu tun gibt – mit Anzahlen statt Details.</p>
{radio("ntfy", "<b>ntfy</b> – kostenlos, ohne Konto (empfohlen)")}
<div class="form-grid"><div><label for="ns">ntfy-Server</label><input id="ns" name="ntfy_server" value="{E(cur.get('server', 'https://ntfy.sh') if t == 'ntfy' else 'https://ntfy.sh')}"></div></div>
<label class="check"><input type="checkbox" name="ntfy_new_topic" value="1"><span>Neues geheimes Thema erzeugen</span></label>
{radio("telegram", "<b>Telegram</b>-Bot")}
<div class="form-grid"><div><label for="tc">Chat-ID</label><input id="tc" name="telegram_chat" value="{E(cur.get('chat_id', ''))}"></div>
<div><label for="tt">Bot-Token</label><input id="tt" name="telegram_token" type="password" autocomplete="off" placeholder="leer = unverändert"></div></div>
{radio("gotify", "<b>Gotify</b> (eigener Server)")}
<div class="form-grid"><div><label for="gs">Gotify-Server</label><input id="gs" name="gotify_server" value="{E(cur.get('server', '') if t == 'gotify' else '')}"></div>
<div><label for="gt">App-Token</label><input id="gt" name="gotify_token" type="password" autocomplete="off" placeholder="leer = unverändert"></div></div>
{radio("email", "<b>E-Mail</b> über dein Postfach")}
<label class="check"><input type="checkbox" name="full" value="1"{" checked" if N.detail(st) == "full" else ""}>
<span>Details in Meldungen (Adressen, Dienste) – nur mit eigenem Server empfehlenswert</span></label>
<div class="row end"><button class="primary big">Speichern</button></div></form>{qr_html}"""


def _setup_auto(ctx, st, q):
    from . import schedule as SCH
    s = st.get_kv("schedule")
    kind = SCH.detect()
    return f"""<form method="post" action="/einrichten/auto" class="card">{ctx.hidden()}
<p>Einmal täglich: Antworten lesen, Anträge und Erinnerungen senden, Leaks prüfen, Sperrlisten auffrischen – und nur bei Bedarf melden.</p>
<p class="sub">Erkannter Dienstplaner: <b>{E(kind)}</b>{' – eingerichtet: täglich ' + E(s['time']) if s else ''}</p>
<div class="form-grid"><div><label for="tm">Uhrzeit</label><input id="tm" name="time" type="time" value="{E(s['time'] if s else '07:43')}" required></div></div>
<div class="row end">{'<button name="action" value="remove" class="danger">Abschalten</button>' if s else ''}
<button class="primary big" name="action" value="install">{'Uhrzeit ändern' if s else 'Automatik einschalten'}</button></div></form>"""
