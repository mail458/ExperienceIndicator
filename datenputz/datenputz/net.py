"""Kleiner HTTP-Helfer (nur Standardbibliothek). In Tests wird `fetch` ersetzt."""
import urllib.error
import urllib.request

from . import __version__

USER_AGENT = f"datenputz/{__version__} (+https://github.com/mail458/experienceindicator)"


class HTTPError(Exception):
    def __init__(self, status, body=b""):
        super().__init__(f"HTTP {status}")
        self.status, self.body = status, body


def fetch(url, data=None, headers=None, timeout=30, method=None):
    """Gibt (status, body_bytes) zurück; 404 ist kein Fehler, sondern ein Ergebnis."""
    h = {"User-Agent": USER_AGENT, **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, e.read()
        raise HTTPError(e.code, e.read()) from None
