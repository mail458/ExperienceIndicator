"""Dashboard als eigenständige HTML-Datei (wie Incognis Fortschrittsübersicht)."""
import html
import json
from collections import Counter

from . import store as S

LABEL = {
    S.PENDING: "geplant", S.SENT: "versendet", S.AWAITING_USER: "Aktion nötig", S.REMINDED: "erinnert",
    S.ESCALATED: "Beschwerde", S.CONFIRMED: "gelöscht", S.NO_DATA: "keine Daten", S.SUPPRESSED: "gesperrt",
    S.REJECTED: "abgelehnt", S.BOUNCED: "unzustellbar",
}
KIND = {"erasure": "Löschung", "access": "Auskunft", "ccpa_delete": "CCPA-Löschung"}
TONE = {
    S.PENDING: "muted", S.SENT: "info", S.AWAITING_USER: "warn", S.REMINDED: "warn", S.ESCALATED: "bad",
    S.CONFIRMED: "good", S.NO_DATA: "good", S.SUPPRESSED: "good", S.REJECTED: "bad", S.BOUNCED: "bad",
}


def rows(store, broker_index):
    """Pro Profil und Händler nur die neueste Anfrage."""
    latest = {}
    for r in store.requests():
        latest[(r["profile_id"], r["broker_id"])] = r
    out = []
    for (pid, bid), r in latest.items():
        b = broker_index.get(bid, {"name": bid})
        out.append({"r": r, "b": b, "p": store.profile_by_id(pid)})
    return sorted(out, key=lambda x: (x["p"]["name"], x["b"]["name"].lower()))


def summary(items):
    c = Counter(x["r"]["status"] for x in items)
    done = c[S.CONFIRMED] + c[S.NO_DATA] + c[S.SUPPRESSED]
    return c, done


def _d(s):
    return S.parse(s).strftime("%d.%m.%Y") if s else ""


def security(store):
    """Kacheln und Liste für Dark-Web-Monitor, DNS-Filter und VPN (leer, wenn nichts genutzt wird)."""
    from . import shield, vpn
    tiles, items = [], []
    found = store.breaches()
    last = store.get_kv("breach_last_check")
    if found or last:
        tiles.append(("Datenlecks", len(found)))
        for email, b, _ in found[:12]:
            items.append(f"<li><b>{html.escape(b.get('Title', b['Name']))}</b> ({html.escape(b.get('BreachDate', ''))}) – "
                         f"{html.escape(email)}: {html.escape(', '.join(b.get('DataClasses', [])[:5]))}</li>")
    stats = shield.folder() / "stats.json"
    if stats.exists():
        st = json.loads(stats.read_text())
        tiles.append(("DNS-Anfragen blockiert", st["blocked"]))
    v = vpn.load()
    if v:
        tiles.append(("VPN-Geräte", len(v["peers"])))
    if not tiles:
        return ""
    tile_html = "".join(f'<div class="tile"><div class="v">{n}</div><div class="k">{k}</div></div>' for k, n in tiles)
    note = f'<p class="lead">Letzte Leak-Prüfung: {_d(last)}</p>' if last else ""
    lst = f'<ul class="leaks">{"".join(items)}</ul>' if items else ""
    return f'<h2>Sicherheit</h2>{note}<div class="tiles">{tile_html}</div>{lst}<h2>Datenhändler</h2>'


