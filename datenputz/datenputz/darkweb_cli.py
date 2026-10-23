"""Befehle für Dark-Web-Monitor, Passwort-Audit, Aliase und Geheimnisse."""
import getpass
import html
import sys
from email import message_from_bytes
from pathlib import Path

from . import aliases as AL
from . import breach as BR
from . import brokers as B
from . import engine as E
from . import inbox as I
from . import keystore as K
from . import mailer as M
from . import store as S
from . import vault as VA

SEV_ICON = {"kritisch": "✖", "hoch": "▲", "mittel": "●", "info": "ℹ"}


def _emails(st, extra=None):
    return sorted({e.lower() for p in st.profiles() for e in p.get("emails", [])}
                  | {e.lower() for e in st.config().get("monitor_emails", [])}
                  | {a["alias"] for a in st.aliases()}
                  | {e.lower() for e in (extra or [])})


def _key(a, st):
    if getattr(a, "key", None):
        if a.save_key:
            print(f"Schlüssel gespeichert in: {K.put('hibp', a.key, st)}")
        return a.key
    return K.get("hibp", st)


def _sources(a, st):
    if getattr(a, "max", False):
        return list(BR.SOURCES)
    if getattr(a, "sources", None):
        chosen = [x.strip() for x in a.sources.split(",") if x.strip()]
        unknown = set(chosen) - set(BR.SOURCES)
        if unknown:
            sys.exit(f"Unbekannte Quelle(n): {', '.join(unknown)}. Verfügbar: {', '.join(BR.SOURCES)}")
        return chosen
    return st.config().get("darkweb_sources") or ["hibp"]


def _consent(st, sources, assume_yes):
    """Vor der ersten Nutzung einer Drittquelle ausdrücklich zustimmen lassen."""
    cfg = st.config()
    given = set(cfg.get("darkweb_consent", []))
    for s in sources:
        if s in given:
            continue
        print(f"ℹ {BR.SOURCES[s][0]}: {BR.SOURCES[s][1]}")
        if not assume_yes and input("  Einverstanden? [j/N]: ").strip().lower() not in ("j", "ja", "y", "yes"):
            sys.exit("Abgebrochen.")
        given.add(s)
    cfg["darkweb_consent"] = sorted(given)
    st.save_config(cfg)


def print_findings(findings, show_actions=True):
    by_subject = {}
    for f in sorted(findings, key=lambda f: (BR.RANK[f["severity"]], f["subject"])):
        by_subject.setdefault(f["subject"], []).append(f)
    for subject, fs in by_subject.items():
        svc = next((f.get("alias_service") for f in fs if f.get("alias_service")), None)
        print(f"\n{subject}" + (f"  (Alias für {svc})" if svc else ""))
        for f in fs:
            print(f"  {SEV_ICON[f['severity']]} {f['severity']:<8} [{f['source']}] {BR.describe(f)}")
            if show_actions:
                for sev, text in f.get("actions", [])[:2]:
                    print(f"      → {text}")


def action_plan(findings):
    """Maßnahmen über alle Funde zusammenfassen, dringendste zuerst, ohne Doppelungen."""
    seen, plan = set(), []
    for f in sorted(findings, key=lambda f: BR.RANK[f["severity"]]):
        for sev, text in f.get("actions", []):
            if text not in seen:
                seen.add(text)
                plan.append((sev, text, f["subject"]))
    return sorted(plan, key=lambda x: BR.RANK[x[0]])


