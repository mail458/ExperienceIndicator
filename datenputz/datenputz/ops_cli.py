"""Befehle für Betrieb: Selbsttest, täglicher Lauf, Zeitsteuerung, Benachrichtigung, Web-Oberfläche."""
import ipaddress
import re
import sys

from . import daily as D
from . import doctor
from . import keystore as K
from . import notify as N
from . import schedule as SC
from . import vpn as V
from . import web


def cmd_doctor(a, st):
    results = doctor.run(st, online=not a.offline, login=not a.no_login)
    width = max(len(n) for _, n, _ in results)
    for level, name, text in results:
        print(f"{doctor.ICON[level]} {name:<{width}}  {text}")
    bad = sum(1 for r in results if r[0] == doctor.BAD)
    warn = sum(1 for r in results if r[0] == doctor.WARN)
    print(f"\n{'✔ Alles in Ordnung.' if not bad and not warn else f'{bad} Fehler, {warn} Hinweise.'}")
    if a.notify_test:
        for ch, err in N.send(st, "Datenputz: Testnachricht", "Benachrichtigungen funktionieren.", "info"):
            print(f"{'✔' if not err else '✖'} Test über {ch}" + (f": {err}" if err else ""))
    if bad:
        sys.exit(1)


def cmd_daily(a, st):
    steps, _ = D.run(st, send=not a.no_send, log=print)
    if any(s[1] == D.BAD for s in steps):
        sys.exit(1)


def cmd_schedule(a, st):
    if a.action == "install":
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", a.time):
            sys.exit("Uhrzeit bitte als HH:MM, z. B. 07:43")
        kind, text = SC.install(st, a.time, a.kind, dry_run=a.dry_run)
        print(text)
        if not a.dry_run:
            missing = [n for n in ("smtp",) if st.config().get("smtp") and not K.get(n, st)]
            if missing:
                print("⚠ Ohne hinterlegtes SMTP-Passwort kann der Lauf nichts senden: `secret set smtp`")
    elif a.action == "remove":
        print(f"Zeitsteuerung entfernt ({SC.remove(st)}).")
    else:
        s = st.get_kv("schedule")
        print(f"{s['kind']}, täglich {s['time']}" if s else "Nicht eingerichtet.")


def cmd_notify(a, st):
    if a.action == "setup":
        if a.channel == "ntfy":
            topic = a.topic or N.new_ntfy_topic()
            N.add_channel(st, {"type": "ntfy", "server": a.server or "https://ntfy.sh", "topic": topic})
            print(f"✔ ntfy eingerichtet. In der ntfy-App abonnieren:\n  Server: {a.server or 'https://ntfy.sh'}\n"
                  f"  Thema:  {topic}\nDer Themenname ist geheim zu halten – wer ihn kennt, kann mitlesen.")
        elif a.channel == "gotify":
            if not a.server:
                sys.exit("--server https://gotify.example.org angeben")
            N.add_channel(st, {"type": "gotify", "server": a.server})
            print("✔ Gotify eingerichtet. Token hinterlegen: `secret set gotify`")
        elif a.channel == "telegram":
            if not a.chat_id:
                sys.exit("--chat-id angeben (von @userinfobot)")
            N.add_channel(st, {"type": "telegram", "chat_id": a.chat_id})
            print("✔ Telegram eingerichtet. Bot-Token hinterlegen: `secret set telegram`")
        elif a.channel == "email":
            N.add_channel(st, {"type": "email", "to": a.to})
            print("✔ Mail-Benachrichtigung eingerichtet (über deinen SMTP-Zugang).")
        if a.full:
            cfg = st.config()
            cfg.setdefault("notify", {})["detail"] = "full"
            st.save_config(cfg)
            print("ℹ Meldungen enthalten jetzt Details (Adressen, Dienste) – nur mit eigenem Server empfehlenswert.")
    elif a.action == "remove":
        N.remove_channel(st, a.channel)
        print("Entfernt.")
    elif a.action == "test":
        res = N.send(st, "Datenputz: Testnachricht", "Benachrichtigungen funktionieren.", "info")
        if not res:
            print("Kein Kanal eingerichtet: `notify setup ntfy`")
        for ch, err in res:
            print(f"{'✔' if not err else '✖'} {ch}" + (f": {err}" if err else ""))
    else:
        chans = N.channels(st)
        print(", ".join(c["type"] for c in chans) or "Kein Kanal eingerichtet.",
              f"· Detailstufe: {N.detail(st)}")


def cmd_web(a, st):
    host = a.listen
    if host == "vpn":
        s = V.load()
        if not s:
            sys.exit("Kein VPN eingerichtet (`vpn init`).")
        host = s["server"]["address"]
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        sys.exit("--listen braucht eine IP-Adresse (oder „vpn“).")
    if not ip.is_loopback and not a.allow_remote:
        sys.exit("Aus Sicherheitsgründen nur lokal oder im VPN. Für andere Adressen bewusst --allow-remote setzen.")
    if not ip.is_loopback:
        print("⚠ Die Oberfläche ist über das Netz erreichbar – nur über das VPN nutzen (kein HTTPS).")
    web.serve(st.dir, host, a.port, persistent_token=a.keep_link, open_browser=a.open)


def register(sub):
    p = sub.add_parser("doctor", help="Selbsttest: Einrichtung, Zugänge und Online-Dienste prüfen")
    p.add_argument("--offline", action="store_true"); p.add_argument("--no-login", action="store_true",
                                                                     help="SMTP/IMAP-Anmeldung nicht testen")
    p.add_argument("--notify-test", action="store_true"); p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("daily", help="Täglicher Automatiklauf (für die Zeitsteuerung)")
    p.add_argument("--no-send", action="store_true"); p.set_defaults(func=cmd_daily)
    p = sub.add_parser("schedule", help="Täglichen Lauf im System einrichten")
    p.add_argument("action", choices=["install", "remove", "status"])
    p.add_argument("--time", default="07:43", help="HH:MM"); p.add_argument("--kind", choices=["systemd", "launchd", "schtasks"])
    p.add_argument("--dry-run", action="store_true", help="nur anzeigen"); p.set_defaults(func=cmd_schedule)
    p = sub.add_parser("notify", help="Benachrichtigungen aufs Handy (ntfy, Gotify, Telegram, Mail)")
    p.add_argument("action", choices=["setup", "remove", "test", "status"])
    p.add_argument("channel", nargs="?", choices=list(N.SENDERS), default="ntfy")
    p.add_argument("--server"); p.add_argument("--topic"); p.add_argument("--chat-id"); p.add_argument("--to")
    p.add_argument("--full", action="store_true", help="Details in Meldungen (Standard: nur Anzahlen)")
    p.set_defaults(func=cmd_notify)
    p = sub.add_parser("web", help="Web-Oberfläche starten")
    p.add_argument("--listen", default="127.0.0.1", help="IP-Adresse oder „vpn“ (Adresse des VPN-Servers)")
    p.add_argument("--port", type=int, default=8765); p.add_argument("--open", action="store_true", help="Browser öffnen")
    p.add_argument("--allow-remote", action="store_true")
    p.add_argument("--keep-link", action="store_true", help="festen Zugangslink aus dem Schlüsselbund nutzen (`secret set web`)")
    p.set_defaults(func=cmd_web)
