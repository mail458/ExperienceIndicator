"""Dark-Web-Monitor: Datenlecks, Pastes und Infostealer-Funde aus mehreren Quellen.

Quellen (jede einzeln zuschaltbar, keine lädt Leak-Daten selbst herunter):

* Have I Been Pwned – Leaks, Pastes, Stealer Logs, eigene Domains (API-Schlüssel)
* XposedOrNot – offene Leak-Datenbank, ohne Schlüssel
* LeakCheck (Public API) – Leak-Quellen und Datenarten, ohne Schlüssel
* Hudson Rock Cavalier – Infostealer-Infektionen (inoffizielle freie Schnittstelle)
* Passwörter: Pwned Passwords mit k-Anonymität (nur 5 Hash-Zeichen verlassen den Rechner)

Alles Gefundene wird bewertet (kritisch/hoch/mittel/info) und mit konkreten
Maßnahmen versehen. Gespeichert werden nur Metadaten, niemals Passwörter.
"""
import hashlib
import json
import time
import urllib.parse
from datetime import timedelta

from . import net
from . import store as S

PWNED_RANGE = "https://api.pwnedpasswords.com/range/"
HIBP = "https://haveibeenpwned.com/api/v3/"
HIBP_ACCOUNT = HIBP + "breachedaccount/"
SEVERITIES = ("kritisch", "hoch", "mittel", "info")
RANK = {s: i for i, s in enumerate(SEVERITIES)}

SOURCES = {
    "hibp": ("Have I Been Pwned – Leaks, Pastes, Stealer Logs",
             "Adresse geht an Have I Been Pwned (Troy Hunt, Australien). API-Schlüssel nötig."),
    "xposedornot": ("XposedOrNot – offene Leak-Datenbank",
                    "Adresse geht an XposedOrNot (Open Source). Ohne Schlüssel, max. 100 Abfragen/Tag."),
    "leakcheck": ("LeakCheck – Leak-Quellen und Datenarten",
                  "Adresse geht an LeakCheck.io. Ohne Schlüssel, zeigt nur Quellen, nie Daten."),
    "hudsonrock": ("Hudson Rock – Infostealer-Infektionen",
                   "Adresse geht an Hudson Rock (Israel). Inoffizielle freie Schnittstelle, ohne Gewähr."),
}

MANUAL_CHECKS = [
    ("HPI Identity Leak Checker", "https://sec.hpi.de/ilc/", "Ergebnis kommt per Mail an die geprüfte Adresse"),
    ("Leak Checker der Universität Bonn", "https://leakchecker.uni-bonn.de/", "Ergebnis kommt per Mail"),
    ("Hudson Rock – Infostealer-Suche", "https://www.hudsonrock.com/free-tools", "auch Benutzernamen prüfen"),
    ("Mozilla Monitor", "https://monitor.mozilla.org/", "dauerhafte Überwachung per Mail"),
    ("Google „Ergebnisse über dich“", "https://myactivity.google.com/results-about-you",
     "Telefonnummer/Adresse in Suchergebnissen finden und entfernen lassen"),
]
MANUAL_INTERVAL_DAYS = 90


class KeyInvalid(SystemExit):
    pass


class NotEntitled(Exception):
    """Der HIBP-Tarif enthält diese Abfrage nicht (z. B. Stealer Logs)."""


# --------------------------------------------------------------------------
# Bewertung und Maßnahmen
STEALER_ACTION = ("kritisch", "Ein Gerät war mit Schadsoftware (Infostealer) infiziert: Gerät bereinigen bzw. neu "
                  "aufsetzen, DANACH von einem sauberen Gerät aus alle Passwörter ändern, alle Sitzungen abmelden "
                  "(„überall abmelden“), Zwei-Faktor-Anmeldung neu einrichten, Krypto-Wallets umziehen.")
