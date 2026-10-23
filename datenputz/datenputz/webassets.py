"""Statische Dateien der Web-Oberfläche: Stylesheet, Skript, Service Worker, Manifest, Symbole.

Alles ohne externe Quellen – die Content-Security-Policy erlaubt nur 'self'.
"""
import base64
import json

CSS = r"""
:root{--bg:#f6f6f3;--card:#fff;--fg:#1b1b1d;--mut:#5f5f66;--line:#e3e3de;--acc:#2f6f5e;--acc-ink:#fff;
--good:#2f7d4f;--info:#2f5f9e;--warn:#9a6200;--bad:#b3362d;--series-1:#2a78d6;--grid:#e8e8e3;--shadow:0 1px 2px rgba(0,0,0,.04)}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--card:#1c1c1f;--fg:#ececee;--mut:#a0a0a8;--line:#2e2e33;--acc:#5fb39b;
--acc-ink:#0d1f1a;--good:#5cc085;--info:#7aa7e8;--warn:#e0a640;--bad:#ef7d73;--series-1:#3987e5;--grid:#2a2a2e;--shadow:none}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:inherit;text-underline-offset:2px}code{font:13px ui-monospace,monospace;background:var(--line);padding:1px 5px;border-radius:4px}
.skip{position:absolute;left:-999px;top:8px;background:var(--card);padding:8px 12px;border-radius:8px;z-index:9}.skip:focus{left:8px}
:focus-visible{outline:3px solid var(--series-1);outline-offset:2px;border-radius:6px}
header{background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.bar{max-width:1080px;margin:0 auto;padding:10px 16px;display:flex;gap:20px;align-items:center}
.brand{display:flex;gap:8px;align-items:center;font-weight:700;text-decoration:none}.brand img{width:26px;height:26px;border-radius:7px}
nav.top{display:flex;gap:18px;flex:1;flex-wrap:wrap}nav.top a,.toplinks a{color:var(--mut);text-decoration:none;padding:6px 0;border-bottom:2px solid transparent}
nav.top a[aria-current=page],.toplinks a[aria-current=page]{color:var(--fg);border-color:var(--acc)}
.toplinks{display:flex;gap:16px;margin-left:auto}.toplinks a{display:flex;gap:6px;align-items:center}
.toplinks svg{width:18px;height:18px;flex:none}form h3,.card form h3{margin:22px 0 2px}.badge{background:var(--bad);color:#fff;border-radius:99px;font-size:11px;padding:0 6px;margin-left:4px;vertical-align:1px}
nav.bottom{display:none}
main{max-width:1080px;margin:0 auto;padding:24px 16px 72px}h1{font-size:23px;margin:0 0 4px;letter-spacing:-.01em}h2{font-size:17px;margin:30px 0 10px}
h3{font-size:15px;margin:0 0 6px}.lead{color:var(--mut);margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.tile,.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:var(--shadow)}
.tile .v{font-size:28px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.2}.tile .k{color:var(--mut);font-size:13px}
.tile a{text-decoration:none}.card{margin:12px 0}.card.hero{padding:22px}
.score{display:flex;gap:28px;align-items:center;flex-wrap:wrap}.score ul{margin:6px 0 0;padding-left:18px}
.ring{width:112px;height:112px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--acc) calc(var(--p,0)*1%),var(--line) 0)}
.ring span{background:var(--card);width:88px;height:88px;border-radius:50%;display:grid;place-items:center;font-size:32px;font-weight:700;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);font-weight:600}tr:last-child td{border-bottom:0}
td a{text-decoration:none}td a:hover{text-decoration:underline}.num{font-variant-numeric:tabular-nums;color:var(--mut)}
.sub{color:var(--mut);font-size:13px}.pill{font-size:12px;padding:1px 9px;border-radius:99px;border:1px solid currentColor;white-space:nowrap;display:inline-block}
.good{color:var(--good)}.info{color:var(--info)}.warn{color:var(--warn)}.bad{color:var(--bad)}.muted{color:var(--mut)}
button,.btn,select,input,textarea{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:9px;padding:8px 12px;min-height:40px}
button,.btn{cursor:pointer;display:inline-flex;align-items:center;gap:6px;text-decoration:none;font-weight:500}
button:hover,.btn:hover{border-color:var(--mut)}.primary{background:var(--acc)!important;border-color:var(--acc)!important;color:var(--acc-ink)!important}
.danger{color:var(--bad)}input,select,textarea{width:100%}input[type=checkbox],input[type=radio]{width:auto;min-height:0;accent-color:var(--acc)}
textarea{min-height:150px;font:13px/1.5 ui-monospace,monospace}label{display:block;font-weight:500;margin:12px 0 4px}
label.check{display:flex;gap:10px;align-items:flex-start;font-weight:400}.hint{color:var(--mut);font-size:13px;margin:4px 0 0}
.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:0 16px}
form.inline{display:inline-flex;gap:6px;margin:0}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.row.end{justify-content:flex-end}
.spread{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}.tabs a{padding:6px 12px;border-radius:99px;border:1px solid var(--line);text-decoration:none;color:var(--mut);background:var(--card)}
.tabs a[aria-current=page]{color:var(--fg);border-color:var(--acc);font-weight:600}
.job{padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:var(--card);margin-bottom:16px}
.job pre{margin:8px 0 0;white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace;max-height:260px;overflow:auto}
.toast{position:fixed;right:16px;bottom:16px;background:var(--fg);color:var(--bg);padding:12px 16px;border-radius:10px;z-index:20;max-width:420px;box-shadow:0 6px 24px rgba(0,0,0,.2)}
ul.plain{list-style:none;padding:0;margin:0}ul.plain>li{padding:10px 0;border-bottom:1px solid var(--line)}ul.plain>li:last-child{border:0}
.done-item{opacity:.55}.done-item .t{text-decoration:line-through}
.steps{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px;padding:0;list-style:none}
.steps a{display:flex;gap:8px;align-items:center;padding:6px 12px 6px 6px;border-radius:99px;border:1px solid var(--line);background:var(--card);text-decoration:none;color:var(--mut)}
.steps a[aria-current=step]{color:var(--fg);border-color:var(--acc);font-weight:600}
.steps .n{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:var(--line);font-size:12px;font-weight:700;color:var(--fg)}
.steps .ok .n{background:var(--acc);color:var(--acc-ink)}
.progress{height:8px;background:var(--line);border-radius:99px;overflow:hidden;margin:6px 0 16px}.progress span{display:block;height:100%;width:var(--w,0);background:var(--acc)}
.focus-card{max-width:760px}.focus-card .kind{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);font-weight:600}
.focus-card h2{margin:4px 0 8px;font-size:20px}.big{font-size:16px;padding:10px 18px;min-height:46px}
.timeline{list-style:none;margin:0;padding:0 0 0 18px;border-left:2px solid var(--line)}
.timeline li{position:relative;padding:0 0 14px 12px}.timeline li::before{content:"";position:absolute;left:-25px;top:6px;width:10px;height:10px;border-radius:50%;background:var(--card);border:2px solid var(--acc)}
.timeline time{color:var(--mut);font-size:13px;font-variant-numeric:tabular-nums;display:block}
.chart-box{position:relative}.chart{width:100%;height:auto;display:block;touch-action:pan-y}
.chart .gridline{stroke:var(--grid);stroke-width:1}.chart .axis{fill:var(--mut);font-size:11px}
.chart .line{fill:none;stroke:var(--series-1);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .pt{fill:var(--series-1);stroke:var(--card);stroke-width:2}.chart .xh{stroke:var(--mut);stroke-width:1;opacity:0}
.chart .focus{fill:var(--series-1);stroke:var(--card);stroke-width:2;opacity:0}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:13px;box-shadow:0 4px 16px rgba(0,0,0,.12);opacity:0;white-space:nowrap}
.tip b{font-variant-numeric:tabular-nums}.qr{background:#fff;padding:8px;border-radius:10px;display:inline-block;line-height:0}.qr svg{width:220px;height:220px}
details>summary{cursor:pointer;font-weight:500}details[open]>summary{margin-bottom:8px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.mb{margin-bottom:12px}
a.tile{text-decoration:none;color:inherit;display:block}a.tile:hover,a.card:hover{border-color:var(--mut)}a.card{text-decoration:none;color:inherit}
.pager{display:flex;gap:8px;justify-content:center;margin:14px 0}.empty{text-align:center;padding:40px 16px}
.empty .big-icon{font-size:40px}.login{max-width:460px;margin:12vh auto}
@media (max-width:720px){
 nav.top,.toplinks .label{display:none}.bar{padding:8px 16px}
 nav.bottom{display:grid;grid-template-columns:repeat(5,1fr);position:fixed;bottom:0;left:0;right:0;background:var(--card);
  border-top:1px solid var(--line);z-index:6;padding:4px 0 calc(4px + env(safe-area-inset-bottom))}
 nav.bottom a{display:flex;flex-direction:column;align-items:center;gap:2px;font-size:11px;color:var(--mut);text-decoration:none;padding:6px 0;min-height:48px}
 nav.bottom a[aria-current=page]{color:var(--acc);font-weight:600}nav.bottom svg{width:22px;height:22px}
 main{padding:18px 16px calc(96px + env(safe-area-inset-bottom))}.toast{left:16px;right:16px;bottom:84px}
 .ring{width:96px;height:96px}.ring span{width:76px;height:76px;font-size:28px}th,td{padding:9px 10px}
 .hide-sm{display:none}.chart .axis{font-size:28px}.chart .pt{r:9}.chart .focus{r:13}.chart{min-height:150px}
}
@media (forced-colors:active){.chart .line{stroke:CanvasText}.pill{border:1px solid CanvasText}}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""

JS = r"""
(function(){
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>Array.from(r.querySelectorAll(s));
function toast(t){let el=$('#toast');if(!el){el=document.createElement('div');el.id='toast';el.className='toast';
 el.setAttribute('role','status');document.body.appendChild(el);}el.textContent=t;el.hidden=false;clearTimeout(el._t);el._t=setTimeout(()=>el.hidden=true,5000);}
const flash=$('#toast');if(flash&&!flash.hidden){flash._t=setTimeout(()=>flash.hidden=true,6000);}
$$('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{const t=document.getElementById(b.dataset.copy);
 try{await navigator.clipboard.writeText(t.value||t.textContent);}catch(e){t.select&&t.select();document.execCommand('copy');}
 b.textContent='Kopiert ✓';toast('In die Zwischenablage kopiert');}));
