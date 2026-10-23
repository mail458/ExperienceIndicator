"""Lokale Web-Oberfläche: Übersicht, Aufgaben, Anfragen, Leaks, Prüfwerkzeuge.

Sicherheit:
* lauscht standardmäßig nur auf 127.0.0.1 (bzw. ausdrücklich auf der VPN-Adresse)
* Zugang nur über einen geheimen Einmal-Link → Sitzungs-Cookie (HttpOnly, SameSite=Strict)
* Host-Prüfung gegen DNS-Rebinding, CSRF-Token und Origin-Prüfung für jede Änderung
* strenge Content-Security-Policy, kein Einbetten, keine Weitergabe von Referrern
* zeigt nie Passwörter oder API-Schlüssel an
"""
import hashlib
import hmac
import html
import ipaddress
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import breach as BR
from . import brokers as B
from . import checker as C
from . import daily as D
from . import doctor
from . import engine as E
from . import keystore as K
from . import report as R
from . import shield as SH
from . import store as S
from . import vpn as V

E_ = html.escape
SEV_TONE = {"kritisch": "bad", "hoch": "warn", "mittel": "info", "info": "muted"}
LEVEL_TONE = {"ok": "good", "warn": "warn", "bad": "bad", "info": "muted", "skip": "muted"}

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--mut:#6b6b70;--line:#e4e4e0;--acc:#2f6f5e;
--good:#2f7d4f;--info:#2f5f9e;--warn:#a86a00;--bad:#b3362d}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1d1d20;--fg:#ececee;--mut:#9a9aa2;--line:#2e2e33;
--acc:#5fb39b;--good:#5cc085;--info:#7aa7e8;--warn:#e0a640;--bad:#ec7a70}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:var(--card);border-bottom:1px solid var(--line)}
.bar{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.brand{font-weight:700;margin-right:8px}nav a{color:var(--mut);text-decoration:none;padding:4px 0}
nav a.on{color:var(--fg);border-bottom:2px solid var(--acc)}nav{display:flex;gap:16px;flex-wrap:wrap}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 10px}
.lead{color:var(--mut);margin:0 0 18px}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.tile,.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile .v{font-size:26px;font-weight:650;font-variant-numeric:tabular-nums}.tile .k{color:var(--mut);font-size:13px}
.card{margin:10px 0}.score{display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.ring{width:96px;height:96px;border-radius:50%;display:grid;place-items:center;font-size:28px;font-weight:700;
background:conic-gradient(var(--acc) calc(var(--p)*1%),var(--line) 0)}.ring span{background:var(--card);width:76px;height:76px;
border-radius:50%;display:grid;place-items:center}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:720px}th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}tr:last-child td{border-bottom:0}
.sub{color:var(--mut);font-size:13px}a{color:inherit}.pill{font-size:12px;padding:1px 8px;border-radius:99px;border:1px solid currentColor;white-space:nowrap}
.good{color:var(--good)}.info{color:var(--info)}.warn{color:var(--warn)}.bad{color:var(--bad)}.muted{color:var(--mut)}
button,select,input,textarea{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
button{cursor:pointer}button.primary{background:var(--acc);border-color:var(--acc);color:#fff}
textarea{width:100%;min-height:140px;font:13px/1.45 ui-monospace,monospace}form.inline{display:inline-flex;gap:6px;margin:0}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.job{padding:10px 14px;border-radius:8px;border:1px solid var(--line);
background:var(--card);margin-bottom:16px;white-space:pre-wrap;font:13px/1.45 ui-monospace,monospace}
ul.plain{list-style:none;padding:0;margin:0}ul.plain li{padding:8px 0;border-bottom:1px solid var(--line)}ul.plain li:last-child{border:0}
.done{opacity:.55;text-decoration:line-through}.mb{margin-bottom:10px}
"""

JS = """
document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',()=>{
  const t=document.getElementById(b.dataset.copy);navigator.clipboard.writeText(t.value);b.textContent='Kopiert ✓';}));
