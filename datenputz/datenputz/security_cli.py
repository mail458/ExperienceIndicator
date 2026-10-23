"""Befehle für Bedrohungsschutz, Link-/Datei-Check, VPN, Verbindungs-Check und Passwörter."""
import secrets
import shutil
import string
import sys
from pathlib import Path

from . import breach as BR
from . import checker as C
from . import leakcheck as LC
from . import shield as SH
from . import vpn as V

ICON = {"ok": "✔", "warn": "⚠", "bad": "✖", "info": "ℹ",
        "unauffällig": "✔", "verdächtig": "⚠", "gefährlich": "✖"}


# --- Bedrohungsschutz -------------------------------------------------------
def shield_update(a, st):
    names = [x.strip() for x in a.only.split(",")] if a.only else None
    for n, c in SH.update(names).items():
        print(f"✔ {n:<12} {c:>9,} Domains  – {SH.SOURCES[n][0]}".replace(",", "."))
    print(f"Gesamt: {len(SH.Blocklist()):,} gesperrte Domains.".replace(",", "."))


def shield_serve(a, st):
    SH.serve(a.listen, a.port, a.upstream, a.verbose)


def shield_test(a, st):
    bl = SH.Blocklist()
    for d in a.domains:
        hit = bl.match(d)
        print(f"{'✖ blockiert' if hit else '✔ erlaubt  '}  {d}" + (f"  (Listeneintrag {hit})" if hit else ""))


def shield_export(a, st):
    text = SH.export(a.format, SH.Blocklist().deny)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"Geschrieben: {a.output}")
    else:
        sys.stdout.write(text)


def shield_custom(kind):
    def run(a, st):
        n = SH.add_custom(kind, a.domains)
        print(f"{'Erlaubt' if kind == 'allow' else 'Gesperrt'}: {', '.join(a.domains)} ({n} eigene Einträge)")
    return run


def shield_stats(a, st):
    import json
    p = SH.folder() / "stats.json"
    if not p.exists():
        sys.exit("Noch keine Statistik – zuerst shield serve laufen lassen.")
    s = json.loads(p.read_text())
    total = s["blocked"] + s["allowed"] or 1
    print(f"{s['blocked']} blockiert / {s['allowed']} erlaubt ({100 * s['blocked'] / total:.1f} % blockiert)")
    for d, n in list(s["top"].items())[:15]:
        print(f"  {n:>6}  {d}")


def clean_url(a, st):
    for u in a.urls:
        clean, removed = SH.clean_url(u)
        print(clean + (f"   (entfernt: {', '.join(removed)})" if removed else ""))


# --- Link-, Betrugs-, Dateiprüfung -------------------------------------------
def _print_check(r, title):
    print(f"{ICON[r['verdict']]} {r['verdict'].upper():<12} {title}")
    for why in r["reasons"]:
        print(f"    – {why}")


def link(a, st):
    bl = SH.Blocklist()
    if not len(bl):
        print("ℹ Ohne Sperrliste nur Merkmalsprüfung (Tipp: shield update).")
    for u in a.urls:
        r = C.check_url(u, bl)
        _print_check(r, u)
        if r["clean"]:
            print(f"    Ohne Tracking: {r['clean']}")


def scam(a, st):
    if a.file:
        text = Path(a.file).read_text(encoding="utf-8", errors="replace")
    elif a.text:
        text = " ".join(a.text)
    else:
        print("Nachricht einfügen, mit Strg+D abschließen:")
        text = sys.stdin.read()
    r = C.check_text(text)
    _print_check(r, "Nachricht")
    for x in r["links"]:
        _print_check(x, "  Link " + x["url"])
    if r["phones"]:
        print(f"    Telefonnummern: {', '.join(r['phones'])} – nur über offiziell bekannte Nummern zurückrufen")


def file_check(a, st):
    for f in a.paths:
        r = C.check_file(f, a.key)
        _print_check(r, f)
        print(f"    SHA-256 {r['sha256']}" + ("" if r["lookup"] else "  (Online-Abgleich: ABUSE_CH_AUTH_KEY setzen)"))


