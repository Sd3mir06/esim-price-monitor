#!/usr/bin/env python3
"""
Build a self-contained dashboard.html from the latest prices CSV.
Open it in any browser — no server needed, works offline.
Run automatically after each collection (wired into run.sh).
"""
import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def latest_csv():
    files = sorted(glob.glob(os.path.join(DATA, "prices_*.csv")))
    return files[-1] if files else None


def main():
    src = latest_csv()
    if not src:
        print("No data CSV found — run collect.py first.")
        return
    rows = list(csv.DictReader(open(src)))
    date = rows[0]["date"] if rows else ""

    recs = []
    for r in rows:
        days = r["days"]
        days = int(days) if str(days).isdigit() else None
        try:
            price = float(r["price_usd"])
        except ValueError:
            continue
        recs.append({
            "co": r["competitor"], "c": r["country"], "d": r["data"],
            "n": days, "p": price,
        })

    competitors = sorted(set(x["co"] for x in recs))
    countries = sorted(set(x["c"] for x in recs))
    total = len(recs)

    # per-competitor freshness: newest collection date per competitor.
    # Carry-forward can leave a provider on an older date -> flag it as stale.
    fresh = {}
    for r in rows:
        c, d = r["competitor"], r["date"]
        if c not in fresh or d > fresh[c]:
            fresh[c] = d
    newest = max(fresh.values()) if fresh else date
    stale = {c: d for c, d in fresh.items() if d < newest}

    payload = json.dumps({
        "date": newest, "competitors": competitors, "countries": countries,
        "recs": recs, "total": total, "stale": stale,
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
<title>eSIM Competitor Prices</title>
<style>
  :root{
    --bg:#0f1220; --panel:#1a1f35; --panel2:#232a45; --line:#2f3860;
    --text:#e7eaf3; --muted:#9aa3c4; --accent:#5b8cff;
    --low:#123a24; --lowtx:#5ef0a3; --high:#3a1620; --hightx:#ff8a9c;
  }
  @media (prefers-color-scheme: light){
    :root{ --bg:#f4f6fb; --panel:#ffffff; --panel2:#f0f3fa; --line:#e2e7f2;
      --text:#1a2138; --muted:#5c6684; --accent:#2f6bff;
      --low:#e2f8ec; --lowtx:#087a45; --high:#fdeaee; --hightx:#c02b45; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  header{padding:22px 26px 14px;border-bottom:1px solid var(--line)}
  h1{margin:0;font-size:20px;font-weight:700;letter-spacing:-.2px}
  .sub{color:var(--muted);font-size:13px;margin-top:4px}
  .wrap{padding:18px 26px 60px;max-width:1200px;margin:0 auto}
  .stats{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 18px}
  .stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;
    padding:10px 14px;min-width:110px}
  .stat b{display:block;font-size:20px;font-weight:700}
  .stat span{color:var(--muted);font-size:12px}
  .controls{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;margin-bottom:8px}
  .ctl{display:flex;flex-direction:column}
  select,input{background:var(--panel);color:var(--text);border:1px solid var(--line);
    border-radius:10px;padding:9px 12px;font-size:15px;outline:none;min-width:140px}
  select:focus,input:focus{border-color:var(--accent)}
  label{color:var(--muted);font-size:12px;margin-bottom:5px}
  .chips{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 14px}
  .chip{background:var(--panel);color:var(--muted);border:1px solid var(--line);
    border-radius:999px;padding:6px 13px;font-size:13px;cursor:pointer;user-select:none}
  .chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
  .reset{margin-left:auto;color:var(--accent);background:none;border:0;cursor:pointer;font-size:13px}
  .tablecard{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
  .scroll{overflow-x:auto}
  table{border-collapse:collapse;width:100%;font-size:14px}
  th,td{padding:10px 13px;text-align:right;white-space:nowrap}
  th.l,td.l{text-align:left}
  th:first-child,td:first-child{position:sticky;left:0;background:var(--panel)}
  thead th{background:var(--panel2);color:var(--muted);font-weight:600;
    border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2;
    cursor:pointer;user-select:none}
  thead th:hover{color:var(--text)}
  thead th.sorted{color:var(--accent)}
  thead th .arw{font-size:10px;margin-left:3px}
  thead th:first-child{z-index:3}
  select[multiple]{min-width:150px;padding:4px}
  select[multiple] option{padding:3px 6px}
  tbody tr{border-bottom:1px solid var(--line)}
  tbody tr:hover td{background:var(--panel2)}
  tbody tr:hover td:first-child{background:var(--panel2)}
  td.price{font-variant-numeric:tabular-nums;font-weight:600}
  td.na{color:var(--muted);font-weight:400}
  td.low{background:var(--low);color:var(--lowtx)}
  td.high{color:var(--hightx)}
  .data{font-weight:700}
  .days{color:var(--muted);font-variant-numeric:tabular-nums}
  .count{color:var(--muted);font-size:12px;margin:10px 2px}
  .empty{padding:40px;text-align:center;color:var(--muted)}
  .legend{display:flex;gap:16px;align-items:center;color:var(--muted);font-size:12px;margin-top:12px;flex-wrap:wrap}
  .sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:middle;margin-right:5px}
</style>
</head>
<body>
<header>
  <h1>eSIM Competitor Prices</h1>
  <div class="sub" id="sub"></div>
</header>
<div class="wrap">
  <div class="stats" id="stats"></div>

  <div class="controls">
    <div class="ctl">
      <label>Country / destination</label>
      <input id="search" placeholder="type to search…" autocomplete="off">
      <select id="country" size="1"></select>
    </div>
    <div class="ctl">
      <label>Data size (⌘/Ctrl-click for several)</label>
      <select id="size" multiple size="4"></select>
    </div>
    <div class="ctl">
      <label>Validity (days)</label>
      <select id="days"></select>
    </div>
    <button class="reset" id="reset">Reset filters</button>
  </div>

  <!-- multi-select data-size chips (synced with the dropdown) -->
  <label style="color:var(--muted);font-size:12px">Data size <span style="opacity:.7">(click chips to select several)</span></label>
  <div class="chips" id="sizechips"></div>

  <div class="tablecard">
    <div class="scroll"><table id="tbl"></table></div>
  </div>
  <div class="count" id="count"></div>
  <div class="legend">
    <span><span class="sw" style="background:var(--lowtx)"></span>cheapest in row</span>
    <span><span class="sw" style="background:var(--hightx)"></span>most expensive</span>
    <span>— = that competitor has no matching plan</span>
    <span>Days “—” = plan sold without a fixed validity (e.g. some Breeze GB plans)</span>
  </div>
</div>

<script>
const D = __PAYLOAD__;
const $ = s => document.querySelector(s);

const staleList = Object.entries(D.stale||{});
$("#sub").innerHTML = "Snapshot " + D.date + " · " + D.competitors.join(" · ")
  + (staleList.length
      ? ` &nbsp; <span style="color:var(--hightx)">⚠ stale (last good): `
        + staleList.map(([c,d])=>`${c} ${d}`).join(", ") + `</span>`
      : "");
document.title = "eSIM Prices — " + D.date;
$("#stats").innerHTML = [
  ["Competitors", D.competitors.length],
  ["Countries", D.countries.length],
  ["Packages", D.total.toLocaleString()],
  ["Snapshot", D.date],
].map(([l,v]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join("");

// ---- state ----
let country = D.countries.includes("United States") ? "United States" : D.countries[0];
let sizes = new Set();      // empty = All sizes
let days = "All";
let sortCol = null;         // null = default (data, then days); else "data"/"days"/competitor
let sortDir = 1;            // 1 = asc, -1 = desc

// ---- helpers ----
function gbVal(d){ if(d==="Unlimited") return 1e9; const m=d.match(/([\d.]+)\s*GB/); return m?parseFloat(m[1]):1e8; }
function sizeOrder(a,b){ if(a==="Unlimited") return -1; if(b==="Unlimited") return 1; return gbVal(a)-gbVal(b); }
function countryRecs(){ return D.recs.filter(r=>r.c===country); }

function fillCountry(filter){
  const sel=$("#country");
  const list=D.countries.filter(c=>!filter||c.toLowerCase().includes(filter.toLowerCase()));
  sel.innerHTML=list.map(c=>`<option${c===country?" selected":""}>${c}</option>`).join("");
  if(!list.includes(country) && list.length){ country=list[0]; sel.value=country; }
}
function sizeMatch(r){ return sizes.size===0 || sizes.has(r.d); }

function fillSize(){
  const avail=[...new Set(countryRecs().map(r=>r.d))].sort(sizeOrder);
  // drop any selected sizes not present for this country
  for(const s of [...sizes]) if(!avail.includes(s)) sizes.delete(s);
  // chips (cheap to rebuild)
  const chips=[`<span class="chip${sizes.size===0?" on":""}" data-v="__all">All</span>`]
    .concat(avail.map(s=>`<span class="chip${sizes.has(s)?" on":""}" data-v="${s}">${s}</span>`));
  $("#sizechips").innerHTML=chips.join("");
  // dropdown: rebuild options only when the country's size list changed
  const el=$("#size");
  const cur=[...el.options].map(o=>o.value);
  if(cur.join("|")!==avail.join("|"))
    el.innerHTML=avail.map(s=>`<option value="${s}">${s}</option>`).join("");
  for(const o of el.options) o.selected=sizes.has(o.value);
}
function fillDays(){
  let ds=[...new Set(countryRecs().filter(sizeMatch).map(r=>r.n))];
  const hasBlank=ds.includes(null);
  ds=ds.filter(x=>x!=null).sort((a,b)=>a-b);
  let opts=`<option>All</option>`+ds.map(d=>`<option${String(d)===String(days)?" selected":""}>${d}</option>`).join("");
  if(hasBlank) opts+=`<option value="none"${days==="none"?" selected":""}>No fixed validity</option>`;
  $("#days").innerHTML=opts;
  if(days!=="All" && days!=="none" && !ds.map(String).includes(String(days))) days="All";
}

function render(){
  const cos=D.competitors;
  let rows=countryRecs().filter(sizeMatch);
  if(days==="none") rows=rows.filter(r=>r.n==null);
  else if(days!=="All") rows=rows.filter(r=>String(r.n)===String(days));

  // pivot key = data + days
  const plans={};
  for(const r of rows){
    const k=r.d+"||"+(r.n==null?"":r.n);
    const p=(plans[k]=plans[k]||{d:r.d,n:r.n,px:{}});
    // a firm may list several variants for the same data+days — keep the cheapest
    p.px[r.co]=(p.px[r.co]==null)?r.p:Math.min(p.px[r.co],r.p);
  }
  const arr=Object.values(plans);
  const dfl=(a,b)=>sizeOrder(a.d,b.d)||((a.n||0)-(b.n||0));  // default order
  arr.sort((a,b)=>{
    if(sortCol===null) return dfl(a,b);
    if(sortCol==="data") return (sizeOrder(a.d,b.d)*sortDir)||((a.n||0)-(b.n||0));
    if(sortCol==="days"){
      const an=a.n==null?Infinity:a.n, bn=b.n==null?Infinity:b.n;
      return ((an-bn)*sortDir)||sizeOrder(a.d,b.d);
    }
    // competitor price column — missing prices always sort last
    const av=a.px[sortCol], bv=b.px[sortCol];
    if(av==null && bv==null) return dfl(a,b);
    if(av==null) return 1;
    if(bv==null) return -1;
    return ((av-bv)*sortDir)||dfl(a,b);
  });

  const t=$("#tbl");
  if(!arr.length){
    t.innerHTML=`<tbody><tr><td class="empty">No plans match these filters for ${country}.</td></tr></tbody>`;
    $("#count").textContent=""; return;
  }
  const arw=c=>c===sortCol?`<span class="arw">${sortDir>0?"▲":"▼"}</span>`:"";
  const th=(id,lbl,cls)=>`<th class="${cls||''}${id===sortCol?' sorted':''}" data-sort="${id}">${lbl}${arw(id)}</th>`;
  let head="<thead><tr>"+th("data","Data","l")+th("days","Days")
    +cos.map(c=>th(c,c)).join("")+"</tr></thead>";
  let body="<tbody>";
  for(const p of arr){
    const vals=cos.map(c=>p.px[c]).filter(v=>v!=null);
    const lo=Math.min(...vals), hi=Math.max(...vals);
    body+=`<tr><td class="l data">${p.d}</td><td class="days">${p.n==null?"—":p.n}</td>`;
    for(const c of cos){
      const v=p.px[c];
      if(v==null){ body+=`<td class="price na">—</td>`; continue; }
      let cls="price";
      if(vals.length>1 && v===lo) cls+=" low";
      else if(vals.length>1 && v===hi) cls+=" high";
      body+=`<td class="${cls}">$${v.toFixed(2)}</td>`;
    }
    body+="</tr>";
  }
  body+="</tbody>";
  t.innerHTML=head+body;
  const sizeTxt = sizes.size ? " · "+[...sizes].join(", ") : "";
  $("#count").textContent=`${arr.length} plan rows · ${country}`+sizeTxt
    + (days!=="All"?` · ${days==="none"?"no fixed validity":days+" days"}`:"");
}

function refresh(){ fillSize(); fillDays(); render(); }

// ---- events ----
$("#search").addEventListener("input", e=>{ fillCountry(e.target.value); country=$("#country").value; sizes.clear(); days="All"; refresh(); });
$("#country").addEventListener("change", e=>{ country=e.target.value; sizes.clear(); days="All"; refresh(); });
$("#days").addEventListener("change", e=>{ days=e.target.value; render(); });
$("#size").addEventListener("change", e=>{
  sizes=new Set([...e.target.selectedOptions].map(o=>o.value));
  days="All"; refresh();
});
$("#sizechips").addEventListener("click", e=>{
  if(!e.target.classList.contains("chip")) return;
  const v=e.target.dataset.v;
  if(v==="__all") sizes.clear();          // "All" = show every size
  else { sizes.has(v) ? sizes.delete(v) : sizes.add(v); }  // toggle
  days="All"; refresh();
});
// column sorting: click a header to sort; click again to reverse
$("#tbl").addEventListener("click", e=>{
  const h=e.target.closest("th[data-sort]"); if(!h) return;
  const col=h.dataset.sort;
  if(sortCol===col) sortDir=-sortDir; else { sortCol=col; sortDir=1; }
  render();
});
$("#reset").addEventListener("click", ()=>{
  sizes.clear(); days="All"; sortCol=null; sortDir=1; refresh();
});

// ---- init ----
fillCountry("");
refresh();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
