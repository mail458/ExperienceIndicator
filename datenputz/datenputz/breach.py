"""Dark-Web-Monitor: geleakte Konten und Passwörter über Have I Been Pwned prüfen.

* Passwörter: k-Anonymität – nur die ersten 5 Zeichen des SHA-1-Hashes
  verlassen den Rechner, das Passwort selbst nie (kostenlos, ohne Schlüssel).
* E-Mail-Adressen: HIBP-API v3, braucht einen eigenen API-Schlüssel
  (haveibeenpwned.com/API/Key). Neue Funde werden gemeldet, bekannte nicht erneut.
"""
import hashlib
import json
import time
import urllib.parse

from . import net
from . import store as S

PWNED_RANGE = "https://api.pwnedpasswords.com/range/"
HIBP_ACCOUNT = "https://haveibeenpwned.com/api/v3/breachedaccount/"


def password_count(password):
    """Wie oft kommt das Passwort in bekannten Leaks vor? 0 = nicht gefunden."""
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    _, body = net.fetch(PWNED_RANGE + prefix, headers={"Add-Padding": "true"})
    for line in body.decode("ascii", "replace").splitlines():
        h, _, count = line.partition(":")
        if h.strip() == suffix:
            return int(count)
    return 0


def account_breaches(email, api_key, retries=3):
    url = HIBP_ACCOUNT + urllib.parse.quote(email) + "?truncateResponse=false"
    for attempt in range(retries):
        try:
            status, body = net.fetch(url, headers={"hibp-api-key": api_key})
        except net.HTTPError as e:
            if e.status == 429 and attempt < retries - 1:  # Ratenlimit
                time.sleep(7)
                continue
            if e.status == 401:
                raise SystemExit("HIBP: API-Schlüssel ungültig.") from None
            raise
        return [] if status == 404 else json.loads(body)
    return []


def monitor(store, api_key, emails, pause=6.5):
    """Alle Adressen prüfen, neue Leaks speichern und zurückgeben."""
    new = []
    for i, email in enumerate(emails):
        if i:
            time.sleep(pause)  # kleinster HIBP-Tarif: 10 Anfragen pro Minute
        for b in account_breaches(email, api_key):
            if store.add_breach(email, b):
                new.append((email, b))
    store.set_kv("breach_last_check", S.iso(S.now()))
    return new


def describe(b):
    classes = ", ".join(b.get("DataClasses", [])[:6])
    return f"{b.get('Title', b.get('Name'))} ({b.get('BreachDate', '?')}): {classes}"