$$('form[data-confirm]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm(f.dataset.confirm))e.preventDefault();}));
$$('.ring[data-p]').forEach(r=>r.style.setProperty('--p',r.dataset.p));
$$('.progress[data-w]').forEach(p=>p.firstElementChild.style.setProperty('--w',p.dataset.w+'%'));
const sel=$('select[data-presets]');
if(sel){const P=JSON.parse(sel.dataset.presets);sel.addEventListener('change',()=>{const p=P[sel.value];if(!p)return;
 for(const k in p){const i=document.getElementsByName(k)[0];if(i)i.value=p[k];}$('#preset-hint').textContent=p.hint||'';});}
const job=$('#job');
if(job&&job.dataset.running==='1'){const log=$('#job pre'),st=$('#job .state');
 const poll=async()=>{try{const r=await fetch('/job.json',{credentials:'same-origin',cache:'no-store'});const j=await r.json();
  log.textContent=j.log.join('\n');log.scrollTop=log.scrollHeight;
  if(j.running){setTimeout(poll,1500);}else{st.textContent='fertig';toast(j.title+': fertig');setTimeout(()=>location.reload(),900);}}
  catch(e){setTimeout(poll,4000);}};setTimeout(poll,1200);}
$$('svg.chart[data-points]').forEach(svg=>{const pts=JSON.parse(svg.dataset.points);if(!pts.length)return;
 const box=svg.parentElement,tip=box.querySelector('.tip'),xh=svg.querySelector('.xh'),dot=svg.querySelector('.focus');let cur=pts.length-1;
 function show(i){cur=i;const p=pts[i];xh.setAttribute('x1',p.x);xh.setAttribute('x2',p.x);xh.style.opacity=1;
  dot.setAttribute('cx',p.x);dot.setAttribute('cy',p.y);dot.style.opacity=1;tip.innerHTML='';const d=document.createElement('div');d.textContent=p.label;
  const b=document.createElement('b');b.textContent=p.value;tip.append(d,b);const r=svg.getBoundingClientRect(),s=r.width/svg.viewBox.baseVal.width;
  let left=p.x*s+12;if(left+tip.offsetWidth>r.width)left=p.x*s-tip.offsetWidth-12;tip.style.left=left+'px';tip.style.top=Math.max(0,p.y*s-40)+'px';tip.style.opacity=1;}
 function hide(){xh.style.opacity=0;dot.style.opacity=0;tip.style.opacity=0;}
 svg.addEventListener('pointermove',e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)*svg.viewBox.baseVal.width/r.width;
  let best=0;pts.forEach((p,i)=>{if(Math.abs(p.x-x)<Math.abs(pts[best].x-x))best=i;});show(best);});
 svg.addEventListener('pointerleave',hide);svg.addEventListener('blur',hide);svg.addEventListener('focus',()=>show(cur));
 svg.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'){show(Math.max(0,cur-1));e.preventDefault();}
  if(e.key==='ArrowRight'){show(Math.min(pts.length-1,cur+1));e.preventDefault();}});});