# ---------------------------------------------------------------------------
def breach_email(a, st):
    sources = _sources(a, st)
    key = _key(a, st)
    if "hibp" in sources and not key:
        print("ℹ Ohne HIBP-Schlüssel wird Have I Been Pwned übersprungen (haveibeenpwned.com/API/Key, dann "
              "`secret set hibp`). Kostenlose Quellen: --sources xposedornot,leakcheck,hudsonrock")
        sources = [s for s in sources if s != "hibp"]
    if not sources:
        sys.exit("Keine Quelle verfügbar.")
    _consent(st, [s for s in sources if s != "hibp"], a.yes)
    emails = _emails(st, a.email)
    if not emails:
        sys.exit("Keine Adressen. Profil anlegen (init), `--email` angeben oder `alias add` nutzen.")
    domains = st.config().get("monitor_domains", [])
    print(f"Prüfe {len(emails)} Adresse(n)" + (f" und {len(domains)} Domain(s)" if domains else "")
          + f" in: {', '.join(sources)} …")
    new, errors = BR.monitor(st, emails, sources, key=key, domains=domains,
                             log=lambda e: print(f"  ✓ {e}", flush=True))
    for e in errors:
        print(f"⚠ {e}")
    allf = st.findings()
    relevant = [f for f in allf if f["subject"] in emails or f["kind"].startswith("domain")
                or f["subject"].split("@")[-1] in domains]
    print_findings(new if a.new_only else relevant)
    counts = {s: sum(1 for f in relevant if f["severity"] == s) for s in BR.SEVERITIES}
    print(f"\nGesamt: {len(relevant)} Funde · " + " · ".join(f"{k} {v}" for k, v in counts.items() if v)
          + f" · davon neu: {len(new)}")
    if new and a.notify:
        _notify(st, new)
    if BR.manual_due(st):
        print("\nℹ Vierteljährliche Handprüfung fällig (HPI, Uni Bonn, Hudson Rock …): `breach manual`")


def _notify(st, new):
    cfg = st.config().get("smtp")
    if not cfg:
        print("(Keine Benachrichtigung: SMTP nicht eingerichtet)")
        return
    lines = []
    for f in sorted(new, key=lambda f: BR.RANK[f["severity"]]):
        lines.append(f"[{f['severity'].upper()}] {f['subject']}: {BR.describe(f)}")
        lines += [f"    → {t}" for _, t in f.get("actions", [])[:2]]
    body = ("Datenputz hat neue Funde zu deinen Adressen:\n\n" + "\n".join(lines) +
            "\n\nDiese Mail enthält keine Passwörter. Details: python -m datenputz breach list\n")
    worst = min((f["severity"] for f in new), key=BR.RANK.get)
    to = sorted({p for pr in st.profiles() for p in pr.get("emails", [])[:1]}) or [cfg["from"]]
    msg = M.build(cfg["from"], ", ".join(to), f"Datenputz: {len(new)} neue Funde (höchste Stufe: {worst})", body)
    m = M.SMTPMailer(cfg, delay=0)
    m.send(msg, "breach")
    m.close()
    print(f"Benachrichtigung an {', '.join(to)} gesendet.")


def breach_list(a, st):
    fs = st.findings()
    if a.severity:
        fs = [f for f in fs if BR.RANK[f["severity"]] <= BR.RANK[a.severity]]
    if not fs:
        print("Keine Funde gespeichert (breach email ausführen).")
        return
    print_findings(fs, show_actions=a.actions)


def breach_plan(a, st):
    plan = action_plan(st.findings())
    if not plan:
        print("Keine offenen Maßnahmen.")
    for i, (sev, text, subject) in enumerate(plan, 1):
        print(f"{i:>2}. {SEV_ICON[sev]} {sev:<8} {text}\n      ({subject})")


def breach_status(a, st):
    key = _key(a, st)
    if not key:
        sys.exit("Kein HIBP-Schlüssel hinterlegt (`secret set hibp`).")
    s = BR.subscription(key)
    print(f"Tarif: {s.get('SubscriptionName')} – {s.get('Description')}\nGültig bis: {s.get('SubscribedUntil')}"
          f"\nAnfragen/Minute: {s.get('Rpm')}\nMax. Domaingröße: {s.get('DomainSearchMaxBreachedAccounts') or 'unbegrenzt'}")


def breach_sources(a, st):
    cfg = st.config()
    active = cfg.get("darkweb_sources") or ["hibp"]
    if a.enable:
        add = [x.strip() for x in a.enable.split(",")]
        _consent(st, [x for x in add if x != "hibp"], a.yes)
        cfg = st.config()
        active = sorted(set(active) | set(add), key=list(BR.SOURCES).index)
    if a.disable:
        active = [x for x in active if x not in a.disable.split(",")]
    cfg["darkweb_sources"] = active
    st.save_config(cfg)
    for name, (label, note) in BR.SOURCES.items():
        print(f"{'✔' if name in active else ' '} {name:<12} {label}\n               {note}")


