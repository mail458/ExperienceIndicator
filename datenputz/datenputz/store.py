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
    note TEXT,
    identity TEXT
);
CREATE INDEX IF NOT EXISTS idx_req_profile_broker ON requests(profile_id, broker_id);
CREATE TABLE IF NOT EXISTS breaches (
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    found TEXT NOT NULL,
    PRIMARY KEY (email, name)
);
CREATE TABLE IF NOT EXISTS findings (
    kind TEXT NOT NULL,       -- breach, paste, stealer, infostealer, domain_breach, domain_stealer, alias_leak
    subject TEXT NOT NULL,    -- E-Mail-Adresse bzw. Alias
    key TEXT NOT NULL,        -- Leak-Name, Paste-ID, Website …
    source TEXT NOT NULL,     -- hibp, xposedornot, leakcheck, hudsonrock, inbox
    severity TEXT NOT NULL,   -- kritisch, hoch, mittel, info
    data TEXT NOT NULL,
    found TEXT NOT NULL,
    PRIMARY KEY (kind, subject, key, source)
);
CREATE TABLE IF NOT EXISTS aliases (
    alias TEXT PRIMARY KEY,
    service TEXT NOT NULL,
    related TEXT,
    note TEXT,
    created TEXT NOT NULL
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
        db_path = self.dir / "datenputz.db"
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(requests)")}
        if "identity" not in cols:  # Datenbanken aus Version 0.1/0.2
            self.db.execute("ALTER TABLE requests ADD COLUMN identity TEXT")
        try:  # enthält personenbezogene Daten: nur für den Eigentümer lesbar
            os.chmod(db_path, 0o600)
        except OSError:
            pass
        # Leaks aus Version 0.2 in die allgemeine Fund-Tabelle übernehmen
        self.db.execute(
            "INSERT OR IGNORE INTO findings(kind, subject, key, source, severity, data, found) "
            "SELECT 'breach', email, name, 'hibp', 'mittel', data, found FROM breaches")
        self.db.commit()
        if not self.get_kv("findings_v3"):
            self._upgrade_findings()

    def _upgrade_findings(self):
        """Alte HIBP-Funde (Version 0.2) nachträglich bewerten und mit Maßnahmen versehen."""
        from . import breach  # spät importiert: breach nutzt selbst store
        for r in self.db.execute("SELECT * FROM findings WHERE source = 'hibp' AND kind = 'breach'").fetchall():
            d = json.loads(r["data"])
            if "actions" in d or "Name" not in d:
                continue
            f = breach._breach_finding(r["subject"], d)
            self.db.execute("UPDATE findings SET severity = ?, data = ? WHERE kind = ? AND subject = ? AND key = ? "
                            "AND source = ?", (f["severity"], json.dumps(f, ensure_ascii=False), r["kind"],
                                               r["subject"], r["key"], r["source"]))
        self.set_kv("findings_v3", True)

    def close(self):
        self.db.close()

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
    def create_request(self, profile_id, broker_id, kind, channel, round_=1, urls=None, identity=None):
        """`identity` ersetzt einzelne Profilangaben nur für diese Anfrage (z. B. nur den Alias nennen)."""
        cur = self.db.execute(
            "INSERT INTO requests(profile_id, broker_id, kind, channel, status, round, created, urls, identity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (profile_id, broker_id, kind, channel, PENDING, round_, iso(now()),
             json.dumps(urls) if urls else None, json.dumps(identity) if identity else None),
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

    # --- Sicherheit: Funde, Aliase, Merkwerte -----------------------------
    def add_finding(self, f):
        """Speichert einen Fund (dict mit kind, subject, key, source, severity). True, wenn neu."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO findings(kind, subject, key, source, severity, data, found) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f["kind"], f["subject"].lower(), f["key"], f["source"], f["severity"],
             json.dumps(f, ensure_ascii=False), iso(now())),
        )
        self.db.commit()
        return cur.rowcount == 1

    def findings(self, kind=None, subject=None):
        q, args = "SELECT * FROM findings WHERE 1=1", []
        if kind:
            q += " AND kind = ?"
            args.append(kind)
        if subject:
            q += " AND subject = ?"
            args.append(subject.lower())
        out = []
        for r in self.db.execute(q + " ORDER BY found DESC, subject", args):
            d = json.loads(r["data"])
            d.update(kind=r["kind"], subject=r["subject"], key=r["key"], source=r["source"],
                     severity=r["severity"], found=r["found"])
            out.append(d)
        return out

    def add_breach(self, email, breach):
        """Kompatibilität: HIBP-Leak als Fund speichern."""
        return self.add_finding({"kind": "breach", "subject": email, "key": breach["Name"], "source": "hibp",
                                 "severity": "mittel", **breach})

    def breaches(self):
        return [(f["subject"], f, f["found"]) for f in self.findings("breach") if f["source"] == "hibp"]

    def add_alias(self, alias, service, related=None, note=None):
        self.db.execute(
            "INSERT INTO aliases(alias, service, related, note, created) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(alias) DO UPDATE SET service = excluded.service, related = excluded.related, "
            "note = excluded.note",
            (alias.lower(), service.lower(), ",".join(related or []), note, iso(now())),
        )
        self.db.commit()

    def aliases(self):
        return [dict(r) | {"related": [x for x in (r["related"] or "").split(",") if x]}
                for r in self.db.execute("SELECT * FROM aliases ORDER BY alias")]

    def remove_alias(self, alias):
        cur = self.db.execute("DELETE FROM aliases WHERE alias = ?", (alias.lower(),))
        self.db.commit()
        return cur.rowcount == 1

    def set_kv(self, k, v):
        self.db.execute("INSERT INTO kv(k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                        (k, json.dumps(v)))
        self.db.commit()

    def get_kv(self, k, default=None):
        r = self.db.execute("SELECT v FROM kv WHERE k = ?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default