if('serviceWorker' in navigator&&window.isSecureContext){navigator.serviceWorker.register('/sw.js').catch(()=>{});}
})();
"""

SERVICE_WORKER = r"""
// Nur die App-Hülle wird zwischengespeichert – nie Seiten mit persönlichen Daten.
const CACHE='datenputz-v1',SHELL=['/static/app.css','/static/app.js','/static/icon-192.png','/offline'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));self.skipWaiting();});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==CACHE).map(x=>caches.delete(x)))));self.clients.claim();});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==location.origin)return;
 if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).catch(()=>caches.match('/offline')));return;}
 if(SHELL.includes(u.pathname)){e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));}});
"""

MANIFEST = json.dumps({
    "name": "Datenputz", "short_name": "Datenputz", "lang": "de",
    "description": "Persönliche Daten löschen lassen, Leaks überwachen, Schutz im Blick.",
    "start_url": "/heute", "scope": "/", "display": "standalone",
    "background_color": "#f6f6f3", "theme_color": "#2f6f5e",
    "icons": [
        {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/static/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}, ensure_ascii=False)

# Linien-Symbole (24×24, stroke = currentColor) für die Navigation
_I = {
    "heute": '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    "uebersicht": '<path d="M3 13h8V3H3zM13 21h8v-8h-8zM13 3v6h8V3zM3 21h8v-4H3z"/>',
    "anfragen": '<path d="M4 4h16v16H4z"/><path d="M4 9h16M9 4v16"/>',
    "leaks": '<path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z"/><path d="M12 8v5M12 16h.01"/>',
    "pruefen": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "system": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "einrichten": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
}


def icon(name):
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" focusable="false">{_I[name]}</svg>')


ICONS = {
    "icon-192": (
        "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"
        "AAAASUVORK5CYII="
    ),
    "icon-512": (
        "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"
    ),
    "maskable-512": (
        "iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAYAAAD0eNT6AAArlElEQVR42u3deXRc9X338c/vd+/MaGakkeQFOwEcDJhgs5iwmhBK"
        "Sts0J2mWkpPnaXOapAmhTxPnsJwTCDzQFDh1Gxqb7YkBYUTsAMYUCqIGgs3qgPGGwRsSCG/ybmNL1joaae69zx8zI8u2TGyQNKPR"
        "+5WT9Jw0oXQsze997/39vtdMvuYHgQAAwLBi+QgAACAAAAAAAQAAAAgAAABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAAAABAAAA"
        "CAAAAEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAIAAAAAABAAAACAAAAEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAAAEAAAAI"
        "AAAAQAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAgAAAAAAEAAAAIAAAAQAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAAAQAAAAgA"
        "AABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAACAAAAAAAQAAAAgAAABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAAAABAAAACAAA"
        "AEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAIAAAAAABAAAACAAAAEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAAAEAAAAIAAAA"
        "QAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAgAPgIAAAgAAAAAAEAAAAIAAAAQAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAAAQAA"
        "AAgAAABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAACAAAAAAAQAAAAgAAABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAAAABAAAA"
        "CAAAAEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAIAAAAAABAAAACAAAAEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAAAEAAAAI"
        "AAAAQAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAgAAAAAAEAAAAIAAAAQAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAAAQAAAAgA"
        "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"
        "AABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAAAABAAAACAAAAAgAAABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAAAABAAAACAAA"
        "AEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAAAEAAAAIAAAACAAAAEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAAAEAAAAIAAAA"
        "QAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAAAQAAAAgAAABAAAAAQAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAAAQAAAAgAAABA"
        "AAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAAAABAAAACAAAAEAAAABAAAAAAAIAAAAQAAAAgAAAAAAEAAAAIAAAAAABAAAACAAAAEAA"
        "AAAAAgAAABAAAACAAAAAAAQAAAAgAAAAAAEAAAAIAAAAQAAAAEAAAAAAAgAAABAAAACAAAAAAAQAAAAgAAAAAAEAAAAIAAAAQAAA"
        "AAACAAAAEAAAAIAAAAAABAAAACAAAAAAAQAAAAgAAABAAAAAQAAAAAACAAAAEAAAAIAAAAAABAAAACAAAAAAAQAAAAgAAABAAAAA"
        "AAIAAAAQAAAAgAAAAAD95f8DB2UsxM9Yi/gAAAAASUVORK5CYII="
    ),
    "apple-180": (
        "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"
    ),
}


def png(name):
    return base64.b64decode("".join(ICONS[name]))