def breach_domain(a, st):
    cfg = st.config()
    doms = set(cfg.get("monitor_domains", []))
    doms |= {d.lower() for d in a.add or []}
    doms -= {d.lower() for d in a.remove or []}
    cfg["monitor_domains"] = sorted(doms)
    st.save_config(cfg)
    print("Überwachte Domains: " + (", ".join(sorted(doms)) or "keine"))
    print("Hinweis: Die Domain muss im HIBP-Dashboard bestätigt sein (DNS-TXT, Datei oder Mail an Domain-Postfach).")


def breach_manual(a, st):
    if a.done:
        st.set_kv("manual_checks_done", S.iso(S.now()))
        print("✔ Als erledigt vermerkt – nächste Erinnerung in 90 Tagen.")
        return
    last = st.get_kv("manual_checks_done")
    print(f"Zuletzt erledigt: {last[:10] if last else 'nie'}\nAdressen: {', '.join(_emails(st)) or '–'}\n")
    for name, url, note in BR.MANUAL_CHECKS:
        print(f"• {name}\n  {url}\n  {note}")
    print("\nDanach: python -m datenputz breach manual --done")


def breach_password(a, st):
    pw = sys.stdin.readline().rstrip("\n") if a.stdin else getpass.getpass("Passwort (wird nicht angezeigt): ")
    n = BR.password_count(pw)
    pw = None
    if n:
        print(f"✖ Dieses Passwort taucht {n:,} Mal in Datenlecks auf. Nicht mehr verwenden!".replace(",", "."))
    else:
        print("✔ Nicht in bekannten Leaks gefunden (nur die ersten 5 Hash-Zeichen wurden übertragen).")


def breach_vault(a, st):
    path = Path(a.file)
    try:
        entries = VA.load(path)
    except ValueError as e:
        sys.exit(str(e))
    print(f"{len(entries)} Einträge gelesen. Prüfe" + (" offline" if a.offline else
          " per k-Anonymität (nur 5 Hash-Zeichen je Passwort verlassen den Rechner)") + " …")
    breaches = [] if a.offline else _safe_all_breaches(st)
    results, summary = VA.audit(entries, breaches, offline=a.offline)
    for r in results:
        who = f"{r['name']}" + (f" ({r['user']})" if r["user"] else "")
        print(f"{SEV_ICON[r['severity']]} {r['severity']:<8} {who}")
        for sev, text in r["issues"]:
            print(f"      – {text}")
    print(f"\n{summary['total']} Konten · ✔ {summary['ok']} ohne Befund · ✖ kritisch {summary['kritisch']} · "
          f"▲ hoch {summary['hoch']} · ● mittel {summary['mittel']} · {summary['reused']} mehrfach genutzte Passwörter")
    if summary["without_totp"]:
        print(f"ℹ {summary['without_totp']} Konten ohne hinterlegten TOTP-Code – wo möglich Zwei-Faktor einschalten.")
    st.set_kv("vault_audit", {**{k: v for k, v in summary.items()}, "date": S.iso(S.now())})
    if a.output:
        Path(a.output).write_text(_vault_html(results, summary), encoding="utf-8")
        Path(a.output).chmod(0o600)
        print(f"Bericht (ohne Passwörter): {a.output}")
    if a.shred:
        VA.shred(path)
        print(f"🗑 Export überschrieben und gelöscht: {path}")
    else:
        print(f"⚠ Der Export enthält alle Passwörter im Klartext. Löschen: `breach vault {path} --shred` "
              "oder sicher von Hand entfernen.")


def _safe_all_breaches(st):
    try:
        return BR.all_breaches(st)
    except Exception as e:
        print(f"⚠ Leak-Verzeichnis nicht abrufbar ({e}) – Abgleich mit Dienst-Leaks entfällt.")
        return []


