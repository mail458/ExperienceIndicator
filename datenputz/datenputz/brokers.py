"""Verzeichnis der Datenhändler: mitgelieferte Daten plus eigene Einträge."""
import json
import re
from importlib import resources
from urllib.parse import urlparse

from . import store

EU_EEA = {
    "at", "be", "bg", "cy", "cz", "de", "dk", "ee", "es", "fi", "fr", "gr", "hr", "hu", "ie", "is",
    "it", "li", "lt", "lu", "lv", "mt", "nl", "no", "pl", "pt", "ro", "se", "si", "sk",
}


def _load(name):
    return json.loads(resources.files("datenputz.data").joinpath(name).read_text(encoding="utf-8"))


def custom_path():
    return store.home() / "custom_brokers.json"


def load_custom():
    p = custom_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_custom(entries):
    custom_path().parent.mkdir(parents=True, exist_ok=True)
    custom_path().write_text(json.dumps(entries, indent=1, ensure_ascii=False), encoding="utf-8")


def all_brokers():
    seen, out = set(), []
    for b in load_custom() + _load("brokers.json") + _load("people_search.json"):
        if b["id"] not in seen:
            seen.add(b["id"])
            out.append(b)
    return out


def by_id():
    return {b["id"]: b for b in all_brokers()}


def authorities():
    return _load("authorities.json")


def relevant(broker, country):
    """Ist der Händler für eine Person mit Wohnsitz in `country` relevant?"""
    countries = set(broker.get("countries") or ["all"])
    return "all" in countries or country in countries or bool(broker.get("custom"))


def select(country, categories=None, search=None, include_public=None):
    """Händler für ein Land filtern.

    US-Personensuchmaschinen werden nur für US-Wohnsitz automatisch
    einbezogen, außer `include_public` ist gesetzt.
    """
    out = []
    for b in all_brokers():
        if b.get("type") == "public" and not (include_public or country == "us"):
            continue
        if b.get("type") != "public" and not relevant(b, country):
            continue
        if categories and not set(categories) & set(b.get("categories", [])):
            continue
        if search and not re.search(search, b["name"] + " " + b["id"], re.I):
            continue
        out.append(b)
    return out


def law_for(country):
    """Rechtsgrundlage, die für die Anfrage herangezogen wird."""
    if country in EU_EEA or country in ("gb", "ch"):
        return "gdpr"
    if country == "us":
        return "ccpa"
    return "gdpr"


def domains(broker):
    """Alle Domains, über die ein Händler antworten könnte (für die Postfach-Zuordnung)."""
    ds = set()
    if broker.get("email") and "@" in broker["email"]:
        ds.add(broker["email"].split("@", 1)[1].lower())
    for key in ("web", "webform"):
        if broker.get(key):
            host = urlparse(broker[key]).hostname or ""
            if host:
                ds.add(host.lower().removeprefix("www."))
    # Basisdomain ergänzen (z. B. mail.acxiom.com -> acxiom.com)
    for d in list(ds):
        parts = d.split(".")
        if len(parts) > 2:
            ds.add(".".join(parts[-2:]))
    return ds


def make_custom(url, name=None, email=None, country="all"):
    host = (urlparse(url if "://" in url else "https://" + url).hostname or url).removeprefix("www.")
    slug = "custom-" + re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
    return {
        "id": slug,
        "name": name or host,
        "email": email,
        "webform": None,
        "web": "https://" + host,
        "address": None,
        "countries": [country],
        "categories": ["custom"],
        "type": "private",
        "default_request": "erasure",
        "channel": "email" if email else "webform",
        "language": None,
        "needs_id": False,
        "required": [],
        "comments": [],
        "custom": True,
        "source": "eigener Eintrag",
    }
