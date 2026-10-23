"""Passwort-Audit: Export eines Passwortmanagers prüfen, ohne Passwörter preiszugeben.

* jedes Passwort per k-Anonymität gegen Pwned Passwords (je Hash-Präfix eine Abfrage)
* mehrfach genutzte Passwörter
* schwache Passwörter (Länge, Zeichenvielfalt, enthält Benutzer- oder Dienstnamen)
* Dienst hatte einen Leak, nachdem das Passwort zuletzt geändert wurde
* sehr alte Passwörter

Klartext-Passwörter bleiben nur kurz im Speicher; gespeichert und ausgegeben
werden nie Passwörter, nur Dienst, Benutzername und Befund.
"""
import csv
import hashlib
import math
import os
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import breach as BR
from . import checker

# Spaltennamen der gängigen Exporte (Bitwarden, Chrome/Edge, Firefox, 1Password,
# KeePass/KeePassXC, Apple Passwörter, LastPass, Proton Pass, Dashlane, Enpass)
COLUMNS = {
    "password": ("login_password", "password", "passwort", "kennwort"),
    "username": ("login_username", "username", "benutzername", "user name", "login", "email", "e-mail"),
    "url": ("login_uri", "url", "website", "web site", "uri", "adresse"),
    "name": ("name", "title", "titel"),
    "totp": ("login_totp", "totp", "otpauth", "otp"),
    "changed": ("timepasswordchanged", "last modified", "modifytime", "passwordchanged", "geändert"),
}
OLD_DAYS = 730


def _find(header, field):
    low = [h.strip().lower() for h in header]
    for cand in COLUMNS[field]:
        if cand in low:
            return low.index(cand)
    return None