def _vault_html(results, summary):
    rows = "".join(
        f"<tr><td>{html.escape(r['severity'])}</td><td>{html.escape(r['name'])}</td><td>{html.escape(r['user'])}</td>"
        f"<td>{'<br>'.join(html.escape(t) for _, t in r['issues'])}</td></tr>" for r in results)
    return (f"<!doctype html><meta charset=utf-8><title>Passwort-Audit</title>"
            f"<style>body{{font:15px system-ui;margin:24px;background:#fff;color:#111}}td,th{{padding:6px 10px;"
            f"border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}</style>"
            f"<h1>Passwort-Audit</h1><p>{summary['total']} Konten, {summary['ok']} ohne Befund, "
            f"{summary['kritisch']} kritisch, {summary['hoch']} hoch.</p>"
            f"<table><tr><th>Stufe</th><th>Konto</th><th>Benutzer</th><th>Befund</th></tr>{rows}</table>")


# --- Aliase -------------------------------------------------------------------
def alias_add(a, st):
    st.add_alias(a.alias, a.service, a.related or [], a.note)
    print(f"✔ {a.alias.lower()} → {a.service}" + (f" (auch erlaubt: {', '.join(a.related)})" if a.related else ""))


def alias_list(a, st):
    found = st.findings()
    for x in st.aliases():
        n = sum(1 for f in found if f["subject"] == x["alias"])
        print(f"{x['alias']:<36} {x['service']:<24} {'⚠ ' + str(n) + ' Funde' if n else ''}")


def alias_remove(a, st):
    print("Entfernt." if st.remove_alias(a.alias) else "Unbekannter Alias.")


def alias_scan(a, st):
    if a.eml_dir:
        msgs = (message_from_bytes(p.read_bytes()) for p in sorted(Path(a.eml_dir).glob("*.eml")))
    else:
        cfg = st.config().get("imap")
        if not cfg:
            sys.exit("Kein IMAP konfiguriert: python -m datenputz smtp (oder --eml-dir)")
        msgs = I.fetch(cfg, days=a.days)
    new = AL.scan(st, msgs)
    print_findings(new) if new else print("✔ Keine Weitergabe entdeckt.")


def alias_request(a, st):
    al = next((x for x in st.aliases() if x["alias"] == a.alias.lower()), None)
    if not al:
        sys.exit("Unbekannter Alias.")
    profiles = [st.profile(a.profile)] if a.profile else st.profiles()
    if not profiles or not profiles[0]:
        sys.exit("Kein Profil (init).")
    b = B.make_custom("https://" + al["service"], name=al["service"], email=a.email)
    B.save_custom([x for x in B.load_custom() if x["id"] != b["id"]] + [b])
    # Nur den Alias nennen: Der Dienst soll deine Hauptadresse nicht zusätzlich erfahren.
    rid = E.Engine(st).add_custom(profiles[0], b, None, identity={"emails": [al["alias"]]})
    print(f"✔ Löschantrag #{rid} an {al['service']} angelegt (Kontakt: {a.email or 'Webformular'}). "
          f"Die Anfrage verlangt auch die Empfänger deiner Daten (Art. 15/19 DSGVO). Versand mit `run`.")


# --- Geheimnisse -------------------------------------------------------------------
def secret_set(a, st):
    value = getpass.getpass(f"{K.NAMES[a.name][1]} (wird nicht angezeigt): ")
    if not value:
        sys.exit("Leer – nichts gespeichert.")
    print(f"✔ Gespeichert in: {K.put(a.name, value, st)}")


def secret_list(a, st):
    print(f"Speicher: {K.backend() or 'kein Schlüsselbund gefunden – Fallback config.json (Rechte 600)'}")
    for name, label, where in K.status(st):
        print(f"  {name:<8} {label:<40} {where}")


def secret_delete(a, st):
    K.delete(a.name, st)
    print("Gelöscht.")


