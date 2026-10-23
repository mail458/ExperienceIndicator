"""Privatsphäre-Wert (0–100) und sein Verlauf über die Zeit."""
import hashlib

from . import breach as BR
from . import brokers as B
from . import report as R
from . import shield as SH
from . import store as S
from . import vpn as V

HISTORY_DAYS = 400


def plan_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def open_serious(st, findings=None):
    """Ernste Funde (kritisch/hoch), deren Maßnahmen noch nicht abgehakt sind."""
    done = set(st.get_kv("plan_done", []))
    return [f for f in (findings if findings is not None else st.findings())
            if BR.RANK[f["severity"]] <= BR.RANK["hoch"]
            and not all(plan_hash(t) in done for _, t in f.get("actions", []))]


def privacy_score(st, items=None, findings=None):
    """(wert, [(bereich, gewicht, anteil)], [tipps])."""
    items = items if items is not None else R.rows(st, B.by_id())
    findings = findings if findings is not None else st.findings()
    parts, tips = [], []
    _, done = R.summary(items)
    parts.append(("Datenhändler", 40, done / len(items) if items else 0))
    if not items:
        tips.append("Löschanträge planen (Einrichten → Profil)")
    serious = open_serious(st, findings)
    checked = bool(findings or st.get_kv("breach_last_check"))
    parts.append(("Leaks bearbeitet", 30, 1 / (1 + len(serious) / 3) if checked else 0))
    if not checked:
        tips.append("Leak-Prüfung einrichten (Einrichten → Leak-Quellen)")
    elif serious:
        tips.append(f"{len(serious)} ernste Leak-Funde abarbeiten (Heute)")
    va = st.get_kv("vault_audit")
    parts.append(("Passwörter", 15, (1 - (va["kritisch"] + va["hoch"]) / max(1, va["total"])) if va else 0))
    if not va:
        tips.append("Passwörter prüfen: `breach vault export.csv --shred`")
    prot = sum([bool(st.get_kv("schedule")), bool(st.config().get("notify", {}).get("channels")),
                (SH.folder() / "blocklist.txt").exists(), bool(V.load())]) / 4
    parts.append(("Schutz aktiv", 15, prot))
    if prot < 1:
        tips.append("Automatik, Benachrichtigung, DNS-Filter oder VPN einrichten")
    return round(sum(w * v for _, w, v in parts)), parts, tips


def record(st):
    """Tageswert speichern (ein Eintrag pro Tag, der neueste gewinnt)."""
    items = R.rows(st, B.by_id())
    findings = st.findings()
    score, _, _ = privacy_score(st, items, findings)
    _, done = R.summary(items)
    today = S.now().date().isoformat()
    hist = [h for h in st.get_kv("history", []) if h["d"] != today]
    hist.append({"d": today, "score": score, "done": done, "total": len(items),
                 "serious": len(open_serious(st, findings))})
    st.set_kv("history", sorted(hist, key=lambda h: h["d"])[-HISTORY_DAYS:])
    return score