const q=document.getElementById('q'),st=document.getElementById('st');
function f(){if(!q)return;const t=q.value.toLowerCase(),s=st?st.value:'';
 document.querySelectorAll('#tb tr').forEach(r=>{r.hidden=!(r.textContent.toLowerCase().includes(t)&&(!s||r.dataset.status===s));});}
if(q){q.addEventListener('input',f);} if(st){st.addEventListener('change',f);}
document.querySelectorAll('.ring[data-p]').forEach(r=>r.style.setProperty('--p',r.dataset.p));
const job=document.getElementById('job');
if(job&&job.dataset.running==='1'){setTimeout(()=>location.reload(),2500);}
"""

NAV = [("/", "Übersicht"), ("/aufgaben", "Aufgaben"), ("/anfragen", "Löschanfragen"), ("/leaks", "Leaks"),
       ("/pruefen", "Prüfen"), ("/system", "System")]


# ---------------------------------------------------------------------------
def privacy_score(st, items, findings):
    """0–100 aus vier Bereichen, mit Erklärung, was fehlt."""
    parts, tips = [], []
    c, done = R.summary(items)
    brokers = done / len(items) if items else 0
    parts.append(("Datenhändler", 40, brokers))
    if not items:
        tips.append("Löschanträge planen (Aufgaben → „Jetzt alles erledigen“ bzw. `plan`)")
    plan_done = set(st.get_kv("plan_done", []))
    open_serious = [f for f in findings if BR.RANK[f["severity"]] <= BR.RANK["hoch"]
                    and not all(_h(t) in plan_done for _, t in f.get("actions", []))]
    leaks = 1 / (1 + len(open_serious) / 3) if findings or st.get_kv("breach_last_check") else 0
    parts.append(("Leaks bearbeitet", 30, leaks))
    if not st.get_kv("breach_last_check"):
        tips.append("Leak-Prüfung einrichten (Leaks → „Jetzt prüfen“)")
    elif open_serious:
        tips.append(f"{len(open_serious)} ernste Leak-Funde abarbeiten (Leaks)")
    va = st.get_kv("vault_audit")
    vault = (1 - (va["kritisch"] + va["hoch"]) / max(1, va["total"])) if va else 0
    parts.append(("Passwörter", 15, vault))
    if not va:
        tips.append("Passwörter prüfen: `breach vault export.csv --shred`")
    prot = sum([bool(st.get_kv("schedule")), bool(st.config().get("notify", {}).get("channels")),
                (SH.folder() / "blocklist.txt").exists(), bool(V.load())]) / 4
    parts.append(("Schutz aktiv", 15, prot))
    if prot < 1:
        tips.append("Automatik, Benachrichtigung, DNS-Filter oder VPN einrichten (System)")
    score = round(sum(w * v for _, w, v in parts))
    return score, parts, tips


def _h(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
class App:
    def __init__(self, home, host="127.0.0.1", port=8765, token=None):
        self.home = Path(home)
        self.host, self.port = host, port
        self.token = token or secrets.token_urlsafe(24)
        self.session = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(24)
        self.failed = []
        self.job = {"name": None, "running": False, "log": [], "started": None}
        self.lock = threading.Lock()

    @property
    def url(self):
        h = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{h}:{self.port}/login?t={self.token}"

    def allowed_host(self, value):
        value = (value or "").lower()
        names = {self.host.lower(), f"[{self.host.lower()}]"}
        if _loopback(self.host):
            names |= {"localhost", "127.0.0.1", "[::1]"}
        return value in names or value in {f"{n}:{self.port}" for n in names}

    def store(self):
        return S.Store(self.home)

    # --- Hintergrundaufträge -----------------------------------------------
    def start_job(self, name, fn):
        with self.lock:
            if self.job["running"]:
                return False
            self.job = {"name": name, "running": True, "log": [], "started": time.time()}

        def runner():
            st = self.store()
            try:
                fn(st, lambda line: self.job["log"].append(str(line)))
            except Exception as e:
                self.job["log"].append(f"✖ Fehler: {e}")
            finally:
                st.close()
                self.job["running"] = False
        threading.Thread(target=runner, daemon=True).start()
        return True


def _loopback(host):
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return host == "localhost"


JOBS = {
    "daily": ("Täglicher Lauf", lambda st, log: D.run(st, log=log)),
    "leaks": ("Leak-Prüfung", lambda st, log: D.run(st, log=log, only={"Leak-Prüfung", "Dashboard"})),
    "replies": ("Antworten lesen", lambda st, log: D.run(st, log=log, only={"Antworten", "Aliase"})),
    "doctor": ("Selbsttest", lambda st, log: [log(f"{doctor.ICON[lv]} {n}: {t}") for lv, n, t in doctor.run(st)]),
}


# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    app: App = None
    server_version = "Datenputz"
    sys_version = ""

    def log_message(self, *args):  # keine Zugriffsprotokolle (enthielten den Login-Token)
        pass

    # --- Antworten -----------------------------------------------------------
    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        # „same-origin“ statt „no-referrer“: sonst senden Browser bei Formularen „Origin: null“ und die
        # Herkunftsprüfung schlägt fehl. Fremde Seiten erfahren weiterhin nichts.
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
                         "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _redirect(self, to, extra=None):
        self._send(303, "", extra={"Location": to, **(extra or {})})

    def _authed(self):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "dp_session" and hmac.compare_digest(v, self.app.session):
                return True
        return False

    def _guard(self):
        if not self.app.allowed_host(self.headers.get("Host")):
            self._send(421, "Falscher Host.", "text/plain; charset=utf-8")
            return False
        return True

    # --- GET -----------------------------------------------------------------
    def do_GET(self):
        if not self._guard():
            return
        u = urlsplit(self.path)
        if u.path == "/static/app.css":
            return self._send(200, CSS, "text/css; charset=utf-8")
        if u.path == "/static/app.js":
            return self._send(200, JS, "text/javascript; charset=utf-8")
        if u.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if u.path == "/login":
            return self._login(parse_qs(u.query).get("t", [""])[0])
        if not self._authed():
            return self._send(401, _page("Anmeldung nötig", "<h1>Anmeldung nötig</h1><p class=lead>Öffne den Link, den "
                                         "<code>python -m datenputz web</code> im Terminal ausgibt.</p>", None, ""))
        routes = {"/": self.overview, "/aufgaben": self.tasks, "/anfragen": self.requests, "/leaks": self.leaks,
                  "/pruefen": self.check, "/system": self.system}
        fn = routes.get(u.path)
        if not fn:
            return self._send(404, _page("Nicht gefunden", "<h1>Nicht gefunden</h1>", None, ""))
        st = self.app.store()
        try:
            self._send(200, fn(st, parse_qs(u.query)))
        finally:
            st.close()

    do_HEAD = do_GET

    def _login(self, token):
        now = time.time()
        self.app.failed = [t for t in self.app.failed if now - t < 60]
        if len(self.app.failed) >= 10:  # Bremse gegen Durchprobieren
            return self._send(429, "Zu viele Versuche – eine Minute warten.", "text/plain; charset=utf-8")
        if not token or not hmac.compare_digest(token, self.app.token):
            self.app.failed.append(now)
            return self._send(403, "Ungültiger Link.", "text/plain; charset=utf-8")
        cookie = f"dp_session={self.app.session}; HttpOnly; SameSite=Strict; Path=/"
        self._redirect("/", {"Set-Cookie": cookie})

    # --- POST ----------------------------------------------------------------
    def do_POST(self):
        if not self._guard():
            return
        if not self._authed():
            return self._send(401, "Anmeldung nötig.", "text/plain; charset=utf-8")
        origin = self.headers.get("Origin")
        if origin and not self.app.allowed_host(urlsplit(origin).netloc):
            return self._send(403, "Fremde Herkunft.", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 200_000:
            return self._send(413, "Zu groß.", "text/plain; charset=utf-8")
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode("utf-8", "replace")).items()}
        if not hmac.compare_digest(form.get("csrf", ""), self.app.csrf):
            return self._send(403, "Sitzung abgelaufen – Seite neu laden.", "text/plain; charset=utf-8")
        path = urlsplit(self.path).path
        st = self.app.store()
        try:
            if path == "/mark":
                status = form.get("status")
                if status not in S.ALL_STATUSES:
                    return self._send(400, "Unbekannter Status.", "text/plain; charset=utf-8")
                E.Engine(st).mark(int(form["id"]), status, form.get("note") or "über Web-Oberfläche")
                return self._redirect(_safe_back(form.get("back"), "/anfragen"))
            if path == "/plan":
                done = set(st.get_kv("plan_done", []))
                h = form.get("h", "")
                done.symmetric_difference_update({h})
                st.set_kv("plan_done", sorted(done))
                return self._redirect("/leaks#plan")
            if path == "/job":
                name = form.get("name")
                if name in JOBS:
                    self.app.start_job(name, JOBS[name][1])
                return self._redirect(_safe_back(form.get("back"), "/"))
            if path == "/pruefen":
                return self._send(200, self.check(st, {}, form.get("text", "")))
            return self._send(404, "Nicht gefunden.", "text/plain; charset=utf-8")
        finally:
            st.close()

    # --- Seiten --------------------------------------------------------------
    def _job_box(self):
        j = self.app.job
        if not j["name"]:
            return ""
        state = "läuft …" if j["running"] else "fertig"
        return (f'<div id="job" class="job" data-running="{1 if j["running"] else 0}"><b>{E_(JOBS[j["name"]][0])}: {state}</b>\n'
                + E_("\n".join(j["log"][-40:])) + "</div>")

    def _btn(self, name, label, back="/", primary=False):
        return (f'<form class="inline" method="post" action="/job"><input type="hidden" name="csrf" value="{self.app.csrf}">'
                f'<input type="hidden" name="name" value="{name}"><input type="hidden" name="back" value="{back}">'
                f'<button{" class=primary" if primary else ""}>{E_(label)}</button></form>')

    def _render(self, title, body, active):
        return _page(title, self._job_box() + body, active, self.app.csrf)

    def overview(self, st, q):
        items = R.rows(st, B.by_id())
        findings = st.findings()
        score, parts, tips = privacy_score(st, items, findings)
        c, done = R.summary(items)
        tasks = len(st.requests(statuses=(S.AWAITING_USER, S.ESCALATED)))
        crit = sum(1 for f in findings if f["severity"] == "kritisch")
        last = st.get_kv("daily_last")
        parts_html = "".join(f"<li>{E_(n)}: <b>{round(v * 100)}%</b> <span class=sub>(Gewicht {w})</span></li>"
                             for n, w, v in parts)
        tips_html = "".join(f"<li>{E_(t)}</li>" for t in tips) or "<li>Alles eingerichtet – weiter so.</li>"
        tiles = [("Händler erledigt", f"{done}/{len(items)}"), ("Aufgaben für dich", tasks),
                 ("Leak-Funde", len(findings)), ("davon kritisch", crit)]
        tiles_html = "".join(f'<div class="tile"><div class="v">{E_(str(v))}</div><div class="k">{E_(k)}</div></div>'
                             for k, v in tiles)
        last_html = f"Letzter Automatiklauf: {E_(R._d(last['at']))}" if last else "Noch kein Automatiklauf."
        body = f"""<h1>Übersicht</h1><p class="lead">{last_html}</p>
