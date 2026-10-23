"""Geheimnisse (API-Schlüssel, Mailpasswörter) sicher aufbewahren.

Reihenfolge beim Lesen: Umgebungsvariable → Schlüsselbund des Betriebssystems
(macOS-Schlüsselbund bzw. Secret Service/GNOME Keyring/KWallet über
`secret-tool`) → Konfigurationsdatei (nur Rechte 600, mit Warnung beim Speichern).
"""
import os
import platform
import shutil
import subprocess

from . import store as S

SERVICE = "datenputz"
NAMES = {
    "hibp": ("HIBP_API_KEY", "Have I Been Pwned API-Schlüssel"),
    "smtp": ("DATENPUTZ_SMTP_PASSWORD", "SMTP-Passwort"),
    "imap": ("DATENPUTZ_IMAP_PASSWORD", "IMAP-Passwort"),
    "abusech": ("ABUSE_CH_AUTH_KEY", "abuse.ch Auth-Key (MalwareBazaar)"),
    "ntfy": ("DATENPUTZ_NTFY_TOKEN", "ntfy-Zugangstoken (optional)"),
    "gotify": ("DATENPUTZ_GOTIFY_TOKEN", "Gotify-App-Token"),
    "telegram": ("DATENPUTZ_TELEGRAM_TOKEN", "Telegram-Bot-Token"),
    "web": ("DATENPUTZ_WEB_TOKEN", "Zugangstoken der Web-Oberfläche"),
}


def backend():
    if platform.system() == "Darwin" and shutil.which("security"):
        return "macos"
    if shutil.which("secret-tool"):
        return "secret-tool"
    return None


def _kc_get(name):
    b = backend()
    try:
        if b == "macos":
            r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", name, "-w"],
                               capture_output=True, text=True, timeout=10)
        elif b == "secret-tool":
            r = subprocess.run(["secret-tool", "lookup", "service", SERVICE, "key", name],
                               capture_output=True, text=True, timeout=10)
        else:
            return None
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _kc_set(name, value):
    b = backend()
    if b == "secret-tool":  # Geheimnis über stdin, taucht nicht in der Prozessliste auf
        r = subprocess.run(["secret-tool", "store", f"--label=Datenputz {name}", "service", SERVICE, "key", name],
                           input=value, text=True, capture_output=True, timeout=30)
        return r.returncode == 0
    if b == "macos":
        # `security` nimmt das Geheimnis nur als Argument an; es ist dabei kurz für
        # lokale Prozesse sichtbar. Das ist der dokumentierte Weg des Systemwerkzeugs.
        r = subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", name, "-w", value],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    return False


def _kc_delete(name):
    b = backend()
    try:
        if b == "macos":
            subprocess.run(["security", "delete-generic-password", "-s", SERVICE, "-a", name], capture_output=True)
        elif b == "secret-tool":
            subprocess.run(["secret-tool", "clear", "service", SERVICE, "key", name], capture_output=True)
    except OSError:
        pass


def get(name, store=None):
    env = NAMES.get(name, (None,))[0]
    if env and os.environ.get(env):
        return os.environ[env]
    v = _kc_get(name)
    if v:
        return v
    cfg = (store or S.Store()).config()
    legacy = {"hibp": cfg.get("hibp_api_key")}.get(name)
    return (cfg.get("secrets") or {}).get(name) or legacy


def put(name, value, store=None):
    """Speichert im Schlüsselbund; nur wenn keiner da ist, in config.json (Rechte 600)."""
    st = store or S.Store()
    cfg = st.config()
    if _kc_set(name, value):
        (cfg.get("secrets") or {}).pop(name, None)
        if name == "hibp":
            cfg.pop("hibp_api_key", None)
        st.save_config(cfg)
        return "Schlüsselbund"
    cfg.setdefault("secrets", {})[name] = value
    st.save_config(cfg)
    return "config.json (Rechte 600 – kein Schlüsselbund gefunden)"


def delete(name, store=None):
    st = store or S.Store()
    _kc_delete(name)
    cfg = st.config()
    (cfg.get("secrets") or {}).pop(name, None)
    if name == "hibp":
        cfg.pop("hibp_api_key", None)
    st.save_config(cfg)


def status(store=None):
    out = []
    for name, (env, label) in NAMES.items():
        where = "Umgebung" if os.environ.get(env) else "Schlüsselbund" if _kc_get(name) else \
            "config.json" if ((store or S.Store()).config().get("secrets") or {}).get(name) else "–"
        out.append((name, label, where))
    return out


def require(name, prompt, store=None):
    """Geheimnis holen; ohne Terminal (Zeitsteuerung, Web) nie auf eine Eingabe warten."""
    import getpass
    import sys
    v = get(name, store)
    if v:
        return v
    if not sys.stdin or not sys.stdin.isatty():
        raise RuntimeError(f"{NAMES[name][1]} nicht hinterlegt – einmalig `python -m datenputz secret set {name}`")
    return getpass.getpass(prompt)