DATA_ACTIONS = [
    (("credit card", "bank account", "iban", "payment", "kreditkart", "bankverbindung", "kontonummer",
      "kontoverbindung"), "kritisch",
     "Bank bzw. Kartenanbieter informieren, Karte sperren lassen (Sperr-Notruf 116 116), Umsätze prüfen."),
    (("government issued", "passport", "social security", "national id", "tax", "driver", "ausweis", "reisepass",
      "steuer", "führerschein"), "kritisch",
     "Ausweisdaten betroffen: SCHUFA-Selbstauskunft und Konten prüfen, bei Missbrauch Anzeige erstatten."),
    (("passw", "kennw", "auth token", "security token"), "hoch",
     "Passwort bei {site} und überall, wo es ebenfalls genutzt wurde, ändern; Zwei-Faktor-Anmeldung aktivieren."),
    (("security questions", "sicherheitsfrage"), "hoch",
     "Sicherheitsfragen bei allen Diensten ändern (Antworten als Zufallswert im Passwortmanager)."),
    (("phone", "telefon", "handy"), "mittel",
     "Mit Betrugs-SMS und -Anrufen rechnen; beim Mobilfunkanbieter ein Kundenkennwort gegen SIM-Tausch setzen."),
    (("physical address", "anschrift", "postadresse", "wohnadresse"), "mittel",
     "Adresse im Umlauf: Datenputz-Löschanträge laufen lassen, mit gefälschten Briefen/Rechnungen rechnen."),
    (("date of birth", "dates of birth", "geburtsdatum", "geburtstag"), "mittel",
     "Geburtsdatum nie als Sicherheitsmerkmal nutzen; SCHUFA-Selbstauskunft prüfen."),
]
DEFAULT_ACTION = ("info", "Phishing-Mails, die sich auf {site} berufen, besonders misstrauisch prüfen.")


def assess(classes, site, flags=None):
    """(Schweregrad, [(schwere, maßnahme), …]) aus den betroffenen Datenarten."""
    flags = flags or {}
    if flags.get("IsStealerLog") or flags.get("IsMalware"):
        return "kritisch", [STEALER_ACTION]
    low = [c.lower() for c in classes]
    actions = []
    for words, sev, text in DATA_ACTIONS:
        if any(w in c for c in low for w in words):
            actions.append((sev, text.format(site=site)))
    if not actions:
        actions.append((DEFAULT_ACTION[0], DEFAULT_ACTION[1].format(site=site)))
    sev = min((a[0] for a in actions), key=RANK.get)
    if flags.get("IsSpamList") or flags.get("IsFabricated"):
        sev = "info"  # Spam-Liste bzw. vermutlich gefälscht: echte Adresse, aber kein Einbruch
    return sev, actions


# --------------------------------------------------------------------------
# Have I Been Pwned
_throttle = {"interval": 0.0, "last": 0.0}


def set_rate(rpm):
    """Mindestabstand zwischen HIBP-Abfragen aus dem Tarif (Anfragen pro Minute)."""
    _throttle["interval"] = 60 / rpm + 0.1 if rpm else 0.0


def hibp_get(path, key, retries=3):
    """GET auf die HIBP-API; None bei 404. Wartet bei 429 so lange wie `Retry-After` verlangt."""
    headers = {"hibp-api-key": key} if key else {}
    for attempt in range(retries):
        if key:
            wait = _throttle["interval"] - (time.monotonic() - _throttle["last"])
            if wait > 0:
                time.sleep(wait)
            _throttle["last"] = time.monotonic()
        try:
            status, body = net.fetch(HIBP + path, headers=headers)
        except net.HTTPError as e:
            if e.status == 429 and attempt < retries - 1:
                time.sleep(e.retry_after())
                continue
            if e.status == 401:
                raise KeyInvalid("HIBP: API-Schlüssel ungültig oder abgelaufen.") from None
            if e.status == 403:
                raise NotEntitled(path.split("/")[0]) from None
            raise
        return None if status == 404 else json.loads(body)
    return None


def subscription(key):
    return hibp_get("subscription/status", key) or {}


def account_breaches(email, api_key):
    return hibp_get("breachedaccount/" + urllib.parse.quote(email) + "?truncateResponse=false", api_key) or []


def all_breaches(store):
    """Alle bekannten Leaks (frei, ohne Schlüssel), einen Tag zwischengespeichert."""
    cache = store.dir / "hibp_breaches.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return json.loads(cache.read_text(encoding="utf-8"))
    data = hibp_get("breaches", None) or []
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


def _breach_finding(email, b, source="hibp"):
    site = b.get("Domain") or b.get("Title") or b.get("Name")
    sev, actions = assess(b.get("DataClasses", []), site, b)
    return {"kind": "stealer" if b.get("IsStealerLog") else "breach", "subject": email, "key": b["Name"],
            "source": source, "severity": sev, "title": b.get("Title", b["Name"]), "domain": b.get("Domain"),
            "date": b.get("BreachDate"), "classes": b.get("DataClasses", []), "actions": actions,
            "flags": [k for k in ("IsVerified", "IsFabricated", "IsSensitive", "IsSpamList", "IsMalware",
                                  "IsStealerLog") if b.get(k)],
            "count": b.get("PwnCount")}


