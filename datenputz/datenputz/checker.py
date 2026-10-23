"""Link-, Betrugs- und Dateiprüfung (wie NordVPNs Link Checker, Scam Checker, File Checker).

Alles läuft lokal anhand von Sperrlisten und Merkmalen; nur die optionale
MalwareBazaar-Abfrage schickt den SHA-256-Hash einer Datei (nie die Datei).
"""
import hashlib
import ipaddress
import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from . import net
from . import shield

BRANDS = [
    "paypal.com", "amazon.de", "amazon.com", "apple.com", "icloud.com", "microsoft.com", "outlook.com",
    "live.com", "google.com", "gmail.com", "facebook.com", "instagram.com", "whatsapp.com", "netflix.com",
    "spotify.com", "dhl.de", "dhl.com", "dpd.de", "hermesworld.com", "myhermes.de", "ups.com", "gls-pakete.de",
    "deutschepost.de", "sparkasse.de", "deutsche-bank.de", "commerzbank.de", "ing.de", "dkb.de", "postbank.de",
    "n26.com", "volksbank.de", "comdirect.de", "consorsbank.de", "targobank.de", "hypovereinsbank.de",
    "telekom.de", "vodafone.de", "o2online.de", "1und1.de", "ebay.de", "ebay.com", "kleinanzeigen.de",
    "elster.de", "bund.de", "zalando.de", "otto.de", "booking.com", "airbnb.com", "binance.com", "coinbase.com",
    "steamcommunity.com", "linkedin.com", "adobe.com", "dropbox.com", "docusign.com", "web.de", "gmx.de",
    "t-online.de", "check24.de", "paydirekt.de", "klarna.com", "mastercard.com", "visa.com",
]
SUSPICIOUS_TLDS = {
    "zip", "mov", "xyz", "top", "click", "tk", "ml", "ga", "cf", "gq", "icu", "cfd", "sbs", "rest", "lol",
    "buzz", "cam", "monster", "quest", "bond", "cyou", "live", "support", "help", "shop", "loan", "work",
}
SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "cutt.ly", "rebrand.ly", "shorturl.at",
    "tiny.cc", "buff.ly", "rb.gy", "t.ly", "s.id", "lnkd.in", "qrco.de",
}
MULTI_PART_SUFFIXES = {"co.uk", "org.uk", "ac.uk", "com.au", "co.jp", "co.nz", "com.br", "co.at", "or.at", "gv.at", "com.tr", "co.za"}
LURE_WORDS = re.compile(r"login|log-in|signin|verif|secure|account|konto|update|bestaetig|bestätig|confirm|"
                        r"unlock|entsperr|wallet|password|passwort|banking|tan\b|support", re.I)