<div class="card score"><div class="ring" data-p="{score}"><span>{score}</span></div>
<div><b>Privatsphäre-Wert</b><ul>{parts_html}</ul></div><div><b>Als Nächstes</b><ul>{tips_html}</ul></div></div>
<div class="tiles">{tiles_html}</div>
<h2>Aktionen</h2><div class="row">{self._btn("daily", "Jetzt alles erledigen", "/", True)}
{self._btn("leaks", "Nur Leaks prüfen")}{self._btn("replies", "Antworten lesen")}</div>"""
        return self._render("Übersicht", body, "/")

    def tasks(self, st, q):
        idx = B.by_id()
        out = []
        for r in st.requests(statuses=(S.AWAITING_USER,)):
            b = idx.get(r["broker_id"], {"name": r["broker_id"]})
            text = _safe_read(st, r["note"])
            link = b.get("webform") or b.get("web") or ""
            last = (st.events(r["id"]) or [None])[-1]
            why = E_(last["detail"]) if last and last["type"] == "status" else (
                "Webformular ausfüllen" if r["channel"] == "webform" else "Brief drucken und senden")
            tid = f"t{r['id']}"
            out.append(f"""<div class="card"><div class="row"><b>{E_(b['name'])}</b><span class="pill warn">{why}</span>
{f'<a href="{E_(link)}" target="_blank" rel="noopener noreferrer">{"Formular öffnen" if r["channel"] == "webform" else "Website"} ↗</a>' if link else ''}</div>
{f'<textarea id="{tid}" readonly>{E_(text)}</textarea><div class="row"><button type="button" data-copy="{tid}">Text kopieren</button>' if text else '<div class="row">'}
{_mark_form(self.app.csrf, r['id'], S.SENT, 'Abgeschickt', '/aufgaben')}{_mark_form(self.app.csrf, r['id'], S.NO_DATA, 'Erledigt/keine Daten', '/aufgaben')}</div></div>""")
        for r in st.requests(statuses=(S.ESCALATED,)):
            b = idx.get(r["broker_id"], {"name": r["broker_id"]})
            tid = f"c{r['id']}"
            out.append(f"""<div class="card"><div class="row"><b>Beschwerde: {E_(b['name'])}</b><span class="pill bad">Frist verstrichen</span></div>
