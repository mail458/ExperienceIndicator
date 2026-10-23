#!/usr/bin/env python3
"""Erzeugt datenputz/data/brokers.json aus einem Checkout von
https://github.com/datenanfragen/data (Lizenz: CC0 1.0).

    git clone --depth 1 https://github.com/datenanfragen/data.git /tmp/dadata
    python scripts/build_brokers.py /tmp/dadata
"""
import json
import sys
from pathlib import Path

# Kategorien, die einem "Datenhändler" im Sinne von Incogni entsprechen.
BROKER_CATEGORIES = {"ads", "addresses", "credit agency", "collection agency"}
# Bekannte Händler/Auskunfteien ohne passende Kategorie im Datensatz.
EXTRA_SLUGS = {"experian-de", "experian-at", "experian-ch", "kantar-de", "bisnode-ab"}
# Auskunfteien und Inkasso: Löschung ist meist aussichtslos (berechtigtes
# Interesse), deshalb standardmäßig Selbstauskunft nach Art. 15.
ACCESS_CATEGORIES = {"credit agency", "collection agency"}


def convert(d):
    cats = d.get("categories") or []
    kind = "access" if set(cats) & ACCESS_CATEGORIES else "erasure"
    channel = d.get("suggested-transport-medium") or ("email" if d.get("email") else "letter")
    if channel == "fax":
        channel = "letter"
    if channel == "email" and not d.get("email"):
        channel = "webform" if d.get("webform") else "letter"
    return {
        "id": d["slug"],
        "name": d["name"],
        "email": d.get("email"),
        "webform": d.get("webform"),
        "web": d.get("web"),
        "address": d.get("address"),
        "countries": d.get("relevant-countries") or ["all"],
        "categories": cats or ["ads"],
        "type": "private",
        "default_request": kind,
        "channel": channel,
        "language": d.get("request-language"),
        "needs_id": bool(d.get("needs-id-document")),
        "required": sorted({e.get("type") for e in d.get("required-elements", []) if e.get("type")}),
        "comments": d.get("comments", []),
        "source": "datenanfragen.de (CC0)",
    }


def main(root):
    root = Path(root)
    out = []
    for f in sorted((root / "companies").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("nsfw"):
            continue
        if set(d.get("categories") or []) & BROKER_CATEGORIES or d["slug"] in EXTRA_SLUGS:
            out.append(convert(d))
    auth = []
    for f in sorted((root / "supervisory-authorities").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        auth.append({k: d.get(k) for k in ("slug", "name", "address", "email", "webform", "web", "relevant-countries", "complaint-language")})
    data = Path(__file__).resolve().parent.parent / "datenputz" / "data"
    (data / "brokers.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (data / "authorities.json").write_text(json.dumps(auth, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} Datenhändler, {len(auth)} Aufsichtsbehörden geschrieben.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dadata")