# ---------------------------------------------------------------------------
def register(sub):
    p = sub.add_parser("breach", help="Dark-Web-Monitor: Leaks, Pastes, Infostealer, Passwort-Audit")
    bs = p.add_subparsers(dest="sub", required=True)
    q = bs.add_parser("email", help="alle Adressen, Aliase und Domains in allen Quellen prüfen")
    q.add_argument("--email", nargs="*", help="zusätzliche Adressen")
    q.add_argument("--sources", help=",".join(BR.SOURCES))
    q.add_argument("--max", action="store_true", help="alle Quellen (maximale Recherche)")
    q.add_argument("--key"); q.add_argument("--save-key", action="store_true")
    q.add_argument("--notify", action="store_true", help="neue Funde per Mail melden")
    q.add_argument("--new-only", action="store_true", help="nur neue Funde anzeigen")
    q.add_argument("--yes", action="store_true", help="Zustimmung zu Drittquellen (für Cron)")
    q.set_defaults(func=breach_email)
    q = bs.add_parser("list", help="gespeicherte Funde"); q.add_argument("--severity", choices=BR.SEVERITIES)
    q.add_argument("--actions", action="store_true"); q.set_defaults(func=breach_list)
    bs.add_parser("plan", help="Maßnahmenplan aus allen Funden").set_defaults(func=breach_plan)
    q = bs.add_parser("sources", help="Quellen ein-/ausschalten")
    q.add_argument("--enable"); q.add_argument("--disable"); q.add_argument("--yes", action="store_true")
    q.set_defaults(func=breach_sources)
    q = bs.add_parser("domain", help="eigene Domains überwachen (HIBP)")
    q.add_argument("--add", nargs="*"); q.add_argument("--remove", nargs="*"); q.set_defaults(func=breach_domain)
    q = bs.add_parser("status", help="HIBP-Tarif anzeigen"); q.add_argument("--key"); q.set_defaults(func=breach_status, save_key=False)
    q = bs.add_parser("manual", help="Handprüfungen (HPI, Uni Bonn, …)"); q.add_argument("--done", action="store_true")
    q.set_defaults(func=breach_manual)
    q = bs.add_parser("password", help="ein Passwort prüfen (k-Anonymität)")
    q.add_argument("--stdin", action="store_true"); q.set_defaults(func=breach_password)
    q = bs.add_parser("vault", help="Passwortmanager-Export (CSV) prüfen")
    q.add_argument("file"); q.add_argument("--offline", action="store_true", help="ohne Netz: nur Wiederholung/Stärke")
    q.add_argument("--shred", action="store_true", help="Export danach überschreiben und löschen")
    q.add_argument("-o", "--output", help="HTML-Bericht ohne Passwörter"); q.set_defaults(func=breach_vault)

    p = sub.add_parser("alias", help="Alias-Verzeichnis: eine Adresse pro Dienst, Weitergaben erkennen")
    al = p.add_subparsers(dest="sub", required=True)
    q = al.add_parser("add", help="Alias einem Dienst zuordnen"); q.add_argument("alias"); q.add_argument("service")
    q.add_argument("--related", nargs="*", help="weitere erlaubte Absender-Domains"); q.add_argument("--note")
    q.set_defaults(func=alias_add)
    al.add_parser("list", help="Aliase anzeigen").set_defaults(func=alias_list)
    q = al.add_parser("remove"); q.add_argument("alias"); q.set_defaults(func=alias_remove)
    q = al.add_parser("scan", help="Postfach nach Weitergaben durchsuchen")
    q.add_argument("--days", type=int, default=90); q.add_argument("--eml-dir"); q.set_defaults(func=alias_scan)
    q = al.add_parser("request", help="Lösch-/Auskunftsantrag an den Dienst des Alias")
    q.add_argument("alias"); q.add_argument("--email", help="Datenschutz-Kontakt des Dienstes"); q.add_argument("--profile")
    q.set_defaults(func=alias_request)

    p = sub.add_parser("secret", help="API-Schlüssel und Passwörter im Schlüsselbund ablegen")
    ss = p.add_subparsers(dest="sub", required=True)
    q = ss.add_parser("set"); q.add_argument("name", choices=list(K.NAMES)); q.set_defaults(func=secret_set)
    ss.add_parser("list").set_defaults(func=secret_list)
    q = ss.add_parser("delete"); q.add_argument("name", choices=list(K.NAMES)); q.set_defaults(func=secret_delete)
