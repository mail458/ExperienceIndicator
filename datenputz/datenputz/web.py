"""Lokale Web-Oberfläche (Server, Sicherheit, Routen). Die Seiten selbst stehen in webui.py.

Sicherheit:
* lauscht standardmäßig nur auf 127.0.0.1 (bzw. ausdrücklich auf der VPN-Adresse)
* Zugang nur über einen geheimen Link → Sitzungs-Cookie (HttpOnly, SameSite=Strict)
* Host-Prüfung gegen DNS-Rebinding, CSRF-Token und Origin-Prüfung für jede Änderung
* strenge Content-Security-Policy (nur 'self', keine Inline-Skripte/-Styles), kein Einbetten
* keine Weiterleitung auf fremde Seiten, Bremse gegen Durchprobieren des Links
* zeigt nie Passwörter oder API-Schlüssel an; Geheimnisse werden nur geschrieben
"""
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import daily as D
from . import doctor
from . import engine as E
from . import keystore as K
from . import notify as N
from . import schedule as SCH
from . import store as S
from . import webassets as A
from . import webui as U
from .score import privacy_score  # noqa: F401  (für Tests und Aufrufer)

STATIC = {
    "/static/app.css": (lambda: A.CSS, "text/css; charset=utf-8"),
    "/static/app.js": (lambda: A.JS, "text/javascript; charset=utf-8"),
    "/sw.js": (lambda: A.SERVICE_WORKER, "text/javascript; charset=utf-8"),
    "/manifest.webmanifest": (lambda: A.MANIFEST, "application/manifest+json; charset=utf-8"),
    "/static/icon-192.png": (lambda: A.png("icon-192"), "image/png"),
    "/static/icon-512.png": (lambda: A.png("icon-512"), "image/png"),
    "/static/maskable-512.png": (lambda: A.png("maskable-512"), "image/png"),
    "/static/apple-180.png": (lambda: A.png("apple-180"), "image/png"),
}


def _doctor_job(st, log):
    for lv, n, t in doctor.run(st):
        log(f"{doctor.ICON[lv]} {n}: {t}")


def _mail_test(st, log):
    for fn in (doctor._smtp, doctor._imap):
        try:
            lv, n, t = fn(st)
        except Exception as e:
            lv, n, t = doctor.BAD, doctor.LABELS[fn.__name__], f"Fehler: {e}"
        log(f"{doctor.ICON[lv]} {n}: {t}")


def _notify_test(st, log):
    res = N.send(st, "Datenputz: Testnachricht", "Benachrichtigungen funktionieren.", "info")
    if not res:
        log("Kein Kanal eingerichtet – Einrichten → Handy.")
    for ch, err in res:
        log(f"{'✔' if not err else '✖'} {ch}" + (f": {err}" if err else " – angekommen?"))


JOBS = {
    "daily": ("Täglicher Lauf", lambda st, log: D.run(st, log=log)),
    "leaks": ("Leak-Prüfung", lambda st, log: D.run(st, log=log, only={"Leak-Prüfung", "Dashboard"})),
    "replies": ("Antworten lesen", lambda st, log: D.run(st, log=log, only={"Antworten", "Aliase"})),
    "doctor": ("Selbsttest", _doctor_job),
    "mailtest": ("Mail-Verbindung", _mail_test),
    "notifytest": ("Testnachricht", _notify_test),
}


# ---------------------------------------------------------------------------
class App:
    def __init__(self, home, host="127.0.0.1", port=8765, token=None):
        self.home = Path(home)
        self.host, self.port = host, port
        self.token = token or secrets.token_urlsafe(24)
        # Fester Link → feste Sitzung (Lesezeichen am Handy bleiben gültig); sonst je Start neu
        self.session = (hmac.new(token.encode(), b"datenputz-session", hashlib.sha256).hexdigest() if token
                        else secrets.token_urlsafe(32))
        self.csrf = secrets.token_urlsafe(24)
        self.failed = []
        self.flash = None
        self.job = {"name": None, "title": None, "running": False, "log": [], "started": None}
        self.lock = threading.Lock()

    @property
    def url(self):
        h = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{h}:{self.port}/login?t={self.token}"

    @property
    def remote(self):
        return not _loopback(self.host)

    def allowed_host(self, value):
        value = (value or "").lower()
        names = {self.host.lower(), f"[{self.host.lower()}]"}
        if _loopback(self.host):
            names |= {"localhost", "127.0.0.1", "[::1]"}
        return value in names or value in {f"{n}:{self.port}" for n in names}

    def store(self):
        return S.Store(self.home)

    def start_job(self, name, fn, title=None):
        with self.lock:
            if self.job["running"]:
                return False
            self.job = {"name": name, "title": title or JOBS.get(name, (name,))[0], "running": True, "log": [],
                        "started": time.time()}

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