# --- VPN ---------------------------------------------------------------------
def _state():
    s = V.load()
    if not s:
        sys.exit("Noch kein VPN eingerichtet: vpn init --endpoint <server-ip-oder-name>")
    return s


def vpn_init(a, st):
    if V.load() and not a.force:
        sys.exit("VPN existiert schon (--force überschreibt alle Schlüssel).")
    s = V.init(a.endpoint, a.port, a.subnet, a.subnet6, dns=a.dns, shield=not a.no_shield)
    print(f"✔ Server {a.endpoint}:{a.port} angelegt (Schlüssel per {'wg' if shutil.which('wg') else 'Python-X25519'}).")
    print("Weiter: vpn add laptop  ·  vpn add handy  ·  vpn export")
    return s


def vpn_add(a, st):
    s = _state()
    mode = "mesh" if a.mesh else "split" if a.split else "full"
    p = V.add_peer(s, a.name, mode, a.split or [], killswitch=not a.no_killswitch)
    print(f"✔ Gerät {p['name']} ({mode}) → {p['address']}. Konfiguration: vpn show {p['name']}")


def vpn_list(a, st):
    s = _state()
    srv = s["server"]
    print(f"Server {srv['endpoint']}:{srv['port']}  Netz {srv['subnet']}  DNS {srv['dns']}"
          f"{'  (Bedrohungsschutz)' if srv.get('shield') else ''}")
    for p in s["peers"]:
        extra = f" ohne {', '.join(p['exclude'])}" if p["exclude"] else ""
        print(f"  {p['name']:<14} {p['address']:<12} {p['mode']}{extra}{'  Kill Switch' if p.get('killswitch') else ''}")


def vpn_show(a, st):
    s = _state()
    p = next((x for x in s["peers"] if x["name"] == a.name), None)
    if not p:
        sys.exit("Unbekanntes Gerät")
    print(V.client_conf(s, p))
    if shutil.which("qrencode"):
        print(f"QR-Code fürs Handy:  python -m datenputz vpn show {a.name} | qrencode -t ansiutf8")


def vpn_remove(a, st):
    print("Entfernt." if V.remove_peer(_state(), a.name) else "Unbekanntes Gerät.")


def vpn_export(a, st):
    files = V.export(_state(), Path(a.output) if a.output else None)
    for f in files:
        print(f"  {f}")
    print("Server: Ordner auf den Server kopieren und install-server.sh als root ausführen.\n"
          "Geräte: .conf in die WireGuard-App importieren (Handy: QR-Code).")


# --- Verbindungs-Check & Passwörter ------------------------------------------
def check(a, st):
    s = V.load()
    vpn_dns = [d.strip() for d in s["server"]["dns"].split(",")] if s else None
    for level, text in LC.run(expect_vpn=a.expect_vpn, vpn_dns=vpn_dns):
        print(f"{ICON[level]} {text}")


def password(a, st):
    alphabet = string.ascii_letters + string.digits + ("" if a.no_symbols else "!#$%&*+-=?@^_~")
    for _ in range(a.count):
        while True:
            pw = "".join(secrets.choice(alphabet) for _ in range(a.length))
            if (any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw)):
                break
        if a.check:
            n = BR.password_count(pw)
            print(pw + ("" if not n else f"   ✖ in {n} Leaks – verwerfen"))
        else:
            print(pw)