def hibp_sources(email, key, state):
    out = [_breach_finding(email, b) for b in account_breaches(email, key)]
    for p in hibp_get("pasteaccount/" + urllib.parse.quote(email), key) or []:
        out.append({"kind": "paste", "subject": email, "key": f"{p.get('Source')}:{p.get('Id')}", "source": "hibp",
                    "severity": "hoch", "title": p.get("Title") or f"Paste auf {p.get('Source')}",
                    "date": (p.get("Date") or "")[:10] or None, "classes": ["Email addresses"],
                    "actions": [("hoch", "Adresse wurde öffentlich gepostet, oft zusammen mit Passwörtern: Passwörter "
                                         "ändern, gezieltes Phishing erwarten.")],
                    "count": p.get("EmailCount")})
    if not state.get("no_stealer"):
        try:
            for site in hibp_get("stealerlogsbyemail/" + urllib.parse.quote(email), key) or []:
                out.append({"kind": "stealer", "subject": email, "key": site, "source": "hibp", "severity": "kritisch",
                            "title": f"Zugangsdaten für {site} in Stealer Logs", "domain": site, "date": None,
                            "classes": ["Email addresses", "Passwords"], "actions": [STEALER_ACTION]})
        except NotEntitled:
            state["no_stealer"] = True
    return out


def hibp_domain(domain, key, state):
    out = []
    for alias, names in (hibp_get("breacheddomain/" + domain, key) or {}).items():
        for n in names:
            out.append({"kind": "domain_breach", "subject": f"{alias}@{domain}", "key": n, "source": "hibp",
                        "severity": "mittel", "title": n, "date": None, "classes": [],
                        "actions": [("mittel", f"{alias}@{domain} steckt im Leak {n}: Details mit "
                                               f"`breach email --email {alias}@{domain}` abrufen.")]})
    if not state.get("no_stealer"):
        try:
            for alias, sites in (hibp_get("stealerlogsbyemaildomain/" + domain, key) or {}).items():
                for site in sites:
                    out.append({"kind": "stealer", "subject": f"{alias}@{domain}", "key": site, "source": "hibp",
                                "severity": "kritisch", "title": f"Zugangsdaten für {site} in Stealer Logs",
                                "domain": site, "date": None, "classes": ["Passwords"], "actions": [STEALER_ACTION]})
        except NotEntitled:
            state["no_stealer"] = True
    return out


# --------------------------------------------------------------------------
# Weitere Quellen
def xposedornot(email):
    status, body = net.fetch("https://api.xposedornot.com/v1/check-email/" + urllib.parse.quote(email))
    if status == 404:
        return []
    data = json.loads(body)
    names = [n for group in data.get("breaches") or [] for n in (group if isinstance(group, list) else [group])]
    return [{"kind": "breach", "subject": email, "key": n, "source": "xposedornot", "severity": "mittel",
             "title": n, "date": None, "classes": [],
             "actions": [("mittel", f"Leak „{n}“: betroffenes Konto suchen, Passwort ändern, 2FA aktivieren.")]}
            for n in names if n]


def leakcheck(email):
    status, body = net.fetch("https://leakcheck.io/api/public?check=" + urllib.parse.quote(email))
    if status == 404:
        return []
    data = json.loads(body)
    if not data.get("success"):
        return []
    fields = data.get("fields") or []
    out = []
    for src in data.get("sources") or []:
        name = src.get("name") or "unbekannt"
        sev, actions = assess(fields, name)
        out.append({"kind": "breach", "subject": email, "key": name, "source": "leakcheck", "severity": sev,
                    "title": name, "date": src.get("date"), "classes": fields, "actions": actions})
    return out