def _split(v, pattern=r"[,\n;]+"):
    return [x.strip() for x in re.split(pattern, v or "") if x.strip()]


# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    app: App = None
    server_version = "Datenputz"
    sys_version = ""

    def log_message(self, *args):  # keine Zugriffsprotokolle (enthielten den Login-Token)
        pass

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
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
                         "connect-src 'self'; manifest-src 'self'; worker-src 'self'; form-action 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _text(self, code, msg):
        self._send(code, msg, "text/plain; charset=utf-8")

    def _redirect(self, to, extra=None):
        self._send(303, "", extra={"Location": to, **(extra or {})})

    def _authed(self):
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "dp_session" and hmac.compare_digest(v, self.app.session):
                return True
        return False

    def _guard(self):
        if not self.app.allowed_host(self.headers.get("Host")):
            self._text(421, "Falscher Host.")
            return False
        return True

    def _ctx(self):
        flash, self.app.flash = self.app.flash, None
        return U.Ctx(self.app.csrf, self.app.job, flash, self.app.remote, self.app.url)

    # --- GET -----------------------------------------------------------------
    def do_GET(self):
        if not self._guard():
            return
        u = urlsplit(self.path)
        if u.path in STATIC:
            fn, ctype = STATIC[u.path]
            return self._send(200, fn(), ctype)
        if u.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if u.path == "/offline":
            return self._send(200, U.bare("Offline", '<div class="card empty"><h1>Keine Verbindung</h1><p class="lead">'
                                          'Datenputz läuft auf deinem Rechner bzw. Server. Prüfe WLAN oder VPN.</p></div>'))
        if u.path == "/login":
            return self._login(parse_qs(u.query).get("t", [""])[0])
        if not self._authed():
            return self._send(401, U.bare("Anmeldung nötig", '<div class="card"><h1>Anmeldung nötig</h1><p class="lead">'
                                          'Öffne den Link, den <code>python -m datenputz web</code> im Terminal ausgibt '
                                          '(am Handy: QR-Code unter System).</p></div>'))
        if u.path == "/job.json":
            j = self.app.job
            return self._send(200, json.dumps({"title": j.get("title"), "running": j.get("running"),
                                               "log": j.get("log", [])[-60:]}), "application/json")
        q = parse_qs(u.query)
        st = self.app.store()
        try:
            m = re.fullmatch(r"/anfrage/(\d+)", u.path)
            pages = {"/": (U.page_overview, "/"), "/heute": (U.page_today, "/heute"), "/aufgaben": (U.page_tasks, "/heute"),
                     "/anfragen": (U.page_requests, "/anfragen"), "/leaks": (U.page_leaks, "/leaks"),
                     "/pruefen": (U.page_check, "/pruefen"), "/system": (U.page_system, "/system"),
                     "/einrichten": (U.page_setup, "/einrichten")}
            ctx = self._ctx()
            if m:
                res = U.page_request_detail(ctx, st, int(m.group(1)))
                active = "/anfragen"
            elif u.path in pages:
                fn, active = pages[u.path]
                res = fn(ctx, st, q)
            else:
                res = None
            if not res:
                return self._send(404, U.layout(ctx, "Nicht gefunden", "<h1>Nicht gefunden</h1>", None))
            title, body = res
            counts = {"/heute": len(U.ordered_cards(st))}
            self._send(200, U.layout(ctx, title, body, active, counts))
        finally:
            st.close()

    do_HEAD = do_GET

    def _login(self, token):
        now = time.time()
        self.app.failed = [t for t in self.app.failed if now - t < 60]
        if len(self.app.failed) >= 10:  # Bremse gegen Durchprobieren
            return self._text(429, "Zu viele Versuche – eine Minute warten.")
        if not token or not hmac.compare_digest(token, self.app.token):
            self.app.failed.append(now)
            return self._text(403, "Ungültiger Link.")
        st = self.app.store()
        try:
            target = "/heute" if st.profiles() else "/einrichten"
        finally:
            st.close()
        self._redirect(target, {"Set-Cookie": f"dp_session={self.app.session}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000"})

    # --- POST ----------------------------------------------------------------
    def do_POST(self):
        if not self._guard():
            return
        if not self._authed():
            return self._text(401, "Anmeldung nötig.")
        origin = self.headers.get("Origin")
        if origin and not self.app.allowed_host(urlsplit(origin).netloc):
            return self._text(403, "Fremde Herkunft.")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 200_000:
            return self._text(413, "Zu groß.")
        form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode("utf-8", "replace"),
                                             keep_blank_values=True).items()}
        if not hmac.compare_digest(form.get("csrf", ""), self.app.csrf):
            return self._text(403, "Sitzung abgelaufen – Seite neu laden.")
        path = urlsplit(self.path).path
        st = self.app.store()
        try:
            handler = POST_ROUTES.get(path)
            if path.startswith("/einrichten/"):
                handler = SETUP_ROUTES.get(path.rsplit("/", 1)[-1])
            if not handler:
                return self._text(404, "Nicht gefunden.")
            return handler(self, st, form)
        finally:
            st.close()

    # Aktionen
    def post_mark(self, st, form):
        status = form.get("status")
        if status not in S.ALL_STATUSES or not form.get("id", "").isdigit():
            return self._text(400, "Unbekannter Status.")
        E.Engine(st).mark(int(form["id"]), status, form.get("note") or "über Web-Oberfläche")
        self.app.flash = f"Gespeichert: {U.R.LABEL[status]}"
        return self._redirect(_safe_back(form.get("back"), "/anfragen"))

    def post_plan(self, st, form):
        done = set(st.get_kv("plan_done", []))
        done.symmetric_difference_update({form.get("h", "")})
        st.set_kv("plan_done", sorted(done))
        self.app.flash = "Maßnahme aktualisiert"
        return self._redirect(_safe_back(form.get("back"), "/leaks#plan"))

    def post_job(self, st, form):
        name = form.get("name")
        if name in JOBS:
            started = self.app.start_job(name, JOBS[name][1])
            self.app.flash = f"{JOBS[name][0]} gestartet" if started else "Es läuft bereits ein Auftrag"
        return self._redirect(_safe_back(form.get("back"), "/"))

    def post_check(self, st, form):
        title, body = U.page_check(self._ctx(), st, {}, form.get("text", ""))
        return self._send(200, U.layout(self._ctx(), title, body, "/pruefen"))

    def post_skip(self, st, form):
        today = S.now().date().isoformat()
        skip = st.get_kv("today_skip") or {}
        keys = set(skip.get("keys", [])) if skip.get("d") == today else set()
        keys.add(form.get("key", ""))
        st.set_kv("today_skip", {"d": today, "keys": sorted(keys)})
        return self._redirect("/heute")

    def post_manual(self, st, form):
        st.set_kv("manual_checks_done", S.iso(S.now()))
        self.app.flash = "Vermerkt – nächste Erinnerung in 90 Tagen"
        return self._redirect("/heute")

    def post_complaint(self, st, form):
        if not form.get("id", "").isdigit():
            return self._text(400, "Ungültig.")
        rid = int(form["id"])
        filed = set(st.get_kv("complaints_filed", []))
        filed.add(rid)
        st.set_kv("complaints_filed", sorted(filed))
        st.log(rid, "complaint_filed", "über Web-Oberfläche")
        self.app.flash = "Beschwerde als eingereicht vermerkt"
        return self._redirect(_safe_back(form.get("back"), "/heute"))

    # Einrichtung
    def setup_profile(self, st, form):
        name = form.get("name", "").strip()
        emails = [e for e in _split(form.get("emails"), r"[,\s;]+") if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e)]
        if not name or not emails:
            self.app.flash = "Bitte Name und mindestens eine gültige E-Mail-Adresse angeben."
            return self._redirect("/einrichten?s=profil")
        if form.get("on_behalf_of_by", "").strip() and form.get("consent") != "1":
            self.app.flash = "Für andere Personen bitte die Einwilligung bestätigen."
            return self._redirect("/einrichten?s=profil&p=neu")
        key = form.get("key", "neu")
        existing = st.profile(key) if key != "neu" else None
        data = {k: v for k, v in (existing or {}).items() if not k.startswith("_")}
        data.update({
            "name": name, "aliases": _split(form.get("aliases")), "emails": emails,
            "addresses": _split(form.get("addresses"), r"\n+"), "phones": _split(form.get("phones")),
            "birthdate": form.get("birthdate", "").strip(), "country": (form.get("country") or "de").strip().lower()[:2],
            "language": "en" if form.get("language") == "en" else "de", "include_public": form.get("include_public") == "1",
        })
        if form.get("on_behalf_of_by", "").strip():
            data["on_behalf_of_by"] = form["on_behalf_of_by"].strip()
        data = {k: v for k, v in data.items() if v not in ("", [], None)}
        if not existing:
            base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:20] or "person"
            key, n = base, 2
            while st.profile(key):
                key, n = f"{base}-{n}", n + 1
        st.add_profile(key, data)
        msg = "Profil gespeichert."
        if form.get("plan_now") == "1":
            n = E.Engine(st).plan(st.profile(key))
            msg += f" {n} Löschanträge geplant – versendet wird mit der Automatik oder „Jetzt alles erledigen“."
        self.app.flash = msg
        return self._redirect("/einrichten?s=mail")

    def setup_mail(self, st, form):
        cfg = st.config()
        preset = U.MAIL_PRESETS.get(form.get("provider", ""), {})
        host = form.get("smtp_host", "").strip() or preset.get("smtp_host", "")
        if not host:
            self.app.flash = "Bitte SMTP-Server angeben oder einen Anbieter wählen."
            return self._redirect("/einrichten?s=mail")
        try:
            port = int(form.get("smtp_port") or preset.get("smtp_port") or 587)
            iport = int(form.get("imap_port") or preset.get("imap_port") or 993)
            limit = max(1, min(500, int(form.get("daily_limit") or 40)))
        except ValueError:
            self.app.flash = "Ports und Tageslimit müssen Zahlen sein."
            return self._redirect("/einrichten?s=mail")
        user = form.get("smtp_user", "").strip()
        sm = cfg.get("smtp", {})
        sm.update({"host": host, "port": port, "security": "ssl" if form.get("smtp_security") == "ssl" else "starttls",
                   "user": user, "from": form.get("smtp_from", "").strip() or user})
        sm.setdefault("delay_seconds", 20)
        cfg["smtp"], cfg["daily_limit"] = sm, limit
        ihost = form.get("imap_host", "").strip() or preset.get("imap_host", "")
        if ihost:
            cfg["imap"] = {**cfg.get("imap", {}), "host": ihost, "port": iport,
                           "user": form.get("imap_user", "").strip() or user}
        st.save_config(cfg)
        where = []
        if form.get("smtp_password"):
            where.append(K.put("smtp", form["smtp_password"], st))
        if form.get("imap_password"):
            where.append(K.put("imap", form["imap_password"], st))
        self.app.flash = "Mail gespeichert" + (f" – Passwort im {where[0]}" if where else "") + "."
        if form.get("action") == "test":
            self.app.start_job("mailtest", _mail_test)
            return self._redirect("/einrichten?s=mail")
        return self._redirect("/einrichten?s=leaks")

    def setup_leaks(self, st, form):
        from . import breach as BR
        key = form.get("hibp_key", "").strip()
        if key and not re.fullmatch(r"[0-9a-fA-F]{32}", key):
            self.app.flash = "Der HIBP-Schlüssel besteht aus 32 Hex-Zeichen – bitte prüfen."
            return self._redirect("/einrichten?s=leaks")
        if key:
            K.put("hibp", key, st)
        cfg = st.config()
        chosen = [k for k in BR.SOURCES if k != "hibp" and form.get(f"src_{k}") == "1"]
        cfg["darkweb_sources"] = ["hibp"] + chosen
        cfg["darkweb_consent"] = sorted(set(cfg.get("darkweb_consent") or []) | set(chosen))
        cfg["monitor_emails"] = [e.lower() for e in _split(form.get("monitor_emails"), r"[\s,;]+") if "@" in e]
        cfg["monitor_domains"] = [d.lower() for d in _split(form.get("monitor_domains"), r"[\s,;]+")
                                  if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", d.lower())]
        st.save_config(cfg)
        self.app.flash = "Leak-Quellen gespeichert."
        return self._redirect("/einrichten?s=push")

    def setup_push(self, st, form):
        kind = form.get("channel", "ntfy")
        old = next((c for c in N.channels(st) if c["type"] == kind), {})
        if kind == "ntfy":
            server = form.get("ntfy_server", "").strip().rstrip("/") or "https://ntfy.sh"
            if not re.fullmatch(r"https?://[^\s/]+(/[^\s]*)?", server):
                self.app.flash = "Bitte eine gültige Server-Adresse (https://…) angeben."
                return self._redirect("/einrichten?s=push")
            topic = old.get("topic") if old.get("topic") and form.get("ntfy_new_topic") != "1" else N.new_ntfy_topic()
            chan = {"type": "ntfy", "server": server, "topic": topic}
        elif kind == "telegram":
            if not form.get("telegram_chat", "").strip():
                self.app.flash = "Bitte die Chat-ID angeben."
                return self._redirect("/einrichten?s=push")
            chan = {"type": "telegram", "chat_id": form["telegram_chat"].strip()}
            if form.get("telegram_token"):
                K.put("telegram", form["telegram_token"].strip(), st)
        elif kind == "gotify":
            if not re.fullmatch(r"https?://\S+", form.get("gotify_server", "").strip()):
                self.app.flash = "Bitte die Gotify-Adresse angeben."
                return self._redirect("/einrichten?s=push")
            chan = {"type": "gotify", "server": form["gotify_server"].strip().rstrip("/")}
            if form.get("gotify_token"):
                K.put("gotify", form["gotify_token"].strip(), st)
        else:
            chan = {"type": "email"}
        cfg = st.config()
        cfg["notify"] = {"channels": [chan], "detail": "full" if form.get("full") == "1" else "minimal"}
        st.save_config(cfg)
        self.app.flash = "Gespeichert – jetzt eine Testnachricht senden."
        return self._redirect("/einrichten?s=push")

    def setup_auto(self, st, form):
        if form.get("action") == "remove":
            SCH.remove(st)
            self.app.flash = "Automatik abgeschaltet."
            return self._redirect("/einrichten?s=auto")
        t = form.get("time", "")
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
            self.app.flash = "Bitte eine Uhrzeit wie 07:43 angeben."
            return self._redirect("/einrichten?s=auto")
        self.app.start_job("schedule", lambda st, log: log(SCH.install(st, t)[1]), "Automatik einrichten")
        return self._redirect("/einrichten?s=auto")


POST_ROUTES = {"/mark": Handler.post_mark, "/plan": Handler.post_plan, "/job": Handler.post_job,
               "/pruefen": Handler.post_check, "/heute/skip": Handler.post_skip, "/manual-done": Handler.post_manual,
               "/complaint-filed": Handler.post_complaint}
SETUP_ROUTES = {"profil": Handler.setup_profile, "mail": Handler.setup_mail, "leaks": Handler.setup_leaks,
                "push": Handler.setup_push, "auto": Handler.setup_auto}


def make_server(home, host="127.0.0.1", port=8765, token=None):
    app = App(home, host, port, token)
    handler = type("BoundHandler", (Handler,), {"app": app})
    srv = ThreadingHTTPServer((host, port), handler)
    app.port = srv.server_address[1]
    return srv, app


def serve(home, host="127.0.0.1", port=8765, persistent_token=False, open_browser=False):
    token = None
    if persistent_token:
        token = K.get("web")
        if not token:
            token = secrets.token_urlsafe(24)
            K.put("web", token)
    srv, app = make_server(home, host, port, token)
    from . import qr
    print(f"Datenputz läuft. Diesen Link öffnen (er ist dein Schlüssel – nicht teilen):\n  {app.url}")
    if app.remote:
        print("\nAm Handy (im VPN) diesen Code scannen:\n" + qr.QR(app.url, "M").terminal())
    print("Beenden mit Strg+C.")
    if open_browser:
        import webbrowser
        webbrowser.open(app.url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