<p class="sub">Entwurf prüfen und an die Aufsichtsbehörde senden (Formular oder Mail), Kopien deiner Mails anhängen (Ordner <code>sent/</code>).</p>
<textarea id="{tid}" readonly>{E_(_safe_read(st, r['note']))}</textarea><div class="row"><button type="button" data-copy="{tid}">Text kopieren</button>
{_mark_form(self.app.csrf, r['id'], S.CONFIRMED, 'Hat sich erledigt', '/aufgaben')}</div></div>""")
        body = "<h1>Aufgaben</h1><p class=lead>Schritte, die nur du erledigen kannst.</p>" + (
            "".join(out) or '<div class="card">✔ Keine offenen Aufgaben.</div>')
        return self._render("Aufgaben", body, "/aufgaben")

    def requests(self, st, q):
        items = R.rows(st, B.by_id())
        c, done = R.summary(items)
        trs = []
        for x in items:
            r, b = x["r"], x["b"]
            trs.append(f'<tr data-status="{r["status"]}"><td>{E_(b["name"])}<div class="sub">{E_(", ".join(b.get("categories", [])))}</div></td>'
                       f'<td>{E_(x["p"]["name"])}</td><td>{R.KIND.get(r["kind"], r["kind"])} · R{r["round"]}</td>'
                       f'<td><span class="pill {R.TONE[r["status"]]}">{R.LABEL[r["status"]]}</span></td>'
                       f'<td>{R._d(r["sent_at"])}</td><td>{R._d(r["due_at"]) if r["status"] in S.OPEN else ""}</td>'
                       f'<td>{_status_form(self.app.csrf, r["id"], r["status"])}</td></tr>')
        options = "".join(f'<option value="{k}">{v} ({c[k]})</option>' for k, v in R.LABEL.items() if c[k])
        body = f"""<h1>Löschanfragen</h1><p class="lead">{done} von {len(items)} Händlern erledigt.</p>
