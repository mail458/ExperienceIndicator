"""Persistenz: Profile, Anfragen und Ereignisse in einer lokalen SQLite-Datei."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Status einer Anfrage
PENDING = "pending"            # geplant, noch nicht verschickt
SENT = "sent"                  # verschickt, Frist läuft
AWAITING_USER = "awaiting_user"  # Webformular/Brief/ID-Nachweis – Nutzer muss handeln
REMINDED = "reminded"          # Erinnerung verschickt, Nachfrist läuft
ESCALATED = "escalated"        # Beschwerdeentwurf an Aufsichtsbehörde erstellt
CONFIRMED = "confirmed"        # Löschung bestätigt
NO_DATA = "no_data"            # Händler hat keine Daten
SUPPRESSED = "suppressed"      # dauerhaft gesperrt (Sperrliste) – keine Wiederholung nötig
REJECTED = "rejected"          # abgelehnt
BOUNCED = "bounced"            # Zustellung fehlgeschlagen

OPEN = (PENDING, SENT, AWAITING_USER, REMINDED, ESCALATED)
DONE = (CONFIRMED, NO_DATA, SUPPRESSED, REJECTED, BOUNCED)
ALL_STATUSES = OPEN + DONE

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    data TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    broker_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    round INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL,
    sent_at TEXT,
    due_at TEXT,
    reminded_at TEXT,
    escalated_at TEXT,
    closed_at TEXT,
    next_round_at TEXT,
    message_id TEXT,
    urls TEXT,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_req_profile_broker ON requests(profile_id, broker_id);
CREATE TABLE IF NOT EXISTS breaches (
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    found TEXT NOT NULL,
    PRIMARY KEY (email, name)
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES requests(id),
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    detail TEXT
);
"""


def home():
    return Path(os.environ.get("DATENPUTZ_HOME", Path.home() / ".datenputz"))


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.isoformat() if dt else None


def parse(s):
    return datetime.fromisoformat(s) if s else None


class Store:
    def __init__(self, path=None):
        self.dir = Path(path) if path else home()
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o700)
        except OSError:
            pass
        self.db = sqlite3.connect(self.dir / "datenputz.db")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # --- Konfiguration -------------------------------------------------
    @property
    def config_path(self):
        return self.dir / "config.json"

    def config(self):
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        return {}

    def save_config(self, cfg):
        self.config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        os.chmod(self.config_path, 0o600)

    # --- Profile -------------------------------------------------------
    def add_profile(self, key, data):
        self.db.execute(
            "INSERT INTO profiles(key, data, created) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
            (key, json.dumps(data, ensure_ascii=False), iso(now())),
        )
        self.db.commit()
        return self.profile(key)

    def profiles(self):
        return [self._profile(r) for r in self.db.execute("SELECT * FROM profiles ORDER BY id")]

    def profile(self, key):
        r = self.db.execute("SELECT * FROM profiles WHERE key = ?", (key,)).fetchone()
        return self._profile(r) if r else None

    def profile_by_id(self, pid):
        r = self.db.execute("SELECT * FROM profiles WHERE id = ?", (pid,)).fetchone()
        return self._profile(r) if r else None

    @staticmethod
    def _profile(r):
        d = json.loads(r["data"])
        d["_id"], d["_key"] = r["id"], r["key"]
        return d

    # --- Anfragen ------------------------------------------------------
    def create_request(self, profile_id, broker_id, kind, channel, round_=1, urls=None):
        cur = self.db.execute(
            "INSERT INTO requests(profile_id, broker_id, kind, channel, status, round, created, urls) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (profile_id, broker_id, kind, channel, PENDING, round_, iso(now()),
             json.dumps(urls) if urls else None),
        )
        self.db.commit()
        self.log(cur.lastrowid, "created", f"Runde {round_}")
        return cur.lastrowid

    def update(self, request_id, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        vals = [iso(v) if isinstance(v, datetime) else v for v in fields.values()]
        self.db.execute(f"UPDATE requests SET {cols} WHERE id = ?", (*vals, request_id))
        self.db.commit()

    def request(self, request_id):
        return self.db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()

    def requests(self, profile_id=None, statuses=None, broker_id=None):
        q, args = "SELECT * FROM requests WHERE 1=1", []
        if profile_id is not None:
            q += " AND profile_id = ?"
            args.append(profile_id)
        if broker_id is not None:
            q += " AND broker_id = ?"
            args.append(broker_id)
        if statuses:
            q += f" AND status IN ({','.join('?' * len(statuses))})"
            args.extend(statuses)
        return self.db.execute(q + " ORDER BY id", args).fetchall()

    def latest(self, profile_id, broker_id):
        return self.db.execute(
            "SELECT * FROM requests WHERE profile_id = ? AND broker_id = ? ORDER BY id DESC LIMIT 1",
            (profile_id, broker_id),
        ).fetchone()

    def find_by_message_id(self, message_id):
        return self.db.execute("SELECT * FROM requests WHERE message_id = ?", (message_id,)).fetchone()

    # --- Ereignisse ----------------------------------------------------
    def log(self, request_id, type_, detail=None):
        self.db.execute(
            "INSERT INTO events(request_id, ts, type, detail) VALUES (?, ?, ?, ?)",
            (request_id, iso(now()), type_, detail),
        )
        self.db.commit()

    def events(self, request_id):
        return self.db.execute("SELECT * FROM events WHERE request_id = ? ORDER BY id", (request_id,)).fetchall()

    def sent_today(self):
        start = now().replace(hour=0, minute=0, second=0).isoformat()
        return self.db.execute(
            "SELECT COUNT(*) FROM events WHERE type IN ('sent', 'reminder_sent') AND ts >= ?", (start,)
        ).fetchone()[0]

    # --- Sicherheit: Leaks und Merkwerte ---------------------------------
    def add_breach(self, email, breach):
        """True, wenn der Leak für diese Adresse neu ist."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO breaches(email, name, data, found) VALUES (?, ?, ?, ?)",
            (email.lower(), breach["Name"], json.dumps(breach, ensure_ascii=False), iso(now())),
        )
        self.db.commit()
        return cur.rowcount == 1

    def breaches(self):
        return [(r["email"], json.loads(r["data"]), r["found"])
                for r in self.db.execute("SELECT * FROM breaches ORDER BY found DESC, email")]

    def set_kv(self, k, v):
        self.db.execute("INSERT INTO kv(k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                        (k, json.dumps(v)))
        self.db.commit()

    def get_kv(self, k, default=None):
        r = self.db.execute("SELECT v FROM kv WHERE k = ?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default