def hudsonrock(email):
    url = "https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email=" + urllib.parse.quote(email)
    status, body = net.fetch(url)
    if status == 404:
        return []
    data = json.loads(body)
    out = []
    for i, st in enumerate(data.get("stealers") or [], 1):
        date = (st.get("date_compromised") or "")[:10] or None
        out.append({"kind": "infostealer", "subject": email, "key": f"{date or 'unbekannt'}#{i}",
                    "source": "hudsonrock", "severity": "kritisch",
                    "title": f"Infostealer-Infektion ({st.get('operating_system') or 'unbekanntes System'})",
                    "date": date, "classes": ["Passwords", "Browser cookies"], "actions": [STEALER_ACTION],
                    "details": {k: st.get(k) for k in ("operating_system", "malware_path", "antiviruses")
                                if st.get(k)}})
    return out


EXTRA = {"xposedornot": (xposedornot, 1.0), "leakcheck": (leakcheck, 1.0), "hudsonrock": (hudsonrock, 1.0)}


# --------------------------------------------------------------------------
def annotate_alias(f, aliases):
    """Fund bei einem Dienst-Alias: Wer hat die Adresse verloren oder weitergegeben?"""
    a = aliases.get(f["subject"])
    if not a:
        return f
    f["alias_service"] = a["service"]
    leak_site = (f.get("domain") or "").lower()
    own = {a["service"], *a["related"]}
    if leak_site and not any(leak_site == d or leak_site.endswith("." + d) for d in own):
        f.setdefault("actions", []).insert(0, (
            "hoch", f"Diese Adresse hast du nur {a['service']} gegeben, sie steckt aber im Leak von {leak_site}: "
                    f"{a['service']} hat sie weitergegeben oder verloren. Löschantrag: `alias request {f['subject']}`"))
        if RANK[f["severity"]] > RANK["hoch"]:
            f["severity"] = "hoch"
    return f


def monitor(store, emails, sources=("hibp",), key=None, domains=(), pause=None, log=None):
    """Alle Adressen in allen gewählten Quellen prüfen. Gibt (neue_funde, fehler) zurück."""
    log = log or (lambda *_: None)
    aliases = {a["alias"]: a for a in store.aliases()}
    new, errors, state = [], [], {}
    if "hibp" in sources and key:
        set_rate(0 if pause == 0 else (subscription(key).get("Rpm") or 10))
    for email in emails:
        for src in sources:
            try:
                if src == "hibp":
                    if not key:
                        continue
                    found = hibp_sources(email, key, state)
                else:
                    fn, wait = EXTRA[src]
                    time.sleep(wait if pause is None else pause)
                    found = fn(email)
            except KeyInvalid:
                raise
            except Exception as e:  # eine ausgefallene Quelle stoppt die anderen nicht
                errors.append(f"{src} für {email}: {e}")
                continue
            for f in found:
                f = annotate_alias(f, aliases)
                if store.add_finding(f):
                    new.append(f)
        log(email)
    if "hibp" in sources and key:
        for d in domains:
            try:
                for f in hibp_domain(d, key, state):
                    if store.add_finding(annotate_alias(f, aliases)):
                        new.append(f)
            except NotEntitled:
                errors.append(f"hibp Domain {d}: Domain nicht in HIBP bestätigt oder Tarif zu klein")
            except Exception as e:
                errors.append(f"hibp Domain {d}: {e}")
    if state.get("no_stealer"):
        errors.append("hibp: Stealer Logs sind in deinem Tarif nicht enthalten (übersprungen)")
    store.set_kv("breach_last_check", S.iso(S.now()))
    return new, errors


def manual_due(store):
    last = S.parse(store.get_kv("manual_checks_done"))
    return not last or S.now() - last > timedelta(days=MANUAL_INTERVAL_DAYS)


# --------------------------------------------------------------------------
def password_count(password):
    """Wie oft kommt das Passwort in bekannten Leaks vor? 0 = nicht gefunden."""
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    return range_counts(sha1[:5]).get(sha1[5:], 0)


def range_counts(prefix):
    """Alle Hash-Suffixe zu einem 5-Zeichen-Präfix (mit Padding gegen Verkehrsanalyse)."""
    _, body = net.fetch(PWNED_RANGE + prefix, headers={"Add-Padding": "true"})
    out = {}
    for line in body.decode("ascii", "replace").splitlines():
        h, _, count = line.partition(":")
        if count.strip() and int(count) > 0:  # Padding-Einträge haben Anzahl 0
            out[h.strip()] = int(count)
    return out


def describe(f):
    when = f" ({f['date']})" if f.get("date") else ""
    classes = ", ".join(f.get("classes", [])[:6])
    return f"{f.get('title') or f.get('key')}{when}" + (f": {classes}" if classes else "")