<div class="row mb"><input id="q" placeholder="Suchen …" aria-label="Suche">
<select id="st" aria-label="Status"><option value="">Alle Status</option>{options}</select></div>
<div class="wrap"><table><thead><tr><th>Händler</th><th>Person</th><th>Art</th><th>Status</th><th>Versendet</th><th>Frist</th><th>Ändern</th></tr></thead>
<tbody id="tb">{''.join(trs)}</tbody></table></div>"""
        return self._render("Löschanfragen", body, "/anfragen")

    def leaks(self, st, q):
        from .darkweb_cli import action_plan
        findings = st.findings()
        done = set(st.get_kv("plan_done", []))
        plan = action_plan(findings)
        plan_html = "".join(
            f'<li class="{"done" if _h(t) in done else ""}"><form class="inline" method="post" action="/plan">'
            f'<input type="hidden" name="csrf" value="{self.app.csrf}"><input type="hidden" name="h" value="{_h(t)}">'
            f'<button title="erledigt umschalten">{"✓" if _h(t) in done else "○"}</button></form> '
            f'<span class="pill {SEV_TONE[sev]}">{sev}</span> {E_(t)} <span class="sub">({E_(subj)})</span></li>'
            for sev, t, subj in plan)
        rows = "".join(
            f'<tr><td><span class="pill {SEV_TONE[f["severity"]]}">{f["severity"]}</span></td><td>{E_(BR.describe(f))}'
            f'<div class="sub">{E_((f.get("actions") or [("", "")])[0][1])}</div></td><td>{E_(f["subject"])}</td>'
            f'<td>{E_(f["source"])}</td><td>{E_(f["found"][:10])}</td></tr>'
            for f in sorted(findings, key=lambda f: (BR.RANK[f["severity"]], f["subject"])))
        last = st.get_kv("breach_last_check")
        body = f"""<h1>Leaks</h1><p class="lead">Letzte Prüfung: {E_(R._d(last)) if last else 'noch nie'} ·