def render(store, broker_index):
    items = rows(store, broker_index)
    c, done = summary(items)
    total = len(items) or 1
    now = S.now()
    overdue = sum(1 for x in items if x["r"]["status"] in (S.SENT, S.REMINDED)
                  and x["r"]["due_at"] and S.parse(x["r"]["due_at"]) < now)
    tiles = [
        ("Händler erfasst", len(items)), ("Erledigt", done),
        ("Warten auf Antwort", c[S.SENT] + c[S.REMINDED]), ("Aktion nötig", c[S.AWAITING_USER]),
        ("Überfällig", overdue), ("Beschwerden", c[S.ESCALATED]),
    ]
    tr = []
    for x in items:
        r, b, p = x["r"], x["b"], x["p"]
        link = b.get("webform") or b.get("web") or ""
        name = html.escape(b["name"])
        name = f'<a href="{html.escape(link)}" target="_blank" rel="noopener">{name}</a>' if link else name
        tr.append(
            f'<tr data-status="{r["status"]}"><td>{name}<div class="sub">{html.escape(", ".join(b.get("categories", [])))}</div></td>'
            f'<td>{html.escape(p["name"])}</td><td>{KIND.get(r["kind"], r["kind"])}</td><td>{r["round"]}</td>'
            f'<td><span class="pill {TONE[r["status"]]}">{LABEL[r["status"]]}</span></td>'
            f'<td>{_d(r["sent_at"])}</td><td>{_d(r["due_at"]) if r["status"] in S.OPEN else ""}</td>'
            f'<td>{_d(r["next_round_at"])}</td><td class="num">#{r["id"]}</td></tr>'
        )
    options = "".join(f'<option value="{k}">{v} ({c[k]})</option>' for k, v in LABEL.items() if c[k])
    tile_html = "".join(f'<div class="tile"><div class="v">{v}</div><div class="k">{k}</div></div>' for k, v in tiles)
    pct = round(100 * done / total)
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Datenputz Übersicht</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --fg:#1d1d1f; --mut:#6b6b70; --line:#e4e4e0; --acc:#2f6f5e;
  --good:#2f7d4f; --info:#2f5f9e; --warn:#a86a00; --bad:#b3362d; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141416; --card:#1d1d20; --fg:#ececee; --mut:#9a9aa2;
  --line:#2e2e33; --acc:#5fb39b; --good:#5cc085; --info:#7aa7e8; --warn:#e0a640; --bad:#ec7a70; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif }}
main {{ max-width:1100px; margin:0 auto; padding:32px 16px 64px }}
h1 {{ font-size:24px; margin:0 0 4px }} h2 {{ font-size:17px; margin:28px 0 10px }}
.leaks {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px 12px 32px; margin:0 0 8px }}
.leaks li {{ margin:4px 0 }} .lead {{ color:var(--mut); margin:0 0 24px }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:20px }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px }}
.tile .v {{ font-size:26px; font-weight:650; font-variant-numeric:tabular-nums }} .tile .k {{ color:var(--mut); font-size:13px }}
.bar {{ height:10px; background:var(--line); border-radius:99px; overflow:hidden; margin:4px 0 24px }}
.bar span {{ display:block; height:100%; width:{pct}%; background:var(--acc) }}
.tools {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px }}
input,select {{ font:inherit; padding:7px 10px; border:1px solid var(--line); border-radius:8px; background:var(--card); color:var(--fg) }}
input {{ flex:1; min-width:180px }}
.wrap {{ overflow-x:auto; background:var(--card); border:1px solid var(--line); border-radius:10px }}
table {{ border-collapse:collapse; width:100%; min-width:760px }}
th,td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:top }}
th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--mut); font-weight:600 }}
tr:last-child td {{ border-bottom:0 }} td.num {{ color:var(--mut); font-variant-numeric:tabular-nums }}
.sub {{ color:var(--mut); font-size:12px }} a {{ color:inherit; text-decoration-color:var(--line) }}
.pill {{ font-size:12px; padding:2px 8px; border-radius:99px; border:1px solid currentColor; white-space:nowrap }}
.good {{ color:var(--good) }} .info {{ color:var(--info) }} .warn {{ color:var(--warn) }} .bad {{ color:var(--bad) }} .muted {{ color:var(--mut) }}
</style></head><body><main>
<h1>Datenputz</h1>
<p class="lead">Stand {now.strftime('%d.%m.%Y %H:%M')} UTC · {pct}% der erfassten Händler erledigt</p>
{security(store)}<div class="tiles">{tile_html}</div>
<div class="bar" role="img" aria-label="{pct}% erledigt"><span></span></div>
<div class="tools"><input id="q" placeholder="Händler oder Person suchen…" aria-label="Suche">
<select id="st" aria-label="Status"><option value="">Alle Status</option>{options}</select></div>
<div class="wrap"><table><thead><tr><th>Händler</th><th>Person</th><th>Art</th><th>Runde</th><th>Status</th>
<th>Versendet</th><th>Frist</th><th>Nächste Runde</th><th>ID</th></tr></thead><tbody id="tb">{''.join(tr)}</tbody></table></div>
</main><script>
const q=document.getElementById('q'), st=document.getElementById('st');
function f(){{const t=q.value.toLowerCase(), s=st.value;
for(const r of document.querySelectorAll('#tb tr')){{r.hidden=!(r.textContent.toLowerCase().includes(t)&&(!s||r.dataset.status===s));}}}}
q.oninput=f; st.onchange=f;
</script></body></html>
"""