# -----------------------------------------------------------------------------
def register(sub):
    p = sub.add_parser("shield", help="Bedrohungsschutz: DNS-Filter gegen Werbung, Tracker, Malware, Phishing")
    ss = p.add_subparsers(dest="sub", required=True)
    q = ss.add_parser("update", help="Sperrlisten laden"); q.add_argument("--only", help=",".join(SH.SOURCES))
    q.set_defaults(func=shield_update)
    q = ss.add_parser("serve", help="lokalen DNS-Filter starten")
    q.add_argument("--listen", default="127.0.0.1"); q.add_argument("--port", type=int, default=5353)
    q.add_argument("--upstream", default=SH.DEFAULT_UPSTREAM, help="DoH-URL oder udp:IP[:Port]")
    q.add_argument("-v", "--verbose", action="store_true"); q.set_defaults(func=shield_serve)
    q = ss.add_parser("test", help="Domains prüfen"); q.add_argument("domains", nargs="+"); q.set_defaults(func=shield_test)
    q = ss.add_parser("export", help="Liste für hosts/Pi-hole/AdGuard/dnsmasq/Unbound")
    q.add_argument("--format", choices=["hosts", "domains", "dnsmasq", "unbound"], default="hosts")
    q.add_argument("-o", "--output"); q.set_defaults(func=shield_export)
    q = ss.add_parser("allow", help="Domain freigeben"); q.add_argument("domains", nargs="+")
    q.set_defaults(func=shield_custom("allow"))
    q = ss.add_parser("deny", help="Domain zusätzlich sperren"); q.add_argument("domains", nargs="+")
    q.set_defaults(func=shield_custom("deny"))
    ss.add_parser("stats", help="Statistik des DNS-Filters").set_defaults(func=shield_stats)
    p = sub.add_parser("clean-url", help="Tracking-Parameter aus Links entfernen")
    p.add_argument("urls", nargs="+"); p.set_defaults(func=clean_url)

    p = sub.add_parser("link", help="Link-Checker: ist ein Link gefährlich?")
    p.add_argument("urls", nargs="+"); p.set_defaults(func=link)
    p = sub.add_parser("scam", help="Scam-Checker: Nachricht auf Betrugsmerkmale prüfen")
    p.add_argument("text", nargs="*"); p.add_argument("--file"); p.set_defaults(func=scam)
    p = sub.add_parser("file", help="File-Checker: Datei auf Tarnung und bekannte Malware prüfen")
    p.add_argument("paths", nargs="+"); p.add_argument("--key", help="abuse.ch Auth-Key"); p.set_defaults(func=file_check)

    p = sub.add_parser("vpn", help="Eigenes WireGuard-VPN: Kill Switch, Split Tunneling, Meshnet")
    vs = p.add_subparsers(dest="sub", required=True)
    q = vs.add_parser("init", help="Server anlegen")
    q.add_argument("--endpoint", required=True, help="öffentliche IP oder Hostname des Servers")
    q.add_argument("--port", type=int, default=51820); q.add_argument("--subnet", default="10.66.0.0/24")
    q.add_argument("--subnet6", default="fd66:6d70::/64"); q.add_argument("--dns")
    q.add_argument("--no-shield", action="store_true", help="kein DNS-Filter auf dem Server")
    q.add_argument("--force", action="store_true"); q.set_defaults(func=vpn_init)
    q = vs.add_parser("add", help="Gerät hinzufügen"); q.add_argument("name")
    g = q.add_mutually_exclusive_group()
    g.add_argument("--mesh", action="store_true", help="nur Geräte untereinander (Meshnet)")
    g.add_argument("--split", nargs="+", metavar="NETZ", help="diese Netze am Tunnel vorbei (Split Tunneling)")
    q.add_argument("--no-killswitch", action="store_true"); q.set_defaults(func=vpn_add)
    vs.add_parser("list", help="Server und Geräte").set_defaults(func=vpn_list)
    q = vs.add_parser("show", help="Gerätekonfiguration anzeigen"); q.add_argument("name"); q.set_defaults(func=vpn_show)
    q = vs.add_parser("remove", help="Gerät entfernen"); q.add_argument("name"); q.set_defaults(func=vpn_remove)
    q = vs.add_parser("export", help="Konfigurationen und Installationsskript schreiben")
    q.add_argument("-o", "--output"); q.set_defaults(func=vpn_export)

    p = sub.add_parser("check", help="Verbindungs-Check: VPN aktiv? IP-, DNS-, IPv6-Lecks?")
    p.add_argument("--expect-vpn", action="store_true"); p.set_defaults(func=check)
    p = sub.add_parser("password", help="Starke Passwörter erzeugen")
    p.add_argument("--length", type=int, default=20); p.add_argument("--count", type=int, default=3)
    p.add_argument("--no-symbols", action="store_true")
    p.add_argument("--check", action="store_true", help="zusätzlich gegen Leaks prüfen"); p.set_defaults(func=password)