Quellen: {E_(', '.join(st.config().get('darkweb_sources') or ['hibp']))}</p>
<div class="row">{self._btn("leaks", "Jetzt prüfen", "/leaks", True)}</div>
<h2 id="plan">Maßnahmenplan</h2><div class="card"><ul class="plain">{plan_html or '<li>Keine Maßnahmen offen.</li>'}</ul></div>
<h2>Alle Funde</h2><div class="wrap"><table><thead><tr><th>Stufe</th><th>Fund</th><th>Adresse</th><th>Quelle</th><th>Gefunden</th></tr></thead>
<tbody>{rows or '<tr><td colspan=5>Keine Funde.</td></tr>'}</tbody></table></div>"""
        return self._render("Leaks", body, "/leaks")

    def check(self, st, q, text=""):
        result = ""
        if text.strip():
            r = C.check_text(text) if " " in text.strip() or "\n" in text else {"links": [C.check_url(text.strip())]}
            parts = []
            if "verdict" in r:
                parts.append(_verdict(r["verdict"], "Nachricht", r["reasons"]))
            for x in r["links"]:
                parts.append(_verdict(x["verdict"], x["url"], x["reasons"]) +
                             (f'<p class="sub">Ohne Tracking: {E_(x["clean"])}</p>' if x.get("clean") else ""))
            result = "".join(parts) or '<div class="card">Keine Links gefunden.</div>'
        body = f"""<h1>Prüfen</h1><p class="lead">Link, SMS oder Mail einfügen – geprüft wird nur auf diesem Rechner.</p>
<form method="post" action="/pruefen" class="card"><input type="hidden" name="csrf" value="{self.app.csrf}">
<textarea name="text" placeholder="https://… oder Nachrichtentext">{E_(text)}</textarea>
<div class="row"><button class="primary">Prüfen</button></div></form>{result}"""
        return self._render("Prüfen", body, "/pruefen")

    def system(self, st, q):
        last = st.get_kv("daily_last")
        steps = "".join(f'<li><span class="pill {LEVEL_TONE.get(lv, "muted")}">{E_(lv)}</span> <b>{E_(n)}</b>: {E_(t)}</li>'
                        for n, lv, t in (last or {}).get("steps", []))
        secrets_html = "".join(f"<li>{E_(label)}: <b>{E_(where)}</b></li>" for _, label, where in K.status(st))
        sched = st.get_kv("schedule")
        body = f"""<h1>System</h1>
