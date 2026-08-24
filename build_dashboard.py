#!/usr/bin/env python3
"""
Build a self-contained executive dashboard.html from the latest prices CSV.
Bilingual (TR/EN) — toggle in the header, all UI text + tooltips localized.
Open it in any browser — no server needed, works offline.
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

    fresh = {}
    for r in raw:
        c, d = r["competitor"], r["date"]
        if c not in fresh or d > fresh[c]:
            fresh[c] = d
    newest = max(fresh.values()) if fresh else ""
    stale = {c: d for c, d in fresh.items() if d < newest}

    per = {c: {"countries": set(), "plans": 0, "rates": [], "unlim7": [],
               "gbLeader": 0, "unlimLeader": 0} for c in competitors}
    best_gb, best_u7 = {}, {}
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
        avg = round(st.median(p["rates"]), 2) if p["rates"] else None
        u7 = round(st.median(p["unlim7"]), 2) if p["unlim7"] else None
        perComp[c] = {"countries": len(p["countries"]), "plans": p["plans"],
                      "avgGB": avg, "unlim7": u7,
                      "gbLeader": p["gbLeader"], "unlimLeader": p["unlimLeader"]}
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

    try:
        events = json.load(open(os.path.join(HERE, "events.json")))
    except Exception:
        events = []

    payload = json.dumps({
        "date": newest, "competitors": competitors, "countries": countries,
        "recs": recs, "total": total, "stale": stale,
        "market": {"perComp": perComp, "leaders": leaders}, "events": events,
        "beta": ["Nomad", "Saily"],   # newly added, Playwright-scraped — flag as beta
    }, separators=(",", ":"))

    html = TEMPLATE.replace("__PAYLOAD__", payload)
    os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
    out = os.path.join(HERE, "docs", "index.html")   # single build output (served by Pages)
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
  header{padding:26px 22px 10px;max-width:1240px;margin:0 auto;display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
  h1{margin:0;font-size:21px;font-weight:800;letter-spacing:-.3px}
  h2{font-size:13px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;
    color:var(--muted);margin:30px 0 12px;display:flex;align-items:center;gap:8px}
  h2::after{content:"";flex:1;height:1px;background:var(--line)}
  .sub{color:var(--muted);font-size:12.5px;margin-top:4px}
  .warn{color:var(--hightx)}
  .langtog{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;flex:none}
  .langtog button{background:var(--panel);color:var(--muted);border:0;padding:6px 11px;font-size:12.5px;font-weight:700;cursor:pointer}
  .langtog button.on{background:var(--accent);color:#fff}
  .qm{display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:50%;
    background:var(--panel);border:1px solid var(--line);color:var(--muted);font-size:10px;font-weight:700;
    margin-left:5px;cursor:help;vertical-align:middle;text-transform:none;letter-spacing:0}
  .qm:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
  .floattip{position:fixed;max-width:280px;background:var(--panel);color:var(--text);border:1px solid var(--line);
    border-radius:11px;padding:11px 13px;font-size:12px;line-height:1.55;font-weight:400;text-align:left;
    text-transform:none;letter-spacing:normal;box-shadow:0 14px 38px rgba(0,0,0,.42);z-index:1000;display:none}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:11px}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px 15px;position:relative;overflow:hidden}
  .kpi .lab{color:var(--muted);font-size:11.5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
  .kpi .val{font-size:22px;font-weight:800;margin-top:3px;letter-spacing:-.5px}
  .kpi .sub2{color:var(--muted);font-size:12px;margin-top:1px}
  .kpi.hl{background:linear-gradient(135deg,var(--panel),var(--panel2))}
  .kpi.hl .val{color:var(--accent)}
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
  .betatag{display:inline-block;font-size:9px;font-weight:800;letter-spacing:.4px;text-transform:uppercase;
    color:var(--accent2);background:color-mix(in srgb,var(--accent2) 18%,transparent);
    border:1px solid var(--accent2);border-radius:5px;padding:0 4px;margin-left:5px;vertical-align:middle;cursor:help}
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
  .deals{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:9px;margin:2px 0 14px}
  .deal{background:linear-gradient(135deg,var(--panel),var(--panel2));border:1px solid var(--line);border-radius:12px;padding:10px 13px}
  .deal .ds{font-size:11.5px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.4px}
  .deal .dco{font-size:14.5px;font-weight:800;color:var(--lowtx);margin-top:1px}
  .deal .dp{font-size:20px;font-weight:800;font-variant-numeric:tabular-nums;letter-spacing:-.4px}
  .deal .dm{font-size:11.5px;color:var(--muted);margin-top:1px}
  .deal .dhead{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:6px}
  .deal .davg{font-size:11px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
  .deal .drow{display:flex;align-items:center;gap:8px;font-size:13px;padding:3px 0;border-top:1px solid var(--line)}
  .deal .drow:first-of-type{border-top:0}
  .deal .drank{width:16px;height:16px;flex:none;border-radius:50%;background:var(--panel2);color:var(--muted);
    font-size:10px;font-weight:800;display:flex;align-items:center;justify-content:center}
  .deal .drow:first-of-type .drank{background:var(--lowtx);color:#08130c}
  .deal .dco2{flex:1;font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .deal .dval{font-weight:800;font-variant-numeric:tabular-nums}
  .deal .drow:first-of-type .dval{color:var(--lowtx)}
  #daychips .chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
  .scoregrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:11px}
  .sc{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
  .sc .co{font-weight:800;font-size:15px}
  .sc .row{display:flex;justify-content:space-between;font-size:12.5px;color:var(--muted);margin-top:6px}
  .sc .row b{color:var(--text);font-variant-numeric:tabular-nums}
  .glab{color:var(--muted);font-size:11.5px;display:block}
  .cdbar{max-width:1240px;margin:0 auto;padding:10px 22px}
  .cdbar .cdinner{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;border-radius:12px;
    padding:11px 16px;font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .cdbar .cdinner b{font-weight:800;font-variant-numeric:tabular-nums}
  /* tabs */
  .tabs{position:sticky;top:0;z-index:20;background:var(--bg);max-width:1240px;margin:0 auto;
    padding:8px 22px 0;display:flex;gap:2px;border-bottom:1px solid var(--line);
    overflow-x:auto;overflow-y:hidden}
  .tabs button{background:none;border:0;color:var(--muted);font:inherit;font-size:14px;font-weight:700;
    padding:11px 15px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap}
  .tabs button:hover{color:var(--text)}
  .tabs button.on{color:var(--accent);border-bottom-color:var(--accent)}
  .panel{display:none} .panel.on{display:block}
  /* event cards (column layout — name / meta / pill never collide) */
  .evgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:11px;margin:4px 0 6px}
  .evcard{display:flex;flex-direction:column;gap:6px;background:var(--panel);border:1px solid var(--line);
    border-radius:12px;padding:13px 15px;cursor:pointer;transition:border-color .12s}
  .evcard:hover{border-color:var(--accent)}
  .evhead{display:flex;align-items:center;gap:9px}
  .evflag{font-size:24px;line-height:1}
  .evname{font-weight:800;font-size:14px;line-height:1.25}
  .evapx{font-weight:600;font-size:10px;color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:0 4px;margin-left:4px;white-space:nowrap}
  .evmeta{color:var(--muted);font-size:11.5px}
  .evpill{align-self:flex-start;font-size:11.5px;font-weight:800;color:var(--accent);background:var(--panel2);border-radius:999px;padding:3px 10px}
  .evpill.on{color:var(--lowtx)}
</style>
</head>
<body>
<header>
  <div>
    <h1 id="h1"></h1>
    <div class="sub" id="sub"></div>
  </div>
  <div class="langtog" id="langtog">
    <button data-l="en">EN</button><button data-l="tr">TR</button>
  </div>
</header>
<div class="cdbar" id="cdbar"></div>
<nav class="tabs" id="tabs">
  <button data-tab="overview" class="on"></button>
  <button data-tab="country"></button>
  <button data-tab="trends"></button>
  <button data-tab="events"></button>
</nav>
<div class="wrap">

  <section class="panel on" data-tab="overview">
    <h2 id="h2-market"></h2>
    <div class="kpis" id="mkpis"></div>
    <h2 id="h2-pos"></h2>
    <div class="card scroll"><table id="posTbl"></table></div>
    <div class="legend" id="pos-legend"></div>
  </section>

  <section class="panel" data-tab="country">
    <h2 id="h2-country"></h2>
    <div class="controls">
      <div class="ctl"><label id="lab-country"></label>
        <input id="search" autocomplete="off">
        <select id="country"></select>
      </div>
    </div>
    <div class="kpis" id="ckpis" style="margin-top:6px"></div>
    <div class="scoregrid" id="score" style="margin-top:12px"></div>

    <h2 id="h2-detail"></h2>
    <div class="controls">
      <div class="ctl"><label id="lab-size"></label>
        <select id="size" multiple size="4"></select></div>
      <button class="reset" id="reset"></button>
    </div>
    <label class="glab" id="lab-cochips"></label>
    <div class="chips" id="cochips"></div>
    <label class="glab" id="lab-sizechips"></label>
    <div class="chips" id="sizechips"></div>
    <label class="glab" id="lab-days"></label>
    <div class="chips" id="daychips"></div>
    <div id="dealwrap"></div>
    <div class="card scroll"><table id="tbl"></table></div>
    <div class="count" id="count"></div>
    <div class="legend" id="tbl-legend"></div>
  </section>

  <section class="panel" data-tab="trends">
    <h2 id="h2-trends"></h2>
    <div class="controls">
      <div class="ctl"><label id="lab-trend-country"></label><select id="trend-country"></select></div>
      <div class="ctl"><label id="lab-trend-plan"></label><select id="trend-plan" style="min-width:190px"></select></div>
    </div>
    <div class="card" style="padding:16px 14px 12px"><div id="trend-chart"></div></div>
    <div class="count" id="trend-note"></div>
  </section>

  <section class="panel" data-tab="events">
    <h2 id="h2-events"></h2>
    <div id="events-2026"></div>
    <div id="events-2027"></div>
  </section>

</div>

<script>
const D = __PAYLOAD__;
const $ = s => document.querySelector(s);
const M = D.market, PC = M.perComp, cos = D.competitors;
const money = v => "$"+v.toFixed(2);

// ---------------- i18n ----------------
const T = {
 en:{
  title:"eSIM Competitor Intelligence",
  snap:"Snapshot", w_comp:"competitors", w_pack:"packages", w_ctry:"countries", stale:"stale (last good)",
  s_market:"Market Overview", s_market_t:"Market-wide summary of every competitor for today's snapshot — who has the widest reach, who is cheapest per unit of data, who leads on price.",
  s_pos:"Competitor Positioning", s_pos_t:"Each competitor's price stance: coverage, typical unit-data price (median $/GB) and how many markets they lead on price. See the ? on each column for detail.",
  s_country:"Country Drill-down", s_country_t:"Pick a country; the best deals, each competitor's scorecard and the detailed table below all update for that country.",
  s_detail:"Detailed Price Comparison", s_detail_t:"Every package for the selected country in one table. Filter by size/days/competitor, click a header to sort; cheapest in each row is green. The panel above gives the absolute cheapest per size.",
  // market KPIs
  k_comp:"Competitors", k_comp_s:"tracked", k_comp_t:"Number of competitor eSIM providers whose prices are collected automatically every day.",
  k_pack:"Packages", k_pack_s:"total plans", k_pack_t:"Total packages in today's snapshot across all competitors × countries × data/day combinations (one package = one row).",
  k_cov:"Widest coverage", k_cov_t:"The provider serving the most countries/destinations, by number of unique countries where they offer a package.",
  k_val:"Best value ($/GB)", k_val_s:"median /GB", k_val_t:"Provider with the lowest unit-data price (price ÷ GB) on GB plans, by median $/GB across all their GB plans. Lower = cheaper.",
  k_gbl:"Price leader (GB)", k_gbl_s:"country","k_gbl_s2":"cheapest in", k_gbl_t:"Provider with the lowest $/GB in the most countries. Per country, each provider's best unit price is compared; the one winning the most countries shows here.",
  k_unl:"Unlimited leader", k_unl_t:"Provider that is cheapest on the 7-day UNLIMITED plan in the most countries. Compares the unlimited-data model (e.g. Holafly).",
  cheapest_in:"countries won", ctry:"countries",
  // positioning
  p_comp:"Competitor", p_comp_t:"Competitor eSIM provider. Rows are sorted cheapest (low median $/GB) to most expensive.",
  p_cov:"Coverage", p_cov_t:"Number of distinct countries/destinations where this provider offers at least one package (unique). Note: Holafly's count includes city pages, so it is high.",
  p_plans:"Plans", p_plans_t:"Total packages collected from this provider — all countries × all data/day combinations. One row = one package.",
  p_medgb:"Median $/GB", p_medgb_t:"MEDIAN of the unit price (price ÷ GB) across ALL of the provider's GB plans. Median ignores outliers (1GB plans are very pricey) → reflects the typical unit price. Lower = cheaper. Unlimited plans excluded. Bar is proportional to the highest median (green=cheap, red=pricey).",
  p_7d:"7d Unlimited", p_7d_t:"Median price of the provider's 7-DAY UNLIMITED plans across all countries. For comparing unlimited-data providers (e.g. Holafly). '—' = no 7-day unlimited plan.",
  p_gbc:"Cheapest in GB", p_gbc_t:"In how many countries this provider has the lowest $/GB. Per country, each provider's best $/GB is compared; the lowest 'wins' that country. Higher = unit-price leader in more markets.",
  p_pos:"Position", p_pos_t:"Automatic tier by median $/GB: cheapest third = Budget, middle = Mid, priciest = Premium. Providers with no GB plans (unlimited only) = Unlimited-only.",
  leg_low:"low $/GB (cheap)", leg_high:"high $/GB (pricey)", leg_badge:"= tier by median $/GB",
  // country
  c_country:"Country / destination", c_search:"type to search…",
  ck_cheapgb:"Cheapest $/GB here", ck_cheapgb_t:"The provider offering the lowest unit-data price (price ÷ GB) in the selected country, and that value. Based on the provider's BEST (cheapest) GB plan here.",
  ck_cheapunl:"Cheapest 7d unlimited", ck_cheapunl_t:"The provider whose 7-day unlimited plan is cheapest in the selected country, and its price. '—' = nobody offers 7d unlimited here.",
  ck_comp:"Competitors here", ck_comp_s:"active", ck_comp_t:"Number of providers with at least one package in the selected country.",
  ck_range:"Price range", ck_range_t:"The lowest and highest package price in this country (all sizes/durations included).",
  sc_cheap:"Cheapest plan", sc_bestgb:"Best $/GB", sc_7d:"7d unlimited", sc_plans:"Plans",
  // deals + table
  d_label:"🏆 Best deals — top 3 by data size (across all durations; unlimited shown per-day)",
  avg:"avg", per_day:"per-day",
  d_suffix:"· cheapest", no_exp:"no expiry", w_days:"days",
  f_size:"Data size (⌘/Ctrl-click)", f_days:"Validity (days)", f_reset:"Reset",
  f_cochips:"Competitors (click to show/hide)", f_sizechips:"Data size (multi)",
  opt_all:"All", opt_novalid:"No fixed validity",
  t_data:"Data", t_data_t:"Package data amount: GB amount or Unlimited. Click header → sort by size.",
  t_days:"Days", t_days_t:"Package validity in days. '—' = no fixed validity stated (e.g. some Breeze GB plans).",
  t_rate:"$/GB · /day", t_rate_t:"Unit cost of the CHEAPEST price in this row: GB plans → price ÷ GB; Unlimited → price ÷ days (per-day). Click header → sort by best unit cost.",
  t_cheap:"🏆 Cheapest", t_cheap_t:"The cheapest provider and price in THIS row (same data size + same days). For the absolute cheapest per size regardless of days, use the 'Best deal by data size' panel above.",
  t_empty:"No plans match these filters.", firms:"firms", plan_rows:"plan",
  leg_cheaprow:"cheapest in row", leg_exp:"most expensive", leg_gb:"$/GB = price ÷ GB (GB plans only)", leg_trophy:"🏆 = cheapest firm in that row",
  s_events:"Upcoming Events", s_events_t:"Big global events (World-Cup scale) that trigger event-specific eSIM packages. Prices are re-collected daily from 7 days before each event. Click a card to jump to that country's prices.",
  ev_2026:"2026 — upcoming", ev_2027:"2027 — upcoming", ev_left:"days left", ev_ongoing:"ONGOING", ev_approx:"approx.",
  tab_overview:"Overview", tab_country:"By Country", tab_trends:"Trends", tab_events:"Events",
  beta_t:"Newly added (auto-scraped in beta) — may contain errors",
  cd_next:"Next event", cd_ongoing:"happening now", cd_d:"d", cd_h:"h", cd_m:"m", cd_s:"s",
  s_trends:"Price Trends", s_trends_t:"How a package's price changes over time — one point per weekly snapshot. Pick a country and a package to see every competitor's line.",
  tr_plan:"Package (data · days)", tr_note_build:"Trends build up over time — one point per weekly run; more points appear each week.", tr_note_pages:"Trends load on the live (Pages) URL — history is fetched there.", tr_nodata:"No history for this selection yet.",
  badge:{Budget:"Budget", Mid:"Mid", Premium:"Premium", "Unlimited-only":"Unlimited-only"},
 },
 tr:{
  title:"eSIM Rakip İstihbaratı",
  snap:"Anlık görüntü", w_comp:"rakip", w_pack:"paket", w_ctry:"ülke", stale:"eski (son iyi veri)",
  s_market:"Pazar Özeti", s_market_t:"Tüm rakiplerin bugünkü anlık görüntüye göre pazar geneli özeti — kim en geniş kapsamlı, kim birim veride en uygun, kim fiyat lideri.",
  s_pos:"Rakip Konumlandırma", s_pos_t:"Her rakibin fiyat konumu: kapsama, tipik birim veri fiyatı (medyan $/GB) ve kaç pazarda en ucuz olduğu. Her sütundaki ? ile ayrıntı.",
  s_country:"Ülke Detayı", s_country_t:"Bir ülke seç; en uygun teklifler, her rakibin skor kartı ve alttaki detaylı tablo o ülkeye göre güncellenir.",
  s_detail:"Detaylı Fiyat Karşılaştırma", s_detail_t:"Seçili ülkedeki tüm paketler tek tabloda. Boyut/gün/rakip filtrele, başlığa tıklayıp sırala; satırda en ucuz yeşil. Üstteki panel boyuta göre mutlak en ucuzu verir.",
  k_comp:"Rakip sayısı", k_comp_s:"takip edilen", k_comp_t:"Fiyatları her gün otomatik toplanan rakip eSIM firması sayısı.",
  k_pack:"Paket", k_pack_s:"toplam plan", k_pack_t:"Bugünkü anlık görüntüde tüm firmalar × ülkeler × veri/gün kombinasyonlarından toplanan toplam paket (bir paket = bir satır).",
  k_cov:"En geniş kapsama", k_cov_t:"En çok ülke/destinasyona hizmet veren firma; paket sunduğu benzersiz ülke sayısına göre.",
  k_val:"En iyi değer ($/GB)", k_val_s:"medyan /GB", k_val_t:"GB planlarında birim veri fiyatı (fiyat ÷ GB) en düşük olan firma; tüm GB planlarındaki $/GB medyanına göre. Düşük = daha uygun.",
  k_gbl:"Fiyat lideri (GB)", k_gbl_s:"ülke","k_gbl_s2":"ülkede en ucuz", k_gbl_t:"En çok ülkede en düşük $/GB'a sahip firma. Her ülkede firmaların en iyi birim fiyatı kıyaslanır; en çok ülke kazanan burada görünür.",
  k_unl:"Sınırsız lideri", k_unl_t:"7 günlük SINIRSIZ planda en çok ülkede en ucuz olan firma. Sınırsız-veri modelini kıyaslar (ör. Holafly).",
  cheapest_in:"ülkede en ucuz", ctry:"ülke",
  p_comp:"Firma", p_comp_t:"Rakip eSIM firması. Satırlar en uygundan (düşük medyan $/GB) pahalıya sıralıdır.",
  p_cov:"Kapsama", p_cov_t:"Firmanın en az bir paket sunduğu farklı ülke/destinasyon sayısı (benzersiz). Not: Holafly'ın sayısı şehir sayfalarını da içerir, o yüzden yüksektir.",
  p_plans:"Plan", p_plans_t:"Bu firmadan toplanan toplam paket — tüm ülkeler × tüm veri/gün kombinasyonları. Bir satır = bir paket.",
  p_medgb:"Medyan $/GB", p_medgb_t:"Firmanın TÜM GB planlarında birim fiyatın (fiyat ÷ GB) MEDYANI. Medyan, uç değerlerden (1GB planları çok pahalıdır) etkilenmez → tipik birim fiyatı yansıtır. Düşük = daha uygun. Sınırsız planlar hariç. Bar: en yüksek medyana göre orantılı (yeşil=ucuz, kırmızı=pahalı).",
  p_7d:"7g Sınırsız", p_7d_t:"Firmanın tüm ülkelerdeki 7 GÜNLÜK SINIRSIZ planlarının fiyat medyanı. Sınırsız-veri modelli firmaları (ör. Holafly) kıyaslamak için. '—' = 7g sınırsız planı yok.",
  p_gbc:"GB'de en ucuz", p_gbc_t:"Bu firmanın kaç ülkede en düşük $/GB'a sahip olduğu. Her ülkede firmaların en iyi $/GB'ı kıyaslanır; en düşük olan o ülkeyi kazanır. Yüksek = daha çok pazarda birim-fiyat lideri.",
  p_pos:"Konum", p_pos_t:"Medyan $/GB'a göre otomatik: en ucuz üçte bir = Budget, orta = Mid, en pahalı = Premium. GB planı olmayan (sadece sınırsız) firmalar = Unlimited-only.",
  leg_low:"düşük $/GB (uygun)", leg_high:"yüksek $/GB (pahalı)", leg_badge:"= medyan $/GB'a göre konum",
  c_country:"Ülke / destinasyon", c_search:"aramak için yaz…",
  ck_cheapgb:"Buradaki en ucuz $/GB", ck_cheapgb_t:"Seçili ülkede en düşük birim veri fiyatını (fiyat ÷ GB) sunan firma ve o değeri. Firmanın bu ülkedeki EN İYİ (en ucuz) GB planına göre.",
  ck_cheapunl:"En ucuz 7g sınırsız", ck_cheapunl_t:"Seçili ülkede 7 günlük sınırsız planı en ucuz olan firma ve fiyatı. '—' = bu ülkede kimsenin 7g sınırsızı yok.",
  ck_comp:"Buradaki firmalar", ck_comp_s:"aktif", ck_comp_t:"Seçili ülkede en az bir paketi olan firma sayısı.",
  ck_range:"Fiyat aralığı", ck_range_t:"Bu ülkedeki tüm paketlerin en düşük ve en yüksek fiyatı (tüm boyut/süreler dahil).",
  sc_cheap:"En ucuz plan", sc_bestgb:"En iyi $/GB", sc_7d:"7g sınırsız", sc_plans:"Plan sayısı",
  d_label:"🏆 En uygun — boyuta göre ilk 3 (gün fark etmeksizin; sınırsız günlük gösterilir)",
  avg:"ort.", per_day:"günlük",
  d_suffix:"· en uygun", no_exp:"süresiz", w_days:"gün",
  f_size:"Veri boyutu (⌘/Ctrl-tıkla)", f_days:"Süre (gün)", f_reset:"Sıfırla",
  f_cochips:"Rakipler (tıkla: göster/gizle)", f_sizechips:"Veri boyutu (çoklu)",
  opt_all:"Tümü", opt_novalid:"Sabit süre yok",
  t_data:"Veri", t_data_t:"Paketin veri miktarı: GB miktarı veya Sınırsız. Başlığa tıkla → boyuta göre sırala.",
  t_days:"Gün", t_days_t:"Paketin geçerlilik süresi (gün). '—' = sabit süre belirtilmemiş (ör. bazı Breeze GB planları).",
  t_rate:"$/GB · /gün", t_rate_t:"Bu satırdaki EN UCUZ fiyatın birim maliyeti: GB planları → fiyat ÷ GB; Sınırsız → fiyat ÷ gün (günlük). Başlığa tıkla → en uygun birim maliyete göre sırala.",
  t_cheap:"🏆 En ucuz", t_cheap_t:"Bu SATIRIN (aynı veri boyutu + aynı gün) en ucuz firması ve fiyatı. Boyuta göre gün-bağımsız MUTLAK en ucuz için üstteki 'En uygun — boyuta göre' paneline bak.",
  t_empty:"Bu filtrelere uyan plan yok.", firms:"firma", plan_rows:"plan",
  leg_cheaprow:"satırda en ucuz", leg_exp:"en pahalı", leg_gb:"$/GB = fiyat ÷ GB (sadece GB planları)", leg_trophy:"🏆 = o satırdaki en ucuz firma",
  s_events:"Yaklaşan Etkinlikler", s_events_t:"Etkinliğe özel eSIM paketlerini tetikleyen büyük küresel organizasyonlar (Dünya Kupası ölçeğinde). Her etkinliğe 7 gün kala fiyatlar günlük yeniden toplanır. Karta tıkla → o ülkenin fiyatlarına git.",
  ev_2026:"2026 — yaklaşan", ev_2027:"2027 — yaklaşan", ev_left:"gün kaldı", ev_ongoing:"SÜRÜYOR", ev_approx:"yaklaşık",
  tab_overview:"Genel Bakış", tab_country:"Ülke", tab_trends:"Trendler", tab_events:"Etkinlikler",
  beta_t:"Yeni eklendi (beta, otomatik çekiliyor) — hata olabilir",
  cd_next:"Sonraki etkinlik", cd_ongoing:"şu an sürüyor", cd_d:"g", cd_h:"s", cd_m:"dk", cd_s:"sn",
  s_trends:"Fiyat Trendi", s_trends_t:"Bir paketin fiyatının zaman içinde nasıl değiştiği — her haftalık anlık görüntü bir nokta. Ülke ve paket seç, her rakibin çizgisini gör.",
  tr_plan:"Paket (veri · gün)", tr_note_build:"Trend zamanla dolar — her haftalık çalışmada bir nokta; her hafta yeni nokta eklenir.", tr_note_pages:"Trend grafiği canlı (Pages) adresinde yüklenir.", tr_nodata:"Bu seçim için henüz geçmiş yok.",
  badge:{Budget:"Budget", Mid:"Mid", Premium:"Premium", "Unlimited-only":"Unlimited-only"},
 }
};
let LANG = localStorage.getItem("esimlang");
if(!["tr","en"].includes(LANG)) LANG = (navigator.language||"").toLowerCase().startsWith("tr") ? "tr" : "en";
const tr = k => T[LANG][k];

function qm(t){return ` <span class="qm" data-tip="${(t||"").replace(/"/g,'&quot;')}">?</span>`;}
const tipEl=document.createElement("div"); tipEl.className="floattip"; document.body.appendChild(tipEl);
function showTip(el){const t=el.getAttribute("data-tip"); if(!t)return; tipEl.textContent=t; tipEl.style.display="block";
  const r=el.getBoundingClientRect(),w=tipEl.offsetWidth,h=tipEl.offsetHeight;
  let left=r.left+r.width/2-w/2; left=Math.max(8,Math.min(left,innerWidth-w-8));
  let top=r.bottom+8; if(top+h>innerHeight-8) top=r.top-h-8;
  tipEl.style.left=left+"px"; tipEl.style.top=Math.max(8,top)+"px";}
function hideTip(){tipEl.style.display="none";}
document.addEventListener("mouseover",e=>{const q=e.target.closest(".qm"); if(q)showTip(q);});
document.addEventListener("mouseout",e=>{if(e.target.closest(".qm"))hideTip();});
document.addEventListener("click",e=>{const q=e.target.closest(".qm"); if(q){e.preventDefault();e.stopPropagation();showTip(q);}else hideTip();});
addEventListener("scroll",hideTip,true);

function kpi(lab,val,sub,hl,tip){return `<div class="kpi${hl?' hl':''}"><div class="lab">${lab}${tip?qm(tip):""}</div><div class="val">${val}</div><div class="sub2">${sub||""}</div></div>`;}
function badgeName(b){return tr("badge")[b]||b;}
const BETA=new Set(D.beta||[]);
function betaTag(c){return BETA.has(c)?` <span class="betatag" title="${tr("beta_t")}">beta</span>`:"";}

// ---------------- renderers ----------------
function renderStatic(){
  document.documentElement.lang=LANG;
  document.title=tr("title"); $("#h1").textContent=tr("title");
  const staleList=Object.entries(D.stale||{});
  $("#sub").innerHTML=tr("snap")+" "+D.date+" · "+cos.length+" "+tr("w_comp")+" · "
    +D.total.toLocaleString()+" "+tr("w_pack")+" · "+D.countries.length+" "+tr("w_ctry")
    +(staleList.length?` &nbsp;<span class="warn">⚠ ${tr("stale")}: `+staleList.map(([c,d])=>`${c} ${d}`).join(", ")+`</span>`:"");
  $("#h2-market").innerHTML=tr("s_market")+qm(tr("s_market_t"));
  $("#h2-pos").innerHTML=tr("s_pos")+qm(tr("s_pos_t"));
  $("#h2-country").innerHTML=tr("s_country")+qm(tr("s_country_t"));
  $("#h2-detail").innerHTML=tr("s_detail")+qm(tr("s_detail_t"));
  $("#lab-country").textContent=tr("c_country"); $("#search").placeholder=tr("c_search");
  $("#lab-size").textContent=tr("f_size"); $("#lab-days").textContent=tr("f_days"); $("#reset").textContent=tr("f_reset");
  $("#lab-cochips").textContent=tr("f_cochips"); $("#lab-sizechips").textContent=tr("f_sizechips");
  $("#pos-legend").innerHTML=`<span><span class="sw" style="background:var(--barlo)"></span>${tr("leg_low")}</span>`
    +`<span><span class="sw" style="background:var(--barhi)"></span>${tr("leg_high")}</span>`
    +`<span><span class="badge b-Budget">${badgeName("Budget")}</span> / <span class="badge b-Mid">${badgeName("Mid")}</span> / <span class="badge b-Premium">${badgeName("Premium")}</span> ${tr("leg_badge")}</span>`;
  $("#tbl-legend").innerHTML=`<span><span class="sw" style="background:var(--lowtx)"></span>${tr("leg_cheaprow")}</span>`
    +`<span><span class="sw" style="background:var(--hightx)"></span>${tr("leg_exp")}</span>`
    +`<span>${tr("leg_gb")}</span><span>${tr("leg_trophy")}</span>`;
  $("#h2-trends").innerHTML=tr("s_trends")+qm(tr("s_trends_t"));
  $("#lab-trend-country").textContent=tr("c_country");
  $("#lab-trend-plan").textContent=tr("tr_plan");
  $("#h2-events").innerHTML=tr("s_events")+qm(tr("s_events_t"));
  [["overview","tab_overview"],["country","tab_country"],["trends","tab_trends"],["events","tab_events"]]
    .forEach(([t,k])=>{const b=document.querySelector(`.tabs button[data-tab="${t}"]`); if(b)b.textContent=tr(k);});
}
function switchTab(t){
  document.querySelectorAll(".tabs button").forEach(x=>x.classList.toggle("on",x.dataset.tab===t));
  document.querySelectorAll(".panel").forEach(p=>p.classList.toggle("on",p.dataset.tab===t));
  window.scrollTo({top:0,behavior:"smooth"});
}

// ---------------- upcoming events + live countdown ----------------
function evList(){
  const now=new Date();
  return (D.events||[]).map(e=>({...e, s:new Date(e.start+"T00:00:00"), e2:new Date((e.end||e.start)+"T23:59:59")}))
    .filter(e=>e.e2>=now).sort((a,b)=>a.s-b.s);
}
function fmtD(iso){return new Date(iso+"T00:00:00").toLocaleDateString(LANG==="tr"?"tr-TR":"en-US",{day:"numeric",month:"short",year:"numeric"});}
function evCard(e){
  const now=new Date(), nm=e.name[LANG]||e.name.en, on=e.s<=now&&now<=e.e2;
  const days=Math.ceil((e.s-now)/864e5);
  const status=on?`<span class="evpill on">${tr("ev_ongoing")}</span>`:`<span class="evpill">${days} ${tr("ev_left")}</span>`;
  const dr=fmtD(e.start)+(e.end&&e.end!==e.start?" – "+fmtD(e.end):"");
  const linkable=D.countries.includes(e.country);
  return `<div class="evcard" data-country="${linkable?e.country:''}">
    <div class="evhead"><span class="evflag">${e.flag||"📅"}</span><span class="evname">${nm}${e.approx?`<span class="evapx">${tr("ev_approx")}</span>`:""}</span></div>
    <div class="evmeta">${e.country||""} · ${dr}</div>
    ${status}</div>`;
}
function renderEvents(){
  const up=evList();
  const y26=up.filter(e=>e.start<"2027"), y27=up.filter(e=>e.start>="2027");
  $("#events-2026").innerHTML=y26.length?`<div class="glab">${tr("ev_2026")}</div><div class="evgrid">${y26.map(evCard).join("")}</div>`:"";
  $("#events-2027").innerHTML=y27.length?`<div class="glab" style="margin-top:14px">${tr("ev_2027")}</div><div class="evgrid">${y27.map(evCard).join("")}</div>`:"";
}
function tickCountdown(){
  const up=evList();
  if(!up.length){$("#cdbar").innerHTML="";return;}
  const e=up[0], now=new Date(), nm=e.name[LANG]||e.name.en, tag=`${nm} ${e.flag||""} ${e.country||""}`;
  if(e.s<=now){$("#cdbar").innerHTML=`<div class="cdinner">⏳ <b>${nm}</b> ${e.flag||""} — <b>${tr("cd_ongoing")}</b></div>`;return;}
  let ms=e.s-now; const d=Math.floor(ms/864e5); ms-=d*864e5; const h=Math.floor(ms/36e5); ms-=h*36e5; const m=Math.floor(ms/6e4); ms-=m*6e4; const s=Math.floor(ms/1e3);
  $("#cdbar").innerHTML=`<div class="cdinner">⏳ ${tr("cd_next")}: <b>${tag}</b> — <b>${d}${tr("cd_d")} ${h}${tr("cd_h")} ${m}${tr("cd_m")} ${s}${tr("cd_s")}</b></div>`;
}

// ---------------- price trends (history.json, fetched on Pages) ----------------
let HIST=null, trendCountry=null, trendPlan=null;
const PALETTE=["#5b8cff","#8b5cf6","#54e39a","#e6c34d","#ff8098","#3bd07f","#ff9f45","#4dd0e1"];
function loadHistory(){
  fetch("history.json").then(r=>r.ok?r.json():Promise.reject()).then(h=>{HIST=h;initTrends();})
    .catch(()=>{$("#trend-note").textContent=tr("tr_note_pages");});
}
function initTrends(){
  const cs=Object.keys(HIST.countries).sort();
  trendCountry = cs.includes(country)?country:(cs.includes("United States")?"United States":cs[0]);
  $("#trend-country").innerHTML=cs.map(c=>`<option${c===trendCountry?" selected":""}>${c}</option>`).join("");
  fillTrendPlans(); drawTrend();
}
function fillTrendPlans(){
  if(!HIST) return;
  const keys=Object.keys(HIST.countries[trendCountry]||{});
  const plans=[...new Set(keys.map(k=>{const a=k.split("|");return a[1]+"||"+a[2];}))]
    .sort((a,b)=>{const x=a.split("||"),y=b.split("||");return sizeOrder(x[0],y[0])||((+x[1]||0)-(+y[1]||0));});
  if(!plans.includes(trendPlan)){ // default = the plan the most competitors offer
    const cd=HIST.countries[trendCountry]||{}; let best=null,bn=-1;
    for(const p of plans){const a=p.split("||");let c=0;for(const co of cos)if(cd[co+"|"+a[0]+"|"+a[1]])c++;if(c>bn){bn=c;best=p;}}
    trendPlan=best||plans[0]||null;
  }
  $("#trend-plan").innerHTML=plans.map(p=>{const a=p.split("||");
    const lbl=a[0]+" · "+(a[1]?a[1]+" "+tr("w_days"):tr("no_exp"));
    return `<option value="${p}"${p===trendPlan?" selected":""}>${lbl}</option>`;}).join("");
}
function drawTrend(){
  if(!HIST||!trendPlan){$("#trend-chart").innerHTML="";return;}
  const a=trendPlan.split("||"), pd=a[0], pn=a[1];
  const cd=HIST.countries[trendCountry]||{}, series={};
  for(const co of cos){const k=co+"|"+pd+"|"+pn; if(cd[k]) series[co]=cd[k];}
  $("#trend-chart").innerHTML=chartSVG(series,HIST.dates);
  $("#trend-note").textContent = HIST.dates.length<=1 ? tr("tr_note_build") : "";
}
function chartSVG(series,dates){
  const list=Object.keys(series);
  if(!list.length) return `<div class="empty">${tr("tr_nodata")}</div>`;
  const W=760,H=300,mL=48,mR=14,mT=14,mB=34, iw=W-mL-mR, ih=H-mT-mB, n=dates.length;
  let vals=[]; list.forEach(c=>series[c].forEach(v=>{if(v!=null)vals.push(v);}));
  let mn=Math.min(...vals), mx=Math.max(...vals);
  if(mn===mx){mn=Math.max(0,mn-1); mx=mx+1;}
  const X=i=> n<=1 ? mL+iw/2 : mL+iw*i/(n-1);
  const Y=v=> mT+ih*(1-(v-mn)/(mx-mn));
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:100%;font-size:11px;overflow:visible">`;
  [mn,(mn+mx)/2,mx].forEach(v=>{const y=Y(v);
    s+=`<line x1="${mL}" y1="${y.toFixed(1)}" x2="${W-mR}" y2="${y.toFixed(1)}" stroke="var(--line)"/>`
      +`<text x="${mL-6}" y="${(y+3).toFixed(1)}" text-anchor="end" fill="var(--muted)">$${v.toFixed(0)}</text>`;});
  (n<=1?[0]:[0,n-1]).forEach(i=>{s+=`<text x="${X(i).toFixed(1)}" y="${H-12}" text-anchor="middle" fill="var(--muted)">${dates[i]}</text>`;});
  list.forEach(c=>{const col=PALETTE[cos.indexOf(c)%PALETTE.length]; let d="",on=false;
    series[c].forEach((v,i)=>{if(v==null){on=false;return;}const x=X(i).toFixed(1),y=Y(v).toFixed(1);d+=(on?" L":" M")+x+" "+y;on=true;});
    if(d) s+=`<path d="${d}" fill="none" stroke="${col}" stroke-width="2"/>`;
    series[c].forEach((v,i)=>{if(v!=null)s+=`<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="3" fill="${col}"/>`;});
  });
  s+=`</svg><div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:10px;font-size:12px">`
    +list.map(c=>`<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${PALETTE[cos.indexOf(c)%PALETTE.length]};margin-right:5px"></span>${c}</span>`).join("")+`</div>`;
  return s;
}

function renderMarket(){
  const L=M.leaders;
  $("#mkpis").innerHTML=[
    kpi(tr("k_comp"),cos.length,tr("k_comp_s"),false,tr("k_comp_t")),
    kpi(tr("k_pack"),D.total.toLocaleString(),tr("k_pack_s"),false,tr("k_pack_t")),
    kpi(tr("k_cov"),L.coverage,PC[L.coverage].countries+" "+tr("ctry"),true,tr("k_cov_t")),
    kpi(tr("k_val"),L.value||"—",L.value?money(PC[L.value].avgGB)+" "+tr("k_val_s"):"",true,tr("k_val_t")),
    kpi(tr("k_gbl"),L.gbLeader,PC[L.gbLeader].gbLeader+" "+tr("cheapest_in"),true,tr("k_gbl_t")),
    kpi(tr("k_unl"),L.unlimLeader,PC[L.unlimLeader].unlimLeader+" "+tr("cheapest_in")+" (7"+tr("w_days")[0]+")",true,tr("k_unl_t")),
  ].join("");
  const rows=cos.map(c=>({c,...PC[c]})).sort((a,b)=>(a.avgGB??1e9)-(b.avgGB??1e9));
  const head=`<thead><tr>
    <th class="l">${tr("p_comp")}${qm(tr("p_comp_t"))}</th>
    <th>${tr("p_cov")}${qm(tr("p_cov_t"))}</th>
    <th>${tr("p_plans")}${qm(tr("p_plans_t"))}</th>
    <th class="l">${tr("p_medgb")}${qm(tr("p_medgb_t"))}</th>
    <th>${tr("p_7d")}${qm(tr("p_7d_t"))}</th>
    <th>${tr("p_gbc")}${qm(tr("p_gbc_t"))}</th>
    <th>${tr("p_pos")}${qm(tr("p_pos_t"))}</th></tr></thead>`;
  let body="<tbody>";
  for(const r of rows){
    const bar=r.avgGB!=null
      ? `<div class="bar"><i style="width:${Math.max(6,r.barPct)}%;background:linear-gradient(90deg,var(--barlo),var(--barhi))"></i></div> <span class="num">${money(r.avgGB)}</span>`
      : `<span class="na">—</span>`;
    body+=`<tr><td class="l"><b>${r.c}</b>${betaTag(r.c)}</td><td class="num">${r.countries}</td>
      <td class="num">${r.plans.toLocaleString()}</td><td class="l">${bar}</td>
      <td class="num">${r.unlim7!=null?money(r.unlim7):'<span class=na>—</span>'}</td>
      <td class="num">${r.gbLeader} ${tr("ctry")}</td>
      <td><span class="badge b-${r.badge}">${badgeName(r.badge)}</span></td></tr>`;
  }
  $("#posTbl").innerHTML=head+body+"</tbody>";
}

let country = D.countries.includes("United States")?"United States":D.countries[0];
function fillCountry(f){
  const el=$("#country");
  const list=D.countries.filter(c=>!f||c.toLowerCase().includes(f.toLowerCase()));
  el.innerHTML=list.map(c=>`<option${c===country?" selected":""}>${c}</option>`).join("");
  if(!list.includes(country)&&list.length){country=list[0];el.value=country;}
}
function cRecs(){return D.recs.filter(r=>r.c===country);}

function renderCountry(){
  const rows=cRecs(); const stat={};
  for(const r of rows){
    const s=stat[r.co]=stat[r.co]||{plans:0,minRate:null,cheapest:null,unlim7:null};
    s.plans++;
    if(r.g){const rate=r.p/r.g; if(s.minRate==null||rate<s.minRate)s.minRate=rate;}
    if(s.cheapest==null||r.p<s.cheapest.p)s.cheapest=r;
    if(r.d==="Unlimited"&&r.n===7&&(s.unlim7==null||r.p<s.unlim7))s.unlim7=r.p;
  }
  const active=Object.keys(stat);
  const gbL=active.filter(c=>stat[c].minRate!=null).sort((a,b)=>stat[a].minRate-stat[b].minRate)[0];
  const uL=active.filter(c=>stat[c].unlim7!=null).sort((a,b)=>stat[a].unlim7-stat[b].unlim7)[0];
  const ap=rows.map(r=>r.p);
  $("#ckpis").innerHTML=[
    kpi(tr("ck_cheapgb"),gbL||"—",gbL?money(stat[gbL].minRate)+" /GB":"",true,tr("ck_cheapgb_t")),
    kpi(tr("ck_cheapunl"),uL||"—",uL?money(stat[uL].unlim7):"—",true,tr("ck_cheapunl_t")),
    kpi(tr("ck_comp"),active.length,tr("ck_comp_s"),false,tr("ck_comp_t")),
    kpi(tr("ck_range"),ap.length?money(Math.min(...ap)):"—",ap.length?"→ "+money(Math.max(...ap)):"",false,tr("ck_range_t")),
  ].join("");
  $("#score").innerHTML=active.sort((a,b)=>(stat[a].minRate??1e9)-(stat[b].minRate??1e9)).map(c=>{
    const s=stat[c],ch=s.cheapest;
    return `<div class="sc"><div class="co">${c}${betaTag(c)} <span class="badge b-${PC[c].badge}" style="font-size:10px">${badgeName(PC[c].badge)}</span></div>
      <div class="row"><span>${tr("sc_cheap")}</span><b>${ch?ch.d+(ch.n?"/"+ch.n+tr("w_days")[0]:"")+" · "+money(ch.p):"—"}</b></div>
      <div class="row"><span>${tr("sc_bestgb")}</span><b>${s.minRate!=null?money(s.minRate):"—"}</b></div>
      <div class="row"><span>${tr("sc_7d")}</span><b>${s.unlim7!=null?money(s.unlim7):"—"}</b></div>
      <div class="row"><span>${tr("sc_plans")}</span><b>${s.plans}</b></div></div>`;
  }).join("");
}

let sizes=new Set(), days="All", hidden=new Set(), sortCol=null, sortDir=1;
function gbVal(d){if(d==="Unlimited")return 1e9;const m=d.match(/([\d.]+)\s*GB/);return m?parseFloat(m[1]):1e8;}
function sizeOrder(a,b){if(a==="Unlimited")return -1;if(b==="Unlimited")return 1;return gbVal(a)-gbVal(b);}
function sizeMatch(r){return sizes.size===0||sizes.has(r.d);}
function shownCos(){return cos.filter(c=>!hidden.has(c));}
function fillCoChips(){$("#cochips").innerHTML=cos.map(c=>`<span class="chip co${hidden.has(c)?"":" on"}" data-c="${c}">${c}</span>`).join("");}
function fillSize(){
  const avail=[...new Set(cRecs().map(r=>r.d))].sort(sizeOrder);
  for(const s of [...sizes]) if(!avail.includes(s)) sizes.delete(s);
  $("#sizechips").innerHTML=[`<span class="chip${sizes.size===0?" on":""}" data-v="__all">${tr("opt_all")}</span>`]
    .concat(avail.map(s=>`<span class="chip${sizes.has(s)?" on":""}" data-v="${s}">${s}</span>`)).join("");
  const el=$("#size"),cur=[...el.options].map(o=>o.value);
  if(cur.join("|")!==avail.join("|")) el.innerHTML=avail.map(s=>`<option value="${s}">${s}</option>`).join("");
  for(const o of el.options)o.selected=sizes.has(o.value);
}
function fillDays(){   // validity days as clickable chips (single-select)
  let ds=[...new Set(cRecs().filter(sizeMatch).map(r=>r.n))];
  const blank=ds.includes(null); ds=ds.filter(x=>x!=null).sort((a,b)=>a-b);
  if(days!=="All"&&days!=="none"&&!ds.map(String).includes(String(days)))days="All";
  let c=`<span class="chip${days==="All"?" on":""}" data-d="All">${tr("opt_all")}</span>`;
  c+=ds.map(d=>`<span class="chip${String(d)===String(days)?" on":""}" data-d="${d}">${d}${tr("w_days")[0]}</span>`).join("");
  if(blank)c+=`<span class="chip${days==="none"?" on":""}" data-d="none">${tr("opt_novalid")}</span>`;
  $("#daychips").innerHTML=c;
}
function renderDeals(vis){
  // per size: each competitor's cheapest offer (metric = total, or per-day for Unlimited)
  const bySize={};
  for(const r of vis){
    const unl=r.d==="Unlimited"&&r.n;
    const metric=unl?r.p/r.n:r.p;
    const m=(bySize[r.d]=bySize[r.d]||{});
    if(!m[r.co]||metric<m[r.co].m) m[r.co]={co:r.co,p:r.p,n:r.n,m:metric};
  }
  const list=Object.keys(bySize).sort(sizeOrder);
  if(!list.length){$("#dealwrap").innerHTML="";return;}
  const cards=list.map(s=>{
    const unl=s==="Unlimited";
    const offers=Object.values(bySize[s]).sort((a,b)=>a.m-b.m);
    const avg=offers.reduce((t,o)=>t+o.m,0)/offers.length;
    const fmt=o=>unl?money(o.m)+"/"+tr("w_days")[0]:money(o.p);
    const rows=offers.slice(0,3).map((o,i)=>
      `<div class="drow"><span class="drank">${i+1}</span><span class="dco2">${o.co}${betaTag(o.co)}</span><span class="dval">${fmt(o)}</span></div>`).join("");
    const avgTxt=unl?money(avg)+"/"+tr("w_days")[0]:money(avg);
    return `<div class="deal"><div class="dhead"><span class="ds">${s}${unl?" · "+tr("per_day"):""}</span>`
      +`<span class="davg">${tr("avg")} ${avgTxt} · ${offers.length}</span></div>${rows}</div>`;
  }).join("");
  $("#dealwrap").innerHTML=`<label class="glab">${tr("d_label")}</label><div class="deals">${cards}</div>`;
}
function minPx(p){return Math.min(...Object.values(p.px));}
function renderTable(){
  const show=shownCos();
  let rows=cRecs().filter(sizeMatch);
  if(days==="none")rows=rows.filter(r=>r.n==null);
  else if(days!=="All")rows=rows.filter(r=>String(r.n)===String(days));
  const vis=rows.filter(r=>!hidden.has(r.co));
  renderDeals(vis);
  const plans={};
  for(const r of vis){const k=r.d+"||"+(r.n==null?"":r.n);const p=(plans[k]=plans[k]||{d:r.d,n:r.n,g:r.g,px:{}});p.px[r.co]=(p.px[r.co]==null)?r.p:Math.min(p.px[r.co],r.p);}
  let arr=Object.values(plans);
  const dfl=(a,b)=>sizeOrder(a.d,b.d)||((a.n||0)-(b.n||0));
  arr.sort((a,b)=>{
    if(sortCol===null)return dfl(a,b);
    if(sortCol==="data")return sizeOrder(a.d,b.d)*sortDir||((a.n||0)-(b.n||0));
    if(sortCol==="days"){const an=a.n==null?1e9:a.n,bn=b.n==null?1e9:b.n;return (an-bn)*sortDir||sizeOrder(a.d,b.d);}
    if(sortCol==="rate"){const rt=x=>x.g?minPx(x)/x.g:(x.n?minPx(x)/x.n:1e9);return (rt(a)-rt(b))*sortDir||dfl(a,b);}
    const av=a.px[sortCol],bv=b.px[sortCol];
    if(av==null&&bv==null)return dfl(a,b); if(av==null)return 1; if(bv==null)return -1;
    return (av-bv)*sortDir||dfl(a,b);
  });
  const t=$("#tbl");
  if(!arr.length){t.innerHTML=`<tbody><tr><td class="empty">${tr("t_empty")}</td></tr></tbody>`;$("#count").textContent="";return;}
  const arw=c=>c===sortCol?`<span class="arw">${sortDir>0?"▲":"▼"}</span>`:"";
  const th=(id,l,cls,tip)=>`<th class="${cls||''}${id===sortCol?' sorted':''}" data-sort="${id}">${l}${tip?qm(tip):""}${arw(id)}</th>`;
  let head="<thead><tr>"+th("data",tr("t_data"),"l",tr("t_data_t"))+th("days",tr("t_days"),"",tr("t_days_t"))
    +th("rate",tr("t_rate"),"",tr("t_rate_t"))+show.map(c=>th(c,c+betaTag(c))).join("")
    +`<th class="l">${tr("t_cheap")}${qm(tr("t_cheap_t"))}</th></tr></thead>`;
  let body="<tbody>";
  for(const p of arr){
    const vals=show.map(c=>p.px[c]).filter(v=>v!=null);
    if(!vals.length)continue;
    const lo=Math.min(...vals),hi=Math.max(...vals);
    const winC=show.find(c=>p.px[c]===lo);
    body+=`<tr><td class="l"><b>${p.d}</b></td><td class="num">${p.n==null?"—":p.n}</td>`
      +`<td class="num" style="color:var(--muted)">${p.g?money(lo/p.g):(p.n?money(lo/p.n)+"/"+tr("w_days")[0]:"—")}</td>`;
    for(const c of show){const v=p.px[c];
      if(v==null){body+=`<td class="price na">—</td>`;continue;}
      let cls="price"; if(vals.length>1&&v===lo)cls+=" low"; else if(vals.length>1&&v===hi)cls+=" high";
      body+=`<td class="${cls}">${money(v)}</td>`;}
    body+=`<td class="l"><span class="win">${winC}</span> ${money(lo)}</td></tr>`;
  }
  t.innerHTML=head+body+"</tbody>";
  $("#count").textContent=`${arr.length} ${tr("plan_rows")} · ${country} · ${show.length}/${cos.length} ${tr("firms")}`
    +(sizes.size?" · "+[...sizes].join(", "):"")+(days!=="All"?" · "+days+tr("w_days")[0]:"");
}

function refreshCountry(){fillSize();fillDays();renderCountry();renderTable();}
function renderAll(){renderStatic();renderEvents();tickCountdown();renderMarket();fillCountry($("#search").value);fillCoChips();refreshCountry();if(HIST){fillTrendPlans();drawTrend();}}

$("#langtog").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;
  LANG=b.dataset.l; localStorage.setItem("esimlang",LANG);
  [...$("#langtog").children].forEach(x=>x.classList.toggle("on",x.dataset.l===LANG));
  renderAll();});
$("#search").addEventListener("input",e=>{fillCountry(e.target.value);country=$("#country").value;sizes.clear();days="All";refreshCountry();});
$("#country").addEventListener("change",e=>{country=e.target.value;sizes.clear();days="All";refreshCountry();});
$("#size").addEventListener("change",e=>{sizes=new Set([...e.target.selectedOptions].map(o=>o.value));days="All";fillSize();fillDays();renderTable();});
$("#sizechips").addEventListener("click",e=>{if(!e.target.classList.contains("chip"))return;const v=e.target.dataset.v;if(v==="__all")sizes.clear();else sizes.has(v)?sizes.delete(v):sizes.add(v);days="All";fillSize();fillDays();renderTable();});
$("#daychips").addEventListener("click",e=>{if(!e.target.classList.contains("chip"))return;days=e.target.dataset.d;fillDays();renderTable();});
$("#cochips").addEventListener("click",e=>{if(!e.target.classList.contains("chip"))return;const c=e.target.dataset.c;hidden.has(c)?hidden.delete(c):hidden.add(c);if(hidden.size>=cos.length)hidden.delete(c);fillCoChips();renderTable();});
$("#tbl").addEventListener("click",e=>{if(e.target.closest(".qm"))return;const h=e.target.closest("th[data-sort]");if(!h)return;const c=h.dataset.sort;if(sortCol===c)sortDir=-sortDir;else{sortCol=c;sortDir=1;}renderTable();});
$("#reset").addEventListener("click",()=>{sizes.clear();days="All";hidden.clear();sortCol=null;sortDir=1;fillCoChips();refreshCountry();});
$("#trend-country").addEventListener("change",e=>{trendCountry=e.target.value;fillTrendPlans();drawTrend();});
$("#trend-plan").addEventListener("change",e=>{trendPlan=e.target.value;drawTrend();});
// click an event card -> jump to that country's prices
document.addEventListener("click",e=>{const c=e.target.closest(".evcard");if(!c||!c.dataset.country)return;
  country=c.dataset.country; sizes.clear(); days="All"; $("#search").value=""; fillCountry(""); $("#country").value=country;
  refreshCountry(); switchTab("country");});
$("#tabs").addEventListener("click",e=>{const b=e.target.closest("button[data-tab]");if(b)switchTab(b.dataset.tab);});
$("#cdbar").style.cursor="pointer";
$("#cdbar").addEventListener("click",()=>switchTab("events"));

// init
[...$("#langtog").children].forEach(x=>x.classList.toggle("on",x.dataset.l===LANG));
renderAll();
loadHistory();
setInterval(tickCountdown,1000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
