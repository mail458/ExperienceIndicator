"""Kommandozeile: `python -m datenputz <befehl>`."""
import argparse
import json
import shutil
import sys
from email import message_from_bytes
from pathlib import Path

from . import brokers as B
from . import engine as E
from . import inbox as I
from . import mailer as M
from . import report as R
from . import store as S

STATUS_ALIASES = {
    "gesendet": S.SENT, "abgeschickt": S.SENT, "geloescht": S.CONFIRMED, "gelöscht": S.CONFIRMED,
    "keine-daten": S.NO_DATA, "gesperrt": S.SUPPRESSED, "abgelehnt": S.REJECTED,
    "unzustellbar": S.BOUNCED, "aktion": S.AWAITING_USER, "geplant": S.PENDING,
}


def ask(prompt, default=None, required=False):
    suffix = f" [{default}]" if default else ""
    while True:
        v = input(f"{prompt}{suffix}: ").strip()
        if v or not required:
            return v or default
        print("  Pflichtangabe.")


def split(v, sep=","):
    return [x.strip() for x in (v or "").split(sep) if x.strip()]


def yes(prompt):
    return input(f"{prompt} [j/N]: ").strip().lower() in ("j", "ja", "y", "yes")


# ---------------------------------------------------------------------------
def cmd_init(a, st):
    if a.from_json:
        data = json.loads(Path(a.from_json).read_text(encoding="utf-8"))
    else:
        print("Neues Profil. Es werden nur Angaben verschickt, die zur Identifikation nötig sind.\n")
        data = {
            "name": ask("Vollständiger Name", required=True),
            "aliases": split(ask("Weitere/frühere Namen, z. B. Geburtsname (kommagetrennt)")),
            "emails": split(ask("E-Mail-Adresse(n) (kommagetrennt)", required=True)),
            "addresses": [x.replace(" / ", "\n") for x in
                          split(ask("Aktuelle Anschrift (Zeilen mit ' / ' trennen)", required=True), ";")],
            "phones": split(ask("Telefonnummer(n) (optional)")),
            "birthdate": ask("Geburtsdatum TT.MM.JJJJ (optional, nur wenn ein Händler es verlangt)"),
            "country": (ask("Land (ISO-Code)", "de") or "de").lower(),
            "language": ask("Briefsprache (de/en)", "de"),
        }
        prev = ask("Frühere Anschriften (mehrere mit ';' trennen, optional)")
        data["addresses"] += [x.replace(" / ", "\n") for x in split(prev, ";")]
        data["include_public"] = data["country"] == "us" or yes("US-Personensuchseiten einbeziehen?")
        if a.on_behalf_by:
            data["on_behalf_of_by"] = a.on_behalf_by
    if data.get("on_behalf_of_by") and not (a.yes or yes(
            f"Liegt eine Vollmacht/Einwilligung von {data['name']} vor (bei Kindern: Sorgeberechtigung)?")):
        sys.exit("Abgebrochen: Anfragen für andere Personen nur mit deren Einwilligung.")
    data = {k: v for k, v in data.items() if v not in (None, "", [])}
    key = a.key or data["name"].split()[0].lower()
    st.add_profile(key, data)
    print(f"Profil '{key}' gespeichert. Weiter mit: python -m datenputz plan")


def cmd_profiles(a, st):
    for p in st.profiles():
        print(f"{p['_key']:<12} {p['name']:<30} {p.get('country', 'de')}  {', '.join(p.get('emails', []))}")


def cmd_smtp(a, st):
    cfg = st.config()
    sm = cfg.get("smtp", {})
    print("Tipp Gmail/Outlook: App-Passwort verwenden. Das Passwort wird nicht gespeichert –\n"
          "setze DATENPUTZ_SMTP_PASSWORD oder gib es beim Versand ein.\n")
    sm["host"] = ask("SMTP-Server", sm.get("host", "smtp.gmail.com"))
    sm["security"] = ask("Verschlüsselung (starttls/ssl)", sm.get("security", "starttls"))
    sm["port"] = int(ask("Port", str(sm.get("port", 587 if sm["security"] == "starttls" else 465))))
    sm["user"] = ask("Benutzername", sm.get("user"), required=True)
    sm["from"] = ask("Absender (From)", sm.get("from", sm["user"]))
    sm["delay_seconds"] = int(ask("Sekunden zwischen zwei Mails", str(sm.get("delay_seconds", 20))))
    cfg["smtp"] = sm
    cfg["daily_limit"] = int(ask("Maximal Mails pro Tag", str(cfg.get("daily_limit", E.DEFAULT_DAILY_LIMIT))))
    im = cfg.get("imap", {})
    im["host"] = ask("IMAP-Server (für Antworten)", im.get("host", sm["host"].replace("smtp", "imap")))
    im["port"] = int(ask("IMAP-Port", str(im.get("port", 993))))
    im["user"] = ask("IMAP-Benutzer", im.get("user", sm["user"]))
    cfg["imap"] = im
    st.save_config(cfg)
    print("Gespeichert.")