def _date(value):
    v = (value or "").strip()
    if not v:
        return None
    if v.isdigit():  # Firefox: Millisekunden, Proton: Sekunden
        n = int(v)
        return datetime.fromtimestamp(n / 1000 if n > 10 ** 11 else n, tz=timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M"):
        try:
            d = datetime.strptime(v.replace("Z", "+0000") if "%z" in fmt else v, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def strength(pw, hints=()):
    """(bits, [probleme]) – grobe Schätzung, bewusst streng."""
    pools = [(any(c.islower() for c in pw), 26), (any(c.isupper() for c in pw), 26),
             (any(c.isdigit() for c in pw), 10), (any(not c.isalnum() for c in pw), 33)]
    pool = sum(n for used, n in pools if used) or 1
    bits = len(pw) * math.log2(pool)
    problems = []
    if len(pw) < 10:
        problems.append(f"nur {len(pw)} Zeichen")
    if len(set(pw)) <= max(3, len(pw) // 4):
        problems.append("viele Wiederholungen")
    low = pw.lower()
    for h in hints:
        if h and len(h) >= 4 and h.lower() in low:
            problems.append("enthält Benutzer- oder Dienstnamen")
            break
    if low.rstrip("0123456789!?.") in ("password", "passwort", "qwertz", "qwerty", "hallo", "geheim", "letmein"):
        problems.append("Allerweltspasswort")
    elif PATTERN.search(low):
        problems.append("vorhersehbares Muster (Jahreszeit/Monat/Tastaturfolge + Zahl)")
    return bits, problems


PATTERN = re.compile(
    r"^(sommer|winter|herbst|fr(ü|ue)hling|summer|spring|autumn|fall|januar|februar|m(ä|ae)rz|april|mai|juni|juli|"
    r"august|september|oktober|november|dezember|january|february|march|may|june|july|october|december|"
    r"qwert[yz]|asdf|yxcv|1234|abcd|passw(or)?d?|willkommen|welcome|admin|test)[a-z]*[-_.]?\d{0,4}[!?.#*+]*$")


def load(path):
    """Liest den Export und gibt Einträge mit Hash statt Klartext zurück."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(f, dialect))
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    idx = {k: _find(header, k) for k in COLUMNS}
    if idx["password"] is None:
        raise ValueError("Keine Passwort-Spalte gefunden. Unterstützt: Bitwarden, Chrome/Edge, Firefox, 1Password, "
                         "KeePass(XC), Apple, LastPass, Proton Pass, Dashlane, Enpass (CSV).")

    def col(row, k):
        i = idx[k]
        return row[i].strip() if i is not None and i < len(row) else ""

    entries = []
    for row in body:
        pw = col(row, "password")
        if not pw:
            continue
        url = col(row, "url")
        host = (urlsplit(url if "://" in url else "https://" + url).hostname or "") if url else ""
        name = col(row, "name") or host or "(ohne Namen)"
        user = col(row, "username")
        site_word = checker.registrable(host).split(".")[0] if host else ""
        bits, problems = strength(pw, (user.split("@")[0], site_word, name))
        entries.append({
            "name": name, "user": user, "host": host, "domain": checker.registrable(host) if host else "",
            "sha1": hashlib.sha1(pw.encode("utf-8")).hexdigest().upper(),
            "bits": round(bits), "weak": problems, "totp": bool(col(row, "totp")),
            "changed": _date(col(row, "changed")),
        })
        pw = None  # Klartext nicht länger als nötig referenzieren
    for row in body:  # Klartext-Zeilen leeren (Python kann Speicher nicht sicher überschreiben)
        row.clear()
    rows.clear()
    return entries


def audit(entries, breaches=None, offline=False, workers=8):
    """Bewertet alle Einträge. Gibt (befunde, zusammenfassung) zurück."""
    counts = {}
    if not offline:
        prefixes = sorted({e["sha1"][:5] for e in entries})
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for prefix, res in zip(prefixes, ex.map(BR.range_counts, prefixes)):
                counts[prefix] = res
    by_hash = {}
    for e in entries:
        by_hash.setdefault(e["sha1"], []).append(e)
    by_domain = {}
    for b in breaches or []:
        if b.get("Domain") and not b.get("IsSpamList"):
            by_domain.setdefault(checker.registrable(b["Domain"]), []).append(b)
    now = datetime.now(timezone.utc)
    results = []
    for e in entries:
        issues = []
        pwned = counts.get(e["sha1"][:5], {}).get(e["sha1"][5:], 0)
        if pwned:
            issues.append(("kritisch", f"Passwort steht {pwned:,} Mal in Leak-Listen".replace(",", ".")))
        for b in by_domain.get(e["domain"], []):
            bd = _date(b.get("BreachDate"))
            if e["changed"] and bd and e["changed"] > bd:
                continue  # nach dem Leak geändert – gut
            when = "vor" if e["changed"] else "möglicherweise vor"
            issues.append(("kritisch" if e["changed"] else "hoch",
                           f"{b.get('Title', b['Name'])} hatte am {b.get('BreachDate')} einen Leak – Passwort "
                           f"wurde {when} diesem Datum zuletzt geändert"))
        same = len(by_hash[e["sha1"]])
        if same > 1:
            others = ", ".join(sorted({x["name"] for x in by_hash[e["sha1"]] if x is not e}))[:120]
            issues.append(("hoch", f"dasselbe Passwort wie bei {same - 1} weiteren Konten ({others})"))
        if e["weak"] or e["bits"] < 50:
            issues.append(("mittel", "schwach: " + ", ".join(e["weak"] or [f"nur ca. {e['bits']} Bit"])))
        if e["changed"] and (now - e["changed"]).days > OLD_DAYS:
            issues.append(("info", f"seit {(now - e['changed']).days // 365} Jahren nicht geändert"))
        if issues:
            sev = min((i[0] for i in issues), key=BR.RANK.get)
            results.append({"name": e["name"], "user": e["user"], "host": e["host"], "severity": sev,
                            "issues": issues, "totp": e["totp"]})
    results.sort(key=lambda r: (BR.RANK[r["severity"]], r["name"].lower()))
    summary = {s: sum(1 for r in results if r["severity"] == s) for s in BR.SEVERITIES}
    summary.update(total=len(entries), ok=len(entries) - len(results),
                   reused=sum(1 for v in by_hash.values() if len(v) > 1),
                   without_totp=sum(1 for e in entries if not e["totp"]), offline=offline)
    return results, summary


def shred(path, passes=2):
    """Datei überschreiben und löschen. Auf SSDs/Journaling-Dateisystemen nicht garantiert vollständig."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("Nur echte Dateien werden vernichtet (keine Verknüpfungen).")
    size = p.stat().st_size
    with open(p, "r+b", buffering=0) as f:
        for _ in range(passes):
            f.seek(0)
            remaining = size
            while remaining > 0:
                n = min(remaining, 1 << 20)
                f.write(secrets.token_bytes(n))
                remaining -= n
            os.fsync(f.fileno())
    tmp = p.with_name(secrets.token_hex(8))  # Dateinamen nicht im Verzeichnis zurücklassen
    p.rename(tmp)
    tmp.unlink()
    return True
