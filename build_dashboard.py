#!/usr/bin/env python3
"""
Build a self-contained executive dashboard.html from the latest prices CSV.
Open it in any browser — no server needed, works offline.

Sections:
  1. Market overview  — KPI cards + competitor positioning (coverage, $/GB, badges)
  2. Country drill-down — pick a country: KPIs + per-competitor scorecard
  3. Smart comparison table — Data/Days/$ per GB/competitors/cheapest, filters + sort
"""
import csv
import glob
import json
import os
import re
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def latest_csv():
    files = sorted(glob.glob(os.path.join(DATA, "prices_*.csv")))
    return files[-1] if files else None


def gb_of(data):
    if data == "Unlimited":
        return None
    m = re.match(r"([\d.]+)\s*GB", data)
    return float(m.group(1)) if m else None


def main():
    src = latest_csv()
    if not src:
        print("No data CSV found — run collect.py first.")
        return
    raw = list(csv.DictReader(open(src)))

    recs = []
    for r in raw:
        days = r["days"]
        days = int(days) if str(days).isdigit() else None
        try:
            price = float(r["price_usd"])
        except ValueError:
            continue
        g = gb_of(r["data"])
        recs.append({"co": r["competitor"], "c": r["country"], "d": r["data"],
                     "n": days, "p": price, "g": g})

    competitors = sorted(set(x["co"] for x in recs))
    countries = sorted(set(x["c"] for x in recs))
    total = len(recs)

    # freshness
    fresh = {}
    for r in raw:
        c, d = r["competitor"], r["date"]
        if c not in fresh or d > fresh[c]:
            fresh[c] = d
    newest = max(fresh.values()) if fresh else ""
    stale = {c: d for c, d in fresh.items() if d < newest}

    # ---------- market analytics ----------
    per = {c: {"countries": set(), "plans": 0, "rates": [], "unlim7": [],
               "gbLeader": 0, "unlimLeader": 0} for c in competitors}
    # best $/GB and cheapest 7d-unlimited per (country, competitor)
    best_gb = {}      # country -> {comp: min $/GB}
    best_u7 = {}      # country -> {comp: min 7d-unlimited price}
    for r in recs:
        p = per[r["co"]]
        p["countries"].add(r["c"])
        p["plans"] += 1
        if r["g"]:
            rate = r["p"] / r["g"]
            p["rates"].append(rate)
            d = best_gb.setdefault(r["c"], {})
            if r["co"] not in d or rate < d[r["co"]]:
                d[r["co"]] = rate
        if r["d"] == "Unlimited" and r["n"] == 7:
            p["unlim7"].append(r["p"])
            d = best_u7.setdefault(r["c"], {})
            if r["co"] not in d or r["p"] < d[r["co"]]:
                d[r["co"]] = r["p"]
    for country, cm in best_gb.items():
        if cm:
            per[min(cm, key=cm.get)]["gbLeader"] += 1
    for country, cm in best_u7.items():
        if cm:
            per[min(cm, key=cm.get)]["unlimLeader"] += 1

    perComp = {}
    for c in competitors:
        p = per[c]
        # median $/GB is robust to small-plan outliers (1GB plans skew the mean up)
        avg = round(st.median(p["rates"]), 2) if p["rates"] else None
        u7 = round(st.median(p["unlim7"]), 2) if p["unlim7"] else None
        perComp[c] = {"countries": len(p["countries"]), "plans": p["plans"],
                      "avgGB": avg, "unlim7": u7,
                      "gbLeader": p["gbLeader"], "unlimLeader": p["unlimLeader"]}
    # badges by avg $/GB tercile
    ranked = sorted([c for c in competitors if perComp[c]["avgGB"] is not None],
                    key=lambda c: perComp[c]["avgGB"])
    n = len(ranked) or 1
    maxAvg = max((perComp[c]["avgGB"] for c in ranked), default=1) or 1
    for i, c in enumerate(ranked):
        t = i / n
        perComp[c]["badge"] = "Budget" if t < 1/3 else ("Mid" if t < 2/3 else "Premium")
        perComp[c]["barPct"] = round(perComp[c]["avgGB"] / maxAvg * 100)
    for c in competitors:
        perComp[c].setdefault("badge", "Unlimited-only")
        perComp[c].setdefault("barPct", 0)

    leaders = {
        "coverage": max(competitors, key=lambda c: perComp[c]["countries"]),
        "value": (min(ranked, key=lambda c: perComp[c]["avgGB"]) if ranked else None),
        "gbLeader": max(competitors, key=lambda c: perComp[c]["gbLeader"]),
        "unlimLeader": max(competitors, key=lambda c: perComp[c]["unlimLeader"]),
    }

    payload = json.dumps({
        "date": newest, "competitors": competitors, "countries": countries,
        "recs": recs, "total": total, "stale": stale,
        "market": {"perComp": perComp, "leaders": leaders},
    }, separators=(",", ":"))

    html = TEMPLATE.replace("__PAYLOAD__", payload)
    out = os.path.join(HERE, "dashboard.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"Dashboard built: {out}  ({total} packages, {len(countries)} countries)")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>eSIM Competitor Intelligence</title>
<style>
  :root{
    --bg:#0e1120; --panel:#171c2e; --panel2:#1f2740; --line:#2b3352;
    --text:#eaedf7; --muted:#98a1c0; --accent:#5b8cff; --accent2:#8b5cf6;
    --low:#12321f; --lowtx:#54e39a; --mid:#3a3212; --midtx:#e6c34d;
    --high:#3a1620; --hightx:#ff8098; --barlo:#3bd07f; --barhi:#ff6b81;
  }
  @media (prefers-color-scheme: light){
    :root{ --bg:#f5f7fc; --panel:#ffffff; --panel2:#f1f4fb; --line:#e4e9f4;
      --text:#151b2e; --muted:#5a647f; --accent:#2f6bff; --accent2:#7c3aed;
      --low:#e2f8ec; --lowtx:#0a7d47; --mid:#fbf3d8; --midtx:#9a7b12;
      --high:#fdeaee; --hightx:#c22b48; --barlo:#16a866; --barhi:#e0455f; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  .wrap{max-width:1240px;margin:0 auto;padding:0 22px 70px}
  header{padding:26px 22px 10px;max-width:1240px;margin:0 auto}
  h1{margin:0;font-size:21px;font-weight:800;letter-spacing:-.3px}
  h2{font-size:13px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;
    color:var(--muted);margin:30px 0 12px;display:flex;align-items:center;gap:8px}
  h2::after{content:"";flex:1;height:1px;background:var(--line)}
  .sub{color:var(--muted);font-size:12.5px;margin-top:4px}
  .warn{color:var(--hightx)}
  /* KPI cards */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:11px}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 15px;
    position:relative;overflow:hidden}
  .kpi .lab{color:var(--muted);font-size:11.5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
  .kpi .val{font-size:22px;font-weight:800;margin-top:3px;letter-spacing:-.5px}
  .kpi .sub2{color:var(--muted);font-size:12px;margin-top:1px}
  .kpi.hl{background:linear-gradient(135deg,var(--panel),var(--panel2))}
  .kpi.hl .val{color:var(--accent)}
  /* generic card + table */
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
  .scroll{overflow-x:auto}
  table{border-collapse:collapse;width:100%;font-size:13.5px}
  th,td{padding:9px 12px;text-align:right;white-space:nowrap}
  th.l,td.l{text-align:left}
  thead th{background:var(--panel2);color:var(--muted);font-weight:600;position:sticky;top:0;
    border-bottom:1px solid var(--line);cursor:pointer;user-select:none;z-index:2}
  thead th:hover{color:var(--text)}
  thead th.sorted{color:var(--accent)} .arw{font-size:9px;margin-left:3px}
  th:first-child,td:first-child{position:sticky;left:0;background:var(--panel)}
  thead th:first-child{background:var(--panel2);z-index:3}
  tbody tr{border-bottom:1px solid var(--line)}
  tbody tr:last-child{border-bottom:0}
  tbody tr:hover td{background:var(--panel2)}
  tbody tr:hover td:first-child{background:var(--panel2)}
  .num{font-variant-numeric:tabular-nums}
  td.price{font-variant-numeric:tabular-nums;font-weight:600}
  td.na{color:var(--muted);font-weight:400}
  td.low{background:var(--low);color:var(--lowtx)}
  td.high{color:var(--hightx)}
  .badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700}
  .b-Budget{background:var(--low);color:var(--lowtx)}
  .b-Mid{background:var(--mid);color:var(--midtx)}
  .b-Premium{background:var(--high);color:var(--hightx)}
  .b-Unlimited-only{background:var(--panel2);color:var(--muted)}
  .bar{height:7px;border-radius:4px;background:var(--panel2);min-width:70px;overflow:hidden;display:inline-block;vertical-align:middle;width:90px}
  .bar > i{display:block;height:100%;border-radius:4px}
  .win{color:var(--lowtx);font-weight:700}
  /* controls */
  .controls{display:flex;gap:13px;flex-wrap:wrap;align-items:flex-end;margin:6px 0 4px}
  .ctl{display:flex;flex-direction:column}
  label{color:var(--muted);font-size:11.5px;margin-bottom:5px}
  select,input{background:var(--panel);color:var(--text);border:1px solid var(--line);
    border-radius:10px;padding:8px 11px;font-size:14px;outline:none;min-width:135px}
  select:focus,input:focus{border-color:var(--accent)}
  select[multiple]{min-width:145px;padding:4px}
  .chips{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0}
  .chip{background:var(--panel);color:var(--muted);border:1px solid var(--line);border-radius:999px;
    padding:5px 12px;font-size:12.5px;cursor:pointer;user-select:none}
  .chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
  .chip.co.on{background:var(--accent2);border-color:var(--accent2)}
  .reset{margin-left:auto;color:var(--accent);background:none;border:0;cursor:pointer;font-size:12.5px}
  .count{color:var(--muted);font-size:12px;margin:9px 2px}
  .empty{padding:36px;text-align:center;color:var(--muted)}
  .legend{display:flex;gap:15px;flex-wrap:wrap;color:var(--muted);font-size:11.5px;margin-top:11px}
  .sw{display:inline-block;width:11px;height:11px;border-radius:3px;vertical-align:middle;margin-right:4px}
  .scoregrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:11px}
  .sc{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
  .sc .co{font-weight:800;font-size:15px}
  .sc .row{display:flex;justify-content:space-between;font-size:12.5px;color:var(--muted);margin-top:6px}
  .sc .row b{color:var(--text);font-variant-numeric:tabular-nums}
</style>
</head>
<body>
<header>
  <h1>eSIM Competitor Intelligence</h1>
  <div class="sub" id="sub"></div>
</header>
<div class="wrap">

  <h2>Market Overview</h2>
  <div class="kpis" id="mkpis"></div>

  <h2>Competitor Positioning</h2>
  <div class="card scroll"><table id="posTbl"></table></div>
  <div class="legend">
    <span><span class="sw" style="background:var(--barlo)"></span>düşük $/GB (uygun)</span>
    <span><span class="sw" style="background:var(--barhi)"></span>yüksek $/GB (pahalı)</span>
    <span><span class="badge b-Budget">Budget</span> / <span class="badge b-Mid">Mid</span> / <span class="badge b-Premium">Premium</span> = ortalama $/GB'a göre konum</span>
  </div>

  <h2>Country Drill-down</h2>
  <div class="controls">
    <div class="ctl"><label>Country / destination</label>
      <input id="search" placeholder="type to search…" autocomplete="off">
      <select id="country"></select>
    </div>
  </div>
  <div class="kpis" id="ckpis" style="margin-top:6px"></div>
  <div class="scoregrid" id="score" style="margin-top:12px"></div>

  <h2>Detailed Price Comparison</h2>
  <div class="controls">
    <div class="ctl"><label>Data size (⌘/Ctrl-click)</label>
      <select id="size" multiple size="4"></select></div>
    <div class="ctl"><label>Validity (days)</label><select id="days"></select></div>
    <button class="reset" id="reset">Reset</button>
  </div>
  <label style="color:var(--muted);font-size:11.5px">Competitors (tıkla: göster/gizle)</label>
  <div class="chips" id="cochips"></div>
  <label style="color:var(--muted);font-size:11.5px">Data size (çoklu)</label>
  <div class="chips" id="sizechips"></div>
  <div class="card scroll"><table id="tbl"></table></div>
  <div class="count" id="count"></div>
  <div class="legend">
    <span><span class="sw" style="background:var(--lowtx)"></span>satırda en ucuz</span>
    <span><span class="sw" style="background:var(--hightx)"></span>en pahalı</span>
    <span>$/GB = fiyat ÷ GB (sadece GB planları)</span>
    <span>🏆 = o satırın en ucuz firması</span>
  </div>
</div>

<script>
const D = __PAYLOAD__;
const $ = s => document.querySelector(s);
const M = D.market, PC = M.perComp, cos = D.competitors;
const money = v => "$"+v.toFixed(2);

const staleList = Object.entries(D.stale||{});
$("#sub").innerHTML = "Snapshot "+D.date+" · "+cos.length+" competitors · "
  + D.total.toLocaleString()+" packages · "+D.countries.length+" countries"
  + (staleList.length ? ` &nbsp;<span class="warn">⚠ stale: `
      +staleList.map(([c,d])=>`${c} ${d}`).join(", ")+`</span>` : "");
document.title = "eSIM Intelligence — "+D.date;

// ---------- 1. MARKET KPIs ----------
function kpi(lab,val,sub,hl){return `<div class="kpi${hl?' hl':''}"><div class="lab">${lab}</div><div class="val">${val}</div><div class="sub2">${sub||""}</div></div>`;}
$("#mkpis").innerHTML = [
  kpi("Competitors", cos.length, "takip edilen"),
  kpi("Packages", D.total.toLocaleString(), "toplam plan"),
  kpi("Widest coverage", M.leaders.coverage, PC[M.leaders.coverage].countries+" ülke", true),
  kpi("En iyi değer ($/GB)", M.leaders.value||"—", M.leaders.value?money(PC[M.leaders.value].avgGB)+" medyan /GB":"", true),
  kpi("Price leader (GB)", M.leaders.gbLeader, PC[M.leaders.gbLeader].gbLeader+" ülkede en ucuz", true),
  kpi("Unlimited leader", M.leaders.unlimLeader, PC[M.leaders.unlimLeader].unlimLeader+" ülkede en ucuz (7g)", true),
].join("");

// ---------- 2. POSITIONING TABLE ----------
(function(){
  const rows = cos.map(c=>({c, ...PC[c]}))
    .sort((a,b)=>(a.avgGB??1e9)-(b.avgGB??1e9));
  const head = `<thead><tr>
    <th class="l">Competitor</th><th>Coverage</th><th>Plans</th>
    <th class="l">Medyan $/GB (uygun → pahalı)</th><th>7d Unlimited (medyan)</th>
    <th>GB'de en ucuz</th><th>Position</th></tr></thead>`;
  let body="<tbody>";
  for(const r of rows){
    const col = `linear-gradient(90deg,var(--barlo),var(--barhi))`;
    const bar = r.avgGB!=null
      ? `<div class="bar"><i style="width:${Math.max(6,r.barPct)}%;background:${col}"></i></div> <span class="num">${money(r.avgGB)}</span>`
      : `<span class="na">— (unlimited-only)</span>`;
    body += `<tr>
      <td class="l"><b>${r.c}</b></td>
      <td class="num">${r.countries}</td>
      <td class="num">${r.plans.toLocaleString()}</td>
      <td class="l">${bar}</td>
      <td class="num">${r.unlim7!=null?money(r.unlim7):'<span class=na>—</span>'}</td>
      <td class="num">${r.gbLeader} ülke</td>
      <td><span class="badge b-${r.badge}">${r.badge}</span></td>
    </tr>`;
  }
  $("#posTbl").innerHTML = head+body+"</tbody>";
})();

// ---------- 3. COUNTRY DRILL-DOWN ----------
let country = D.countries.includes("United States")?"United States":D.countries[0];

function fillCountry(f){
  const el=$("#country");
  const list=D.countries.filter(c=>!f||c.toLowerCase().includes(f.toLowerCase()));
  el.innerHTML=list.map(c=>`<option${c===country?" selected":""}>${c}</option>`).join("");
  if(!list.includes(country)&&list.length){country=list[0];el.value=country;}
}
function cRecs(){return D.recs.filter(r=>r.c===country);}

function renderCountry(){
  const rows=cRecs();
  // per competitor stats for this country
  const stat={};
  for(const r of rows){
    const s=stat[r.co]=stat[r.co]||{plans:0,minRate:null,cheapest:null,unlim7:null};
    s.plans++;
    if(r.g){const rate=r.p/r.g; if(s.minRate==null||rate<s.minRate){s.minRate=rate;}}
    if(s.cheapest==null||r.p<s.cheapest.p) s.cheapest=r;
    if(r.d==="Unlimited"&&r.n===7&&(s.unlim7==null||r.p<s.unlim7)) s.unlim7=r.p;
  }
  const active=Object.keys(stat);
  // country KPIs
  const gbLeader = active.filter(c=>stat[c].minRate!=null)
    .sort((a,b)=>stat[a].minRate-stat[b].minRate)[0];
  const u7Leader = active.filter(c=>stat[c].unlim7!=null)
    .sort((a,b)=>stat[a].unlim7-stat[b].unlim7)[0];
  const allPrices=rows.map(r=>r.p);
  $("#ckpis").innerHTML=[
    kpi("Cheapest $/GB here", gbLeader||"—", gbLeader?money(stat[gbLeader].minRate)+" /GB":"", true),
    kpi("Cheapest 7d unlimited", u7Leader||"—", u7Leader?money(stat[u7Leader].unlim7):"—", true),
    kpi("Competitors here", active.length, "aktif firma"),
    kpi("Price range", allPrices.length?money(Math.min(...allPrices)):"—",
        allPrices.length?"→ "+money(Math.max(...allPrices)):""),
  ].join("");
  // scorecards
  $("#score").innerHTML = active.sort((a,b)=>(stat[a].minRate??1e9)-(stat[b].minRate??1e9))
    .map(c=>{
      const s=stat[c], ch=s.cheapest;
      return `<div class="sc">
        <div class="co">${c} <span class="badge b-${PC[c].badge}" style="font-size:10px">${PC[c].badge}</span></div>
        <div class="row"><span>En ucuz plan</span><b>${ch?ch.d+(ch.n?"/"+ch.n+"g":"")+" · "+money(ch.p):"—"}</b></div>
        <div class="row"><span>En iyi $/GB</span><b>${s.minRate!=null?money(s.minRate):"—"}</b></div>
        <div class="row"><span>7g sınırsız</span><b>${s.unlim7!=null?money(s.unlim7):"—"}</b></div>
        <div class="row"><span>Plan sayısı</span><b>${s.plans}</b></div>
      </div>`;
    }).join("");
}

// ---------- 4. DETAILED TABLE (filters + sort) ----------
let sizes=new Set(), days="All", hidden=new Set(), sortCol=null, sortDir=1;
function gbVal(d){if(d==="Unlimited")return 1e9;const m=d.match(/([\d.]+)\s*GB/);return m?parseFloat(m[1]):1e8;}
function sizeOrder(a,b){if(a==="Unlimited")return -1;if(b==="Unlimited")return 1;return gbVal(a)-gbVal(b);}
function sizeMatch(r){return sizes.size===0||sizes.has(r.d);}
function shownCos(){return cos.filter(c=>!hidden.has(c));}

function fillCoChips(){
  $("#cochips").innerHTML=cos.map(c=>`<span class="chip co${hidden.has(c)?"":" on"}" data-c="${c}">${c}</span>`).join("");
}
function fillSize(){
  const avail=[...new Set(cRecs().map(r=>r.d))].sort(sizeOrder);
  for(const s of [...sizes]) if(!avail.includes(s)) sizes.delete(s);
  $("#sizechips").innerHTML=[`<span class="chip${sizes.size===0?" on":""}" data-v="__all">All</span>`]
    .concat(avail.map(s=>`<span class="chip${sizes.has(s)?" on":""}" data-v="${s}">${s}</span>`)).join("");
  const el=$("#size"), cur=[...el.options].map(o=>o.value);
  if(cur.join("|")!==avail.join("|")) el.innerHTML=avail.map(s=>`<option value="${s}">${s}</option>`).join("");
  for(const o of el.options) o.selected=sizes.has(o.value);
}
function fillDays(){
  let ds=[...new Set(cRecs().filter(sizeMatch).map(r=>r.n))];
  const blank=ds.includes(null); ds=ds.filter(x=>x!=null).sort((a,b)=>a-b);
  let o=`<option>All</option>`+ds.map(d=>`<option${String(d)===String(days)?" selected":""}>${d}</option>`).join("");
  if(blank)o+=`<option value="none"${days==="none"?" selected":""}>No fixed validity</option>`;
  $("#days").innerHTML=o;
  if(days!=="All"&&days!=="none"&&!ds.map(String).includes(String(days)))days="All";
}

function renderTable(){
  const show=shownCos();
  let rows=cRecs().filter(sizeMatch);
  if(days==="none")rows=rows.filter(r=>r.n==null);
  else if(days!=="All")rows=rows.filter(r=>String(r.n)===String(days));

  const plans={};
  for(const r of rows){
    if(hidden.has(r.co))continue;
    const k=r.d+"||"+(r.n==null?"":r.n);
    const p=(plans[k]=plans[k]||{d:r.d,n:r.n,g:r.g,px:{}});
    p.px[r.co]=(p.px[r.co]==null)?r.p:Math.min(p.px[r.co],r.p);
  }
  let arr=Object.values(plans);
  const dfl=(a,b)=>sizeOrder(a.d,b.d)||((a.n||0)-(b.n||0));
  arr.sort((a,b)=>{
    if(sortCol===null)return dfl(a,b);
    if(sortCol==="data")return sizeOrder(a.d,b.d)*sortDir||((a.n||0)-(b.n||0));
    if(sortCol==="days"){const an=a.n==null?1e9:a.n,bn=b.n==null?1e9:b.n;return (an-bn)*sortDir||sizeOrder(a.d,b.d);}
    if(sortCol==="rate"){const ar=a.g?minPx(a)/a.g:1e9,br=b.g?minPx(b)/b.g:1e9;return (ar-br)*sortDir||dfl(a,b);}
    const av=a.px[sortCol],bv=b.px[sortCol];
    if(av==null&&bv==null)return dfl(a,b);
    if(av==null)return 1; if(bv==null)return -1;
    return (av-bv)*sortDir||dfl(a,b);
  });

  const t=$("#tbl");
  if(!arr.length){t.innerHTML=`<tbody><tr><td class="empty">No plans match filters for ${country}.</td></tr></tbody>`;$("#count").textContent="";return;}
  const arw=c=>c===sortCol?`<span class="arw">${sortDir>0?"▲":"▼"}</span>`:"";
  const th=(id,l,cls)=>`<th class="${cls||''}${id===sortCol?' sorted':''}" data-sort="${id}">${l}${arw(id)}</th>`;
  let head="<thead><tr>"+th("data","Data","l")+th("days","Days")+th("rate","$/GB")
    +show.map(c=>th(c,c)).join("")+`<th class="l">🏆 Cheapest</th></tr></thead>`;
  let body="<tbody>";
  for(const p of arr){
    const vals=show.map(c=>p.px[c]).filter(v=>v!=null);
    if(!vals.length)continue;
    const lo=Math.min(...vals),hi=Math.max(...vals);
    const winC=show.find(c=>p.px[c]===lo);
    const rate=p.g?money(lo/p.g):"—";
    body+=`<tr><td class="l"><b>${p.d}</b></td><td class="num">${p.n==null?"—":p.n}</td>`
      +`<td class="num" style="color:var(--muted)">${rate}</td>`;
    for(const c of show){
      const v=p.px[c];
      if(v==null){body+=`<td class="price na">—</td>`;continue;}
      let cls="price"; if(vals.length>1&&v===lo)cls+=" low"; else if(vals.length>1&&v===hi)cls+=" high";
      body+=`<td class="${cls}">${money(v)}</td>`;
    }
    body+=`<td class="l"><span class="win">${winC}</span> ${money(lo)}</td></tr>`;
  }
  t.innerHTML=head+body+"</tbody>";
  $("#count").textContent=`${arr.length} plan · ${country} · ${show.length}/${cos.length} firma`
    +(sizes.size?" · "+[...sizes].join(", "):"")+(days!=="All"?" · "+days+"g":"");
}
function minPx(p){return Math.min(...Object.values(p.px));}

// ---------- refresh / events ----------
function refreshCountry(){fillSize();fillDays();renderCountry();renderTable();}
$("#search").addEventListener("input",e=>{fillCountry(e.target.value);country=$("#country").value;sizes.clear();days="All";refreshCountry();});
$("#country").addEventListener("change",e=>{country=e.target.value;sizes.clear();days="All";refreshCountry();});
$("#size").addEventListener("change",e=>{sizes=new Set([...e.target.selectedOptions].map(o=>o.value));days="All";fillSize();fillDays();renderTable();});
$("#sizechips").addEventListener("click",e=>{if(!e.target.classList.contains("chip"))return;const v=e.target.dataset.v;if(v==="__all")sizes.clear();else sizes.has(v)?sizes.delete(v):sizes.add(v);days="All";fillSize();fillDays();renderTable();});
$("#days").addEventListener("change",e=>{days=e.target.value;renderTable();});
$("#cochips").addEventListener("click",e=>{if(!e.target.classList.contains("chip"))return;const c=e.target.dataset.c;hidden.has(c)?hidden.delete(c):hidden.add(c);if(hidden.size>=cos.length)hidden.delete(c);fillCoChips();renderTable();});
$("#tbl").addEventListener("click",e=>{const h=e.target.closest("th[data-sort]");if(!h)return;const c=h.dataset.sort;if(sortCol===c)sortDir=-sortDir;else{sortCol=c;sortDir=1;}renderTable();});
$("#reset").addEventListener("click",()=>{sizes.clear();days="All";hidden.clear();sortCol=null;sortDir=1;fillCoChips();refreshCountry();});

// init
fillCountry(""); fillCoChips(); refreshCountry();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