<div class="row">{self._btn("doctor", "Selbsttest starten", "/system", True)}</div>
<h2>Letzter Automatiklauf</h2><div class="card"><ul class="plain">{steps or '<li>noch keiner</li>'}</ul></div>
<h2>Zeitsteuerung</h2><div class="card">{E_(f"{sched['kind']}, täglich {sched['time']}") if sched else
'Nicht eingerichtet – <code>python -m datenputz schedule install</code>'}</div>
<h2>Geheimnisse</h2><div class="card"><ul>{secrets_html}</ul><p class="sub">Werte werden hier nie angezeigt.</p></div>"""
        return self._render("System", body, "/system")


# ---------------------------------------------------------------------------
def _page(title, body, active, csrf):
    nav = "".join(f'<a href="{p}" class="{"on" if p == active else ""}">{E_(n)}</a>' for p, n in NAV) if csrf else ""
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            f'initial-scale=1"><title>{E_(title)} · Datenputz</title><link rel="stylesheet" href="/static/app.css"></head>'
            f'<body><header><div class="bar"><span class="brand">Datenputz</span><nav>{nav}</nav></div></header>'
            f'<main>{body}</main><script src="/static/app.js"></script></body></html>')


def _mark_form(csrf, rid, status, label, back):
    return (f'<form class="inline" method="post" action="/mark"><input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="id" value="{rid}"><input type="hidden" name="status" value="{status}">'
            f'<input type="hidden" name="back" value="{back}"><button>{E_(label)}</button></form>')


def _status_form(csrf, rid, current):
    opts = "".join(f'<option value="{k}"{" selected" if k == current else ""}>{v}</option>' for k, v in R.LABEL.items())
    return (f'<form class="inline" method="post" action="/mark"><input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="id" value="{rid}"><input type="hidden" name="back" value="/anfragen">'
            f'<select name="status" aria-label="Status">{opts}</select><button>OK</button></form>')


def _verdict(verdict, title, reasons):
    tone = {"unauffällig": "good", "verdächtig": "warn", "gefährlich": "bad"}[verdict]
    items = "".join(f"<li>{E_(r)}</li>" for r in reasons)
    return f'<div class="card"><span class="pill {tone}">{verdict}</span> <b>{E_(title)}</b><ul>{items}</ul></div>'


def _safe_back(value, default):
    """Nur Pfade dieser Oberfläche als Rücksprung – verhindert Weiterleitung auf fremde Seiten (//evil.com)."""
    v = value or ""
    if v.startswith("/") and not v.startswith(("//", "/\\")) and "\\" not in v and "\n" not in v and "\r" not in v:
        return v
    return default


def _safe_read(st, path):
    """Nur Dateien aus dem Datenordner anzeigen."""
    if not path:
        return ""
    p = Path(path).resolve()
    try:
        p.relative_to(st.dir.resolve())
    except ValueError:
        return ""
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def make_server(home, host="127.0.0.1", port=8765, token=None):
    app = App(home, host, port, token)
    handler = type("BoundHandler", (Handler,), {"app": app})
    srv = ThreadingHTTPServer((host, port), handler)
    app.port = srv.server_address[1]
    return srv, app


def serve(home, host="127.0.0.1", port=8765, persistent_token=False, open_browser=False):
    token = K.get("web") if persistent_token else None
    srv, app = make_server(home, host, port, token)
    print(f"Datenputz läuft. Diesen Link öffnen (er ist dein Schlüssel – nicht teilen):\n  {app.url}\nBeenden mit Strg+C.")
    if open_browser:
        import webbrowser
        webbrowser.open(app.url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