def cmd_brokers(a, st):
    items = B.select(a.country, categories=split(a.category) or None, search=a.search, include_public=a.public)
    if not a.count:
        for b in items:
            contact = b.get("email") or b.get("webform") or "(Brief)"
            print(f"{b['id']:<34} {b['name'][:44]:<44} {','.join(b['categories'])[:26]:<26} {contact}")
    print(f"\n{len(items)} Händler für Land '{a.country}'.")


def cmd_authorities(a, st):
    for x in B.authorities():
        if a.country in (x.get("relevant-countries") or []):
            print(f"{x['slug']:<16} {x['name']}")


def _profiles(st, key):
    ps = [st.profile(key)] if key else st.profiles()
    if not ps or ps[0] is None:
        sys.exit("Kein Profil gefunden. Zuerst: python -m datenputz init")
    return ps


def cmd_plan(a, st):
    eng = E.Engine(st)
    for p in _profiles(st, a.profile):
        n = eng.plan(p, categories=split(a.category) or None, search=a.search,
                     include_public=a.public or None, only=split(a.only) or None)
        print(f"{p['name']}: {n} neue Anfragen geplant.")


def cmd_run(a, st):
    if a.send:
        cfg = st.config().get("smtp")
        if not cfg:
            sys.exit("Kein SMTP konfiguriert: python -m datenputz smtp")
        due = len(st.requests(statuses=(S.PENDING,)))
        if not a.yes and not yes(f"Bis zu {due} geplante Anfragen (plus fällige Erinnerungen) jetzt per SMTP senden?"):
            return
        eng = E.Engine(st, M.SMTPMailer(cfg))
    elif a.outbox:
        eng = E.Engine(st, M.Outbox(st.dir / "outbox"))
    else:
        # Vorschau: auf einer Kopie arbeiten, echter Zustand bleibt unverändert
        pv = st.dir / "preview"
        shutil.rmtree(pv, ignore_errors=True)
        pv.mkdir()
        shutil.copy(st.dir / "datenputz.db", pv / "datenputz.db")
        if st.config_path.exists():
            shutil.copy(st.config_path, pv / "config.json")
        copy = S.Store(pv)
        stats = E.Engine(copy, M.Outbox(pv / "outbox")).run()
        copy.db.close()
        print(f"VORSCHAU (nichts verschickt): {stats}\nEntwürfe: {pv}/outbox, {pv}/forms, {pv}/complaints\n"
              "Wirklich senden: run --send   ·   Als .eml-Dateien zum Selbstversand: run --outbox")
        return
    stats = eng.run()
    print(f"Fertig: {stats['sent']} versendet, {stats['reminded']} Erinnerungen, {stats['escalated']} Beschwerdeentwürfe, "
          f"{stats['manual']} Formular/Brief, {stats['recurring']} neue Runden, {stats['deferred']} auf morgen verschoben.")
    if stats["manual"]:
        print("Formulare/Briefe: python -m datenputz forms")


def cmd_status(a, st):
    idx = B.by_id()
    items = R.rows(st, idx)
    if a.profile:
        items = [x for x in items if x["p"]["_key"] == a.profile]
    c, done = R.summary(items)
    print(f"{len(items)} Händler · erledigt {done} · " + " · ".join(f"{R.LABEL[k]} {v}" for k, v in c.items()))
    if a.all or a.filter:
        for x in items:
            r = x["r"]
            if a.filter and r["status"] != STATUS_ALIASES.get(a.filter, a.filter):
                continue
            print(f"#{r['id']:<5} {x['b']['name'][:40]:<40} {x['p']['_key']:<10} R{r['round']} {R.LABEL[r['status']]:<13} "
                  f"Frist {R._d(r['due_at']) if r['status'] in S.OPEN else '-'}")


def cmd_show(a, st):
    r = st.request(a.id)
    if not r:
        sys.exit("Unbekannte ID")
    b = B.by_id().get(r["broker_id"], {})
    print(json.dumps({k: r[k] for k in r.keys()}, indent=1, ensure_ascii=False))
    print("Händler:", b.get("name"), b.get("email") or b.get("webform"))
    for c in b.get("comments", []):
        print("  Hinweis:", c)
    for e in st.events(a.id):
        print(f"  {e['ts']}  {e['type']:<14} {e['detail'] or ''}")


def cmd_mark(a, st):
    status = STATUS_ALIASES.get(a.status, a.status)
    if status not in S.ALL_STATUSES:
        sys.exit(f"Unbekannter Status. Erlaubt: {', '.join(S.ALL_STATUSES + tuple(STATUS_ALIASES))}")
    eng = E.Engine(st)
    for rid in a.ids:
        try:
            eng.mark(rid, status, a.note)
        except KeyError:
            print(f"#{rid}: unbekannte ID")
            continue
        print(f"#{rid} → {R.LABEL[status]}")


