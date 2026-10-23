"""Benachrichtigungen aufs Handy: ntfy, Gotify, Telegram oder Mail.

Standardmäßig sind die Meldungen „knapp“: nur Anzahlen und Stufen, keine
Adressen, Dienstnamen oder Leak-Details. Push-Dienste sehen den Inhalt, und
ein öffentliches ntfy-Thema kann jeder lesen, der den Namen kennt. Mit
`detail: full` werden Details mitgeschickt (nur bei eigenem Server sinnvoll).
"""
import json
import secrets
import urllib.parse

from . import keystore as K
from . import mailer as M
from . import net

PRIORITY = {"info": 2, "mittel": 3, "hoch": 4, "kritisch": 5}  # ntfy 1–5, Gotify 0–10 (×2)


def channels(store):
    return store.config().get("notify", {}).get("channels", [])


def add_channel(store, channel):
    cfg = store.config()
    n = cfg.setdefault("notify", {"detail": "minimal"})
    n["channels"] = [c for c in n.get("channels", []) if c["type"] != channel["type"]] + [channel]
    store.save_config(cfg)


def remove_channel(store, kind):
    cfg = store.config()
    n = cfg.get("notify", {})
    n["channels"] = [c for c in n.get("channels", []) if c["type"] != kind]
    store.save_config(cfg)


def detail(store):
    return store.config().get("notify", {}).get("detail", "minimal")


def new_ntfy_topic():
    """Nicht erratbarer Themenname – auf ntfy.sh ist das Thema das einzige Geheimnis."""
    return "datenputz-" + secrets.token_urlsafe(18)


def _ntfy(c, title, body, level, store):
    # Titel als Query-Parameter: HTTP-Header vertragen keine Umlaute zuverlässig
    params = urllib.parse.urlencode({"title": title, "priority": PRIORITY.get(level, 3),
                                     "tags": "lock" if level in ("info", "mittel") else "warning"})
    url = c.get("server", "https://ntfy.sh").rstrip("/") + "/" + urllib.parse.quote(c["topic"]) + "?" + params
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    token = K.get("ntfy", store)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    net.fetch(url, data=body.encode("utf-8"), headers=headers, method="POST", timeout=15)


def _gotify(c, title, body, level, store):
    token = K.get("gotify", store)
    if not token:
        raise RuntimeError("Gotify-Token fehlt: secret set gotify")
    data = json.dumps({"title": title, "message": body, "priority": PRIORITY.get(level, 3) * 2}).encode()
    net.fetch(c["server"].rstrip("/") + "/message", data=data, method="POST", timeout=15,
              headers={"Content-Type": "application/json", "X-Gotify-Key": token})


def _telegram(c, title, body, level, store):
    token = K.get("telegram", store)
    if not token:
        raise RuntimeError("Telegram-Bot-Token fehlt: secret set telegram")
    data = urllib.parse.urlencode({"chat_id": c["chat_id"], "text": f"{title}\n\n{body}",
                                   "disable_web_page_preview": "true"}).encode()
    net.fetch(f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST", timeout=15,
              headers={"Content-Type": "application/x-www-form-urlencoded"})


def _email(c, title, body, level, store):
    smtp = store.config().get("smtp")
    if not smtp:
        raise RuntimeError("SMTP nicht eingerichtet")
    msg = M.build(smtp["from"], c.get("to") or smtp["from"], f"Datenputz: {title}", body)
    m = M.SMTPMailer(smtp, delay=0)
    try:
        m.send(msg, "notify")
    finally:
        m.close()


SENDERS = {"ntfy": _ntfy, "gotify": _gotify, "telegram": _telegram, "email": _email}


def send(store, title, body, level="mittel"):
    """An alle eingerichteten Kanäle senden. Gibt Liste (kanal, fehler|None) zurück; wirft nie."""
    results = []
    for c in channels(store):
        try:
            SENDERS[c["type"]](c, title, body, level, store)
            results.append((c["type"], None))
        except Exception as e:  # ein ausgefallener Kanal verhindert die anderen nicht
            results.append((c["type"], str(e)))
    return results