def registrable(host):
    """Näherung an die registrierbare Domain (ohne vollständige Public Suffix List)."""
    parts = host.lower().rstrip(".").split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _lev(a, b):
    if abs(len(a) - len(b)) > 2:
        return 3
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _skeleton(s):
    """Typische Verwechslungen angleichen (0→o, 1→l, rn→m, vv→w)."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.translate(str.maketrans("01345", "oleas")).replace("rn", "m").replace("vv", "w")


# Echte Zweit-Domains der Marken und regionale Banken, die sonst als Nachahmung gälten
LEGIT_RELATED = {
    "googleapis.com", "googleusercontent.com", "googlevideo.com", "paypalobjects.com", "microsoftonline.com",
    "amazonaws.com", "amazontrust.com", "applecloud.com", "icloud-content.com", "ebaystatic.com",
    "netflixdnstest.com", "spotifycdn.com", "linkedinmobileapp.com", "dropboxusercontent.com",
}
LEGIT_REGIONAL = re.compile(r"^(sparkasse|kreissparkasse|stadtsparkasse|ksk|volksbank|vr|raiffeisenbank|"
                            r"sparda)[-a-z0-9]*\.de$")


def lookalike(host):
    """Gibt die nachgeahmte Marke zurück, falls die Domain einer bekannten ähnelt."""
    reg = registrable(host)
    name = reg.split(".")[0]
    if reg in BRANDS or reg in LEGIT_RELATED or LEGIT_REGIONAL.match(reg):
        return None
    for brand in BRANDS:
        bname = brand.split(".")[0]
        if len(bname) < 5:  # kurze Namen (ing, dhl, otto …) erzeugen zu viele Fehlalarme
            continue
        if (len(name) >= 5 and _lev(name, bname) in (1, 2)) or (_skeleton(name) == bname and name != bname):
            return brand
        if bname in name and name != bname:  # paypal-sicherheit.com
            return brand
    tokens = set(re.split(r"[-_]", name))
    for brand in BRANDS:  # dhl-zustellung.top, ing-sicherheit.com
        if len(tokens) > 1 and brand.split(".")[0] in tokens:
            return brand
    labels = host.lower().split(".")[:-2]
    for brand in BRANDS:  # paypal.com.konto-check.xyz
        if brand.split(".")[0] in labels or brand in host.lower().removesuffix("." + reg):
            return brand
    return None


def check_url(url, blocklist=None):
    """Bewertet einen Link. Gibt dict mit score, verdict und Gründen zurück."""
    raw = url.strip()
    if "://" not in raw:
        raw = "http://" + raw
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    reasons, score = [], 0

    def flag(points, text):
        nonlocal score
        score += points
        reasons.append(text)

    bl = blocklist if blocklist is not None else shield.Blocklist()
    hit = bl.match(host) if host else None
    if hit:
        flag(100, f"steht auf einer Sperrliste ({hit})")
    try:
        ipaddress.ip_address(host.strip("[]"))
        flag(30, "IP-Adresse statt Domainname")
    except ValueError:
        pass
    if "xn--" in host or any(ord(c) > 127 for c in host):
        flag(30, "internationalisierte Domain (mögliche Buchstaben-Täuschung)")
    brand = lookalike(host) if host else None
    if brand:
        flag(40, f"ähnelt {brand}, gehört aber nicht dazu")
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in SUSPICIOUS_TLDS:
        flag(15, f"Endung .{tld} wird häufig für Betrug genutzt")
    if "@" in parts.netloc:
        flag(30, "„@“ im Link versteckt das echte Ziel")
    if parts.scheme == "http":
        flag(10, "unverschlüsselt (http)")
    if registrable(host) in SHORTENERS or host in SHORTENERS:
        flag(10, "Kurzlink – Ziel ist verschleiert")
    if host.count(".") >= 4:
        flag(10, "ungewöhnlich viele Subdomains")
    if score and LURE_WORDS.search(parts.path + "?" + parts.query + host):
        flag(10, "Lockwörter wie Login/Konto/Bestätigen")
    cleaned, removed = shield.clean_url(raw)
    verdict = "gefährlich" if score >= 60 else "verdächtig" if score >= 25 else "unauffällig"
    return {"url": url, "host": host, "score": score, "verdict": verdict, "reasons": reasons,
            "tracking": removed, "clean": cleaned if removed else None}


# --------------------------------------------------------------------------
SCAM_PATTERNS = [
    (r"(konto|account|karte|zugang).{0,40}(gesperrt|eingeschränkt|deaktiviert|suspended|locked|limited)", 25,
     "droht mit Kontosperrung"),
    (r"innerhalb (von )?\d+ ?(stunden|std|h)\b|within \d+ hours|sofort|umgehend|letzte (mahnung|warnung)|final notice|"
     r"immediately|urgent|dringend", 15, "erzeugt Zeitdruck"),
    (r"ungewöhnliche aktivität|verdächtige anmeldung|unusual (sign-?in )?activity|suspicious login", 20,
     "meldet angebliche verdächtige Aktivität"),
    (r"paket.{0,40}(nicht zugestellt|zustellung|zollgebühr|gebühr)|parcel.{0,30}(fee|delivery)|customs fee", 25,
     "angebliche Paketzustellung mit Gebühr"),
    (r"(sie haben|you have) .{0,20}(gewonnen|won)|gewinnspiel|lottery|lotterie|erbschaft|inheritance", 25,
     "Gewinn- oder Erbschaftsversprechen"),
    (r"geschenkkarte|gift ?card|itunes-karte|paysafecard|google play karte", 30, "Bezahlung mit Gutscheinkarten"),
    (r"bitcoin|krypto|crypto|wallet|usdt", 10, "Krypto-Bezug"),
    (r"hallo (mama|papa)|hi (mum|mom|dad)|meine neue nummer|my new number|handy (ist )?kaputt", 35,
     "„Hallo Mama/Papa“-Masche (neue Nummer)"),
    (r"\b(tan|pin|passwort|password|kennwort|cvv|prüfziffer)\b.{0,40}(eingeben|bestätigen|mitteilen|senden|confirm|enter)",
     35, "fordert Passwort/PIN/TAN"),
    (r"(überweis|transfer).{0,40}(heute|sofort|dringend|today)|(heute|sofort|dringend|today).{0,40}(überweis|transfer)",
     20, "fordert eilige Überweisung"),
    (r"(fernwartung|anydesk|teamviewer|remote access)", 25, "will Fernzugriff auf den Rechner"),
]


def check_text(text, blocklist=None):
    """Nachricht (Mail, SMS, Chat) auf typische Betrugsmerkmale prüfen."""
    score, reasons = 0, []
    low = text.lower()
    for pattern, points, why in SCAM_PATTERNS:
        if re.search(pattern, low):
            score += points
            reasons.append(why)
    urls = re.findall(r"(?:https?://|www\.)[^\s<>\"')]+", text, re.I)
    bl = blocklist if blocklist is not None else shield.Blocklist()
    links = [check_url(u, bl) for u in urls]
    if links:
        score += max(x["score"] for x in links)
    phones = re.findall(r"(?:\+|00)\d[\d \-/]{7,}\d", text)
    verdict = "gefährlich" if score >= 60 else "verdächtig" if score >= 25 else "unauffällig"
    return {"score": score, "verdict": verdict, "reasons": reasons, "links": links, "phones": phones}


# --------------------------------------------------------------------------
RISKY_EXT = {
    "exe", "scr", "bat", "cmd", "com", "pif", "js", "jse", "vbs", "vbe", "wsf", "wsh", "hta", "ps1", "lnk",
    "iso", "img", "vhd", "msi", "jar", "docm", "xlsm", "pptm", "dotm", "xlam", "apk", "dmg", "pkg", "reg",
    "cpl", "chm", "one", "html", "htm", "svg",
}
DOC_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "txt", "zip", "mp4", "mp3", "rtf"}
MAGIC = [(b"MZ", "Windows-Programm"), (b"\x7fELF", "Linux-Programm"), (b"\xcf\xfa\xed\xfe", "macOS-Programm"),
         (b"%PDF", "PDF"), (b"PK\x03\x04", "ZIP-Archiv/Office"), (b"\xd0\xcf\x11\xe0", "altes Office-Dokument")]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def malwarebazaar(digest, key):
    status, body = net.fetch("https://mb-api.abuse.ch/api/v1/", method="POST",
                             data=urlencode({"query": "get_info", "hash": digest}).encode(),
                             headers={"Auth-Key": key, "Content-Type": "application/x-www-form-urlencoded"})
    d = json.loads(body)
    if d.get("query_status") == "ok" and d.get("data"):
        x = d["data"][0]
        return x.get("signature") or x.get("file_type") or "bekannte Malware"
    return None


def check_file(path, key=None):
    p = Path(path)
    name = p.name
    reasons, score = [], 0
    exts = [e.lower() for e in name.split(".")[1:]]
    if "‮" in name:
        score += 60
        reasons.append("Dateiname enthält Schreibrichtungs-Umkehr (versteckt die echte Endung)")
    if len(exts) >= 2 and exts[-1] in RISKY_EXT and exts[-2] in DOC_EXT:
        score += 60
        reasons.append(f"doppelte Endung .{exts[-2]}.{exts[-1]} – tarnt ein Programm als Dokument")
    elif exts and exts[-1] in RISKY_EXT:
        score += 20
        reasons.append(f".{exts[-1]} kann Code ausführen – nur aus vertrauenswürdiger Quelle öffnen")
    with open(p, "rb") as f:
        head = f.read(8)
    kind = next((k for m, k in MAGIC if head.startswith(m)), None)
    if kind and "Programm" in kind and exts and exts[-1] in DOC_EXT:
        score += 60
        reasons.append(f"Inhalt ist ein {kind}, obwohl die Endung .{exts[-1]} lautet")
    digest = sha256(p)
    known = None
    key = key or os.environ.get("ABUSE_CH_AUTH_KEY")
    if key:
        known = malwarebazaar(digest, key)
        if known:
            score += 100
            reasons.append(f"in MalwareBazaar als Schadsoftware bekannt: {known}")
    verdict = "gefährlich" if score >= 60 else "verdächtig" if score >= 20 else "unauffällig"
    return {"file": str(p), "sha256": digest, "type": kind, "score": score, "verdict": verdict,
            "reasons": reasons, "lookup": bool(key)}
