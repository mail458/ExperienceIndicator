"""Zeitsteuerung für den täglichen Lauf: systemd (Linux), launchd (macOS), Aufgabenplanung (Windows).

Erzeugt die Dateien selbst und richtet sie auf Wunsch ein. Der Lauf startet
mit leichter Zufallsverzögerung, holen verpasste Termine nach und arbeitet
ohne Terminal (Passwörter kommen aus dem Schlüsselbund).
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from . import store as S

LABEL = "de.datenputz.daily"
PROJECT = Path(__file__).resolve().parent.parent  # Ordner, der das Paket enthält


def detect():
    system = platform.system()
    if system == "Linux" and shutil.which("systemctl"):
        return "systemd"
    if system == "Darwin":
        return "launchd"
    if system == "Windows":
        return "schtasks"
    return "cron"


def _cmd():
    return [sys.executable, "-m", "datenputz", "daily"]


def systemd_units(time_, home, system_wide=False):
    hh, mm = time_.split(":")
    service = f"""[Unit]
Description=Datenputz – täglicher Lauf (Löschanträge, Leak-Prüfung, Benachrichtigung)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={PROJECT}
Environment="PYTHONPATH={PROJECT}"
Environment="DATENPUTZ_HOME={home}"
ExecStart={' '.join(f'"{c}"' if " " in c else c for c in _cmd())}
Nice=10
NoNewPrivileges=yes
"""
    if system_wide:  # Härtung für Systemdienste: nur der Datenordner ist beschreibbar
        service += f"PrivateTmp=yes\nProtectSystem=strict\nReadWritePaths={home}\n"
    timer = f"""[Unit]
Description=Datenputz – täglich um {time_}

[Timer]
OnCalendar=*-*-* {hh}:{mm}:00
RandomizedDelaySec=15min
Persistent=true

[Install]
WantedBy=timers.target
"""
    return service, timer


def launchd_plist(time_, home):
    hh, mm = (int(x) for x in time_.split(":"))
    args = "".join(f"<string>{a}</string>" for a in _cmd())
    log = Path(home) / "daily.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array>{args}</array>
  <key>WorkingDirectory</key><string>{PROJECT}</string>
  <key>EnvironmentVariables</key><dict>
    <key>PYTHONPATH</key><string>{PROJECT}</string>
    <key>DATENPUTZ_HOME</key><string>{home}</string>
  </dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>{hh}</integer><key>Minute</key><integer>{mm}</integer></dict>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
  <key>ProcessType</key><string>Background</string>
</dict></plist>
"""


def schtasks_cmd(time_, home):
    tr = f'cmd /c "set DATENPUTZ_HOME={home}&& set PYTHONPATH={PROJECT}&& cd /d {PROJECT}&& {" ".join(_cmd())}"'
    return ["schtasks", "/Create", "/F", "/SC", "DAILY", "/TN", "Datenputz", "/ST", time_, "/TR", tr]


def cron_line(time_, home):
    hh, mm = time_.split(":")
    return f"{int(mm)} {int(hh)} * * *  cd {PROJECT} && DATENPUTZ_HOME={home} {' '.join(_cmd())} >> {home}/daily.log 2>&1"


def plan(time_="08:17", kind=None, home=None):
    """Beschreibt, was installiert würde: (art, [(pfad, inhalt)], [befehle])."""
    kind = kind or detect()
    home = Path(home or S.home())
    if kind == "systemd":
        root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
        base = Path("/etc/systemd/system") if root else Path.home() / ".config/systemd/user"
        service, timer = systemd_units(time_, home, system_wide=root)
        ctl = ["systemctl"] + ([] if root else ["--user"])
        return kind, [(base / "datenputz.service", service), (base / "datenputz.timer", timer)], \
            [ctl + ["daemon-reload"], ctl + ["enable", "--now", "datenputz.timer"]]
    if kind == "launchd":
        path = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
        return kind, [(path, launchd_plist(time_, home))], [["launchctl", "unload", str(path)],
                                                             ["launchctl", "load", "-w", str(path)]]
    if kind == "schtasks":
        return kind, [], [schtasks_cmd(time_, home)]
    return "cron", [], []


def install(st, time_="08:17", kind=None, dry_run=False):
    kind, files, cmds = plan(time_, kind, st.dir)
    if kind == "cron":
        return kind, f"Kein Dienstplaner erkannt. Diese Zeile mit `crontab -e` eintragen:\n{cron_line(time_, st.dir)}"
    if dry_run:
        text = "\n\n".join(f"# {p}\n{c}" for p, c in files) + "\n\n" + "\n".join(" ".join(c) for c in cmds)
        return kind, text
    for path, content in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for c in cmds:
        r = subprocess.run(c, capture_output=True, text=True)
        if r.returncode and c[:2] != ["launchctl", "unload"]:  # „nicht geladen“ beim Entladen ist kein Fehler
            raise RuntimeError(f"{' '.join(c[:3])}: {(r.stderr or r.stdout).strip()}")
    st.set_kv("schedule", {"kind": kind, "time": time_, "files": [str(p) for p, _ in files]})
    hint = ""
    if kind == "systemd" and "--user" in cmds[0]:
        hint = f"\nDamit der Lauf auch ohne Anmeldung startet: `sudo loginctl enable-linger {os.environ.get('USER', '$USER')}`"
    return kind, f"Eingerichtet: täglich um {time_} ({kind}).{hint}"


def remove(st):
    s = st.get_kv("schedule") or {}
    kind = s.get("kind") or detect()
    if kind == "systemd":
        user = not any(str(f).startswith("/etc/") for f in s.get("files", []))
        subprocess.run(["systemctl"] + (["--user"] if user else []) + ["disable", "--now", "datenputz.timer"],
                       capture_output=True)
    elif kind == "launchd":
        for f in s.get("files", []):
            subprocess.run(["launchctl", "unload", f], capture_output=True)
    elif kind == "schtasks":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", "Datenputz"], capture_output=True)
    for f in s.get("files", []):
        Path(f).unlink(missing_ok=True)
    st.set_kv("schedule", None)
    return kind