def cmd_forms(a, st):
    idx = B.by_id()
    rs = st.requests(statuses=(S.AWAITING_USER,))
    if not rs:
        print("Keine offenen manuellen Schritte.")
    for r in rs:
        b = idx.get(r["broker_id"], {})
        where = b.get("webform") or b.get("address", "").replace("\n", ", ") or b.get("web")
        print(f"#{r['id']:<5} {b.get('name', r['broker_id'])[:40]:<40} {r['channel']:<8} {where}\n       Text: {r['note']}")
    if rs:
        print("\nNach dem Absenden: python -m datenputz mark <ID> gesendet")


def cmd_custom(a, st):
    p = _profiles(st, a.profile)[0]
    b = B.make_custom(a.urls[0], name=a.name, email=a.email)
    customs = [x for x in B.load_custom() if x["id"] != b["id"]] + [b]
    B.save_custom(customs)
    rid = E.Engine(st).add_custom(p, b, a.urls)
    print(f"Eigene Löschanfrage #{rid} für {b['name']} angelegt ({'E-Mail' if b['email'] else 'Formular'}). "
          "Wird beim nächsten `run` verarbeitet.")


def cmd_inbox(a, st):
    eng = E.Engine(st)
    if a.eml_dir:
        msgs = (message_from_bytes(p.read_bytes()) for p in sorted(Path(a.eml_dir).glob("*.eml")))
    else:
        cfg = st.config().get("imap")
        if not cfg:
            sys.exit("Kein IMAP konfiguriert: python -m datenputz smtp")
        msgs = I.fetch(cfg, days=a.days)
    found = I.process(st, eng, msgs, apply=a.apply)
    for f in found:
        print(f"#{f['request']:<5} {f['broker']:<30} {(f['verdict'] or 'unklar'):<14} {f['subject'][:60]}")
    print(f"{len(found)} Antworten zugeordnet." + ("" if a.apply else " Mit --apply übernehmen."))


def cmd_report(a, st):
    out = Path(a.output or st.dir / "report.html")
    out.write_text(R.render(st, B.by_id()), encoding="utf-8")
    print(f"Übersicht: {out}")


# ---------------------------------------------------------------------------
def parser():
    ap = argparse.ArgumentParser(prog="datenputz", description="Persönliche Daten bei Datenhändlern löschen lassen.")
    ap.add_argument("--home", help="Datenverzeichnis (Standard: ~/.datenputz oder $DATENPUTZ_HOME)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Profil anlegen (auch für Familienmitglieder)")
    p.add_argument("--key"); p.add_argument("--from-json"); p.add_argument("--on-behalf-by", help="Dein Name, wenn du für eine andere Person handelst")
    p.add_argument("--yes", action="store_true")
    sub.add_parser("profiles", help="Profile anzeigen")
    sub.add_parser("smtp", help="Mailversand und Postfach einrichten")

    p = sub.add_parser("brokers", help="Händlerverzeichnis durchsuchen")
    p.add_argument("--country", default="de"); p.add_argument("--category"); p.add_argument("--search")
    p.add_argument("--public", action="store_true", help="US-Personensuchseiten einbeziehen"); p.add_argument("--count", action="store_true")
    p = sub.add_parser("authorities", help="Datenschutzbehörden auflisten")
    p.add_argument("--country", default="de")

    p = sub.add_parser("plan", help="Anfragen an alle passenden Händler vorbereiten")
    p.add_argument("--profile"); p.add_argument("--category"); p.add_argument("--search"); p.add_argument("--only")
    p.add_argument("--public", action="store_true")

    p = sub.add_parser("run", help="Fällige Schritte ausführen (Standard: Vorschau)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--send", action="store_true", help="per SMTP versenden")
    g.add_argument("--outbox", action="store_true", help="als .eml speichern und als versendet zählen")
    p.add_argument("--yes", action="store_true")

    p = sub.add_parser("status", help="Fortschritt anzeigen")
    p.add_argument("--profile"); p.add_argument("--all", action="store_true"); p.add_argument("--filter")
    p = sub.add_parser("show", help="Details einer Anfrage"); p.add_argument("id", type=int)
    p = sub.add_parser("mark", help="Status manuell setzen")
    p.add_argument("status"); p.add_argument("ids", type=int, nargs="+"); p.add_argument("--note")
    sub.add_parser("forms", help="Offene Webformulare und Briefe")
    p = sub.add_parser("custom", help="Eigene Löschanfrage für beliebige Website")
    p.add_argument("urls", nargs="+"); p.add_argument("--name"); p.add_argument("--email"); p.add_argument("--profile")
    p = sub.add_parser("inbox", help="Antworten im Postfach auswerten")
    p.add_argument("--days", type=int, default=60); p.add_argument("--apply", action="store_true")
    p.add_argument("--eml-dir", help="statt IMAP: Ordner mit gespeicherten .eml-Dateien")
    p = sub.add_parser("report", help="HTML-Übersicht erzeugen"); p.add_argument("-o", "--output")
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    if a.home:
        import os
        os.environ["DATENPUTZ_HOME"] = a.home
    st = S.Store()
    globals()["cmd_" + a.cmd](a, st)


if __name__ == "__main__":
    main()
