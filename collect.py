#!/usr/bin/env python3
"""
eSIM competitor price monitor  —  production collector.

Collects per-country package prices from competitor websites and writes a
normalized CSV (one row per package) + a JSON snapshot, dated by day.

Sources (all public pages, no login):
  - Airalo   : country pages `airalo.com/{slug}-esim`     (prices in aria-labels)
  - Holafly  : country pages `esim.holafly.com/esim-{slug}`(pdp price table)
  - esim.io  : country pages `esim.io/destinations/esim-{slug}` (plan cards)
  - Breeze   : Shopify `breezesim.com/products.json`       (catalog JSON)

Countries are auto-enumerated from each site every run (sitemaps / index page),
so new countries the competitors add are picked up automatically.

Nomad is a JavaScript SPA (prices not in raw HTML) and is intentionally NOT
included here — it needs a headless browser (see README).

Usage:
  python3 collect.py                     # ALL countries, all 4 providers
  python3 collect.py --limit 10          # first 10 countries per provider (test)
  python3 collect.py --providers airalo,breeze
"""
import argparse
import concurrent.futures as cf
import csv
import datetime
import json
import os
import re
import sys
import urllib.request
import urllib.error

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
TIMEOUT = 30
WORKERS = 8
HERE = os.path.dirname(os.path.abspath(__file__))

# ---- canonical country name (aligns different provider slugs) ----
ALIASES = {
    "usa": "United States", "united-states": "United States",
    "united-states-of-america": "United States",
    "uk": "United Kingdom", "united-kingdom": "United Kingdom",
    "great-britain": "United Kingdom",
    "uae": "United Arab Emirates", "united-arab-emirates": "United Arab Emirates",
    "south-korea": "South Korea", "korea": "South Korea",
    "republic-of-korea": "South Korea",
    "czech-republic": "Czechia", "czechia": "Czechia",
    "hong-kong": "Hong Kong", "hong-kong-china": "Hong Kong",
    "russia": "Russia", "russian-federation": "Russia",
    "turkey": "Turkey", "turkiye": "Turkey",
    "vietnam": "Vietnam", "viet-nam": "Vietnam",
}


def canon(slug):
    s = slug.strip().lower().strip("-")
    if s in ALIASES:
        return ALIASES[s]
    return s.replace("-", " ").title()


# ISO-3 -> canonical country name (for Ubigi, which tags plans by ISO code)
ISO3 = {
 "AFG":"Afghanistan","ALB":"Albania","DZA":"Algeria","AND":"Andorra","AGO":"Angola",
 "AIA":"Anguilla","ATG":"Antigua And Barbuda","ARG":"Argentina","ARM":"Armenia",
 "ABW":"Aruba","AUS":"Australia","AUT":"Austria","AZE":"Azerbaijan","BHS":"Bahamas",
 "BHR":"Bahrain","BGD":"Bangladesh","BRB":"Barbados","BLR":"Belarus","BEL":"Belgium",
 "BLZ":"Belize","BEN":"Benin","BMU":"Bermuda","BTN":"Bhutan","BOL":"Bolivia",
 "BIH":"Bosnia And Herzegovina","BWA":"Botswana","BRA":"Brazil","BRN":"Brunei",
 "BGR":"Bulgaria","BFA":"Burkina Faso","BDI":"Burundi","KHM":"Cambodia","CMR":"Cameroon",
 "CAN":"Canada","CPV":"Cape Verde","CYM":"Cayman Islands","CAF":"Central African Republic",
 "TCD":"Chad","CHL":"Chile","CHN":"China","COL":"Colombia","COM":"Comoros","COG":"Congo",
 "COD":"Congo","CRI":"Costa Rica","CIV":"Ivory Coast","HRV":"Croatia","CUB":"Cuba",
 "CUW":"Curacao","CYP":"Cyprus","CZE":"Czechia","DNK":"Denmark","DJI":"Djibouti",
 "DMA":"Dominica","DOM":"Dominican Republic","ECU":"Ecuador","EGY":"Egypt",
 "SLV":"El Salvador","GNQ":"Equatorial Guinea","EST":"Estonia","SWZ":"Eswatini",
 "ETH":"Ethiopia","FJI":"Fiji","FIN":"Finland","FRA":"France","GUF":"French Guiana",
 "PYF":"French Polynesia","GAB":"Gabon","GMB":"Gambia","GEO":"Georgia","DEU":"Germany",
 "GHA":"Ghana","GIB":"Gibraltar","GRC":"Greece","GRL":"Greenland","GRD":"Grenada",
 "GLP":"Guadeloupe","GUM":"Guam","GTM":"Guatemala","GIN":"Guinea","GNB":"Guinea-Bissau",
 "GUY":"Guyana","HTI":"Haiti","HND":"Honduras","HKG":"Hong Kong","HUN":"Hungary",
 "ISL":"Iceland","IND":"India","IDN":"Indonesia","IRQ":"Iraq","IRL":"Ireland",
 "ISR":"Israel","ITA":"Italy","JAM":"Jamaica","JPN":"Japan","JOR":"Jordan",
 "KAZ":"Kazakhstan","KEN":"Kenya","KOR":"South Korea","KWT":"Kuwait","KGZ":"Kyrgyzstan",
 "LAO":"Laos","LVA":"Latvia","LBN":"Lebanon","LSO":"Lesotho","LBR":"Liberia",
 "LIE":"Liechtenstein","LTU":"Lithuania","LUX":"Luxembourg","MAC":"Macau",
 "MDG":"Madagascar","MWI":"Malawi","MYS":"Malaysia","MDV":"Maldives","MLI":"Mali",
 "MLT":"Malta","MTQ":"Martinique","MRT":"Mauritania","MUS":"Mauritius","MEX":"Mexico",
 "MDA":"Moldova","MCO":"Monaco","MNG":"Mongolia","MNE":"Montenegro","MSR":"Montserrat",
 "MAR":"Morocco","MOZ":"Mozambique","MMR":"Myanmar","NAM":"Namibia","NPL":"Nepal",
 "NLD":"Netherlands","NCL":"New Caledonia","NZL":"New Zealand","NIC":"Nicaragua",
 "NER":"Niger","NGA":"Nigeria","MKD":"North Macedonia","NOR":"Norway","OMN":"Oman",
 "PAK":"Pakistan","PSE":"Palestine","PAN":"Panama","PNG":"Papua New Guinea",
 "PRY":"Paraguay","PER":"Peru","PHL":"Philippines","POL":"Poland","PRT":"Portugal",
 "PRI":"Puerto Rico","QAT":"Qatar","REU":"Reunion","ROU":"Romania","RUS":"Russia",
 "RWA":"Rwanda","KNA":"Saint Kitts And Nevis","LCA":"Saint Lucia",
 "VCT":"Saint Vincent And The Grenadines","WSM":"Samoa","SMR":"San Marino",
 "SAU":"Saudi Arabia","SEN":"Senegal","SRB":"Serbia","SYC":"Seychelles",
 "SLE":"Sierra Leone","SGP":"Singapore","SVK":"Slovakia","SVN":"Slovenia",
 "SLB":"Solomon Islands","ZAF":"South Africa","SSD":"South Sudan","ESP":"Spain",
 "LKA":"Sri Lanka","SDN":"Sudan","SUR":"Suriname","SWE":"Sweden","CHE":"Switzerland",
 "TWN":"Taiwan","TJK":"Tajikistan","TZA":"Tanzania","THA":"Thailand","TLS":"Timor-Leste",
 "TGO":"Togo","TON":"Tonga","TTO":"Trinidad And Tobago","TUN":"Tunisia","TUR":"Turkey",
 "TKM":"Turkmenistan","TCA":"Turks And Caicos Islands","UGA":"Uganda","UKR":"Ukraine",
 "ARE":"United Arab Emirates","GBR":"United Kingdom","USA":"United States",
 "URY":"Uruguay","UZB":"Uzbekistan","VUT":"Vanuatu","VEN":"Venezuela","VNM":"Vietnam",
 "VGB":"British Virgin Islands","VIR":"United States Virgin Islands","YEM":"Yemen",
 "ZMB":"Zambia","ZWE":"Zimbabwe","MYT":"Mayotte","GGY":"Guernsey","JEY":"Jersey",
 "IMN":"Isle Of Man","FRO":"Faroe Islands","KOS":"Kosovo","XKX":"Kosovo",
 "NRU":"Nauru","BLM":"Saint Barthelemy","MAF":"Saint Martin","KIR":"Kiribati",
 "TUV":"Tuvalu","PLW":"Palau","MHL":"Marshall Islands","FSM":"Micronesia",
 "STP":"Sao Tome And Principe","SXM":"Sint Maarten","ATF":"French Southern Territories",
 "COK":"Cook Islands","NIU":"Niue","WLF":"Wallis And Futuna","WMA":"Global",
}


def fetch(url, retries=1, backoff=3):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                import time
                time.sleep(backoff * (attempt + 1))
                continue
            return e.code, ""
        except Exception:
            return 0, ""
    return 0, ""


def norm_data(s):
    s = s.strip()
    if re.search(r"unlim", s, re.I):
        return "Unlimited"
    m = re.search(r"([\d.]+)\s*(GB|MB|TB)", s, re.I)
    if m:
        return f"{m.group(1)} {m.group(2).upper()}"
    return s


# =========================================================================
#  ENUMERATION  (find every country slug per provider)
# =========================================================================
def enum_airalo():
    _, xml = fetch("https://www.airalo.com/sitemap-v2-countries.xml")
    slugs = re.findall(r"https://www\.airalo\.com/([a-z0-9-]+)-esim\b", xml)
    return sorted(set(slugs))


def enum_holafly():
    _, xml = fetch("https://esim.holafly.com/product-sitemap.xml")
    slugs = re.findall(r"https://esim\.holafly\.com/esim-([a-z0-9-]+)", xml)
    return sorted(set(slugs))


def enum_esimio():
    _, html = fetch("https://esim.io/destinations")
    slugs = re.findall(r"/destinations/esim-([a-z0-9-]+)", html)
    return sorted(set(slugs))


# =========================================================================
#  PARSERS  (one country page -> list of packages)
# =========================================================================
def parse_airalo(slug):
    """Parse ALL packages (Unlimited + fixed-GB 'Standard') from the Nuxt data
    blob. Only the active tab exposes aria-labels, so the blob is the reliable
    source for every package type."""
    url = f"https://www.airalo.com/{slug}-esim"
    code, html = fetch(url)
    rows = []
    if code != 200:
        return rows, url, code
    m = re.search(r'id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
        except Exception:
            data = None
        if isinstance(data, list):
            def rz(v):
                return data[v] if isinstance(v, int) and 0 <= v < len(data) else v
            for p in data:
                if not (isinstance(p, dict) and "is_unlimited" in p
                        and "day" in p and "price" in p and "data" in p):
                    continue
                days = rz(p["day"])
                if not isinstance(days, int) or days <= 0:
                    continue
                # skip data+calls+texts bundles — not useful for price comparison
                voice, text = rz(p.get("voice")), rz(p.get("text"))
                if (voice not in (None, 0, "0")) or (text not in (None, 0, "0")):
                    continue
                unlimited = rz(p["is_unlimited"]) is True
                dlabel = "Unlimited" if unlimited else norm_data(str(rz(p["data"])))
                po = rz(p["price"])
                if not isinstance(po, dict):
                    continue
                amt = rz(po.get("amount"))
                try:
                    price = float(amt)
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                rows.append({"data": dlabel, "days": days, "price_usd": price})
    if rows:
        return _dedup(rows), url, code
    # fallback: aria-labels (active tab only) if the blob shape ever changes
    for mm in re.finditer(
            r'aria-label="Select\s+(.+?)\s+for\s+\$([0-9]+(?:\.[0-9]+)?)\s+USD', html):
        label, price = mm.group(1), mm.group(2)
        parts = label.rsplit(" - ", 1)
        d = norm_data(parts[0]) if len(parts) == 2 else norm_data(label)
        dm = re.search(r"(\d+)\s*day", parts[-1], re.I)
        rows.append({"data": d, "days": int(dm.group(1)) if dm else "",
                     "price_usd": float(price)})
    return _dedup(rows), url, code


def parse_holafly(slug):
    url = f"https://esim.holafly.com/esim-{slug}/"
    code, html = fetch(url)
    rows = []
    if code != 200:
        return rows, url, code
    pairs = re.findall(
        r'pdp-table__row-header">\s*(\d+)\s*days\s*</th>.*?<span>\s*\$?\s*'
        r'([0-9]+[.,][0-9]{2})\s*</span>', html, re.S)
    for days, price in pairs:
        price = float(price.replace(",", "."))
        if price < 1:
            continue
        rows.append({"data": "Unlimited", "days": int(days), "price_usd": price})
    return _dedup(rows), url, code


def parse_esimio(slug):
    url = f"https://esim.io/destinations/esim-{slug}"
    code, html = fetch(url)
    rows = []
    if code != 200:
        return rows, url, code
    for m in re.finditer(
            r'(\d+(?:\.\d+)?)\s*GB.{0,400}?(\d+)\s*Days.{0,400}?\$([0-9]+(?:\.[0-9]+)?)',
            html, re.S | re.I):
        gb, days, price = m.group(1), m.group(2), float(m.group(3))
        if price < 0.5:
            continue
        rows.append({"data": f"{gb} GB", "days": int(days), "price_usd": price})
    return _dedup(rows), url, code


def enum_pocketesim():
    _, html = fetch("https://www.pocketesim.com/en/esim")
    slugs = re.findall(r"/en/esim/([a-z0-9-]+)", html)
    return sorted(set(slugs))


def parse_pocketesim(slug):
    url = f"https://www.pocketesim.com/en/esim/{slug}"
    code, html = fetch(url)
    rows = []
    if code != 200:
        return rows, url, code
    for data, valid, price in re.findall(
            r'data-esimData="([^"]+)"[^>]*?data-esimValidity="([^"]+)"'
            r'[^>]*?data-esimUnitPrice="([0-9.]+)"', html):
        dm = re.search(r"(\d+)", valid)
        rows.append({"data": norm_data(data), "days": int(dm.group(1)) if dm else "",
                     "price_usd": float(price)})
    return _dedup(rows), url, code


def _dedup(rows):
    seen, out = set(), []
    for r in rows:
        k = (r["data"], r["days"], r["price_usd"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


# =========================================================================
#  BREEZE  (Shopify catalog — different shape, handled whole)
# =========================================================================
SKIP_BREEZE = re.compile(r"gift|world-cup|top-?up|voucher|bundle-of", re.I)


def collect_breeze(limit=None):
    """Return normalized rows straight from the Shopify catalog."""
    rows = []
    page = 1
    products = []
    import time
    while True:
        code, body = fetch(
            f"https://breezesim.com/products.json?limit=250&page={page}",
            retries=3, backoff=5)
        if code != 200 or not body:
            break
        time.sleep(0.5)  # be gentle with Shopify
        try:
            batch = json.loads(body).get("products", [])
        except Exception:
            break
        if not batch:
            break
        products.extend(batch)
        page += 1
        if page > 20:
            break
    today = datetime.date.today().isoformat()
    count = 0
    for p in products:
        handle = p.get("handle", "")
        title = p.get("title", "").strip()
        if SKIP_BREEZE.search(handle) or not title:
            continue
        # country slug from handle: esim-{country} or esimg_{cc}_v2
        m = re.match(r"esim-([a-z0-9-]+)$", handle)
        country = canon(m.group(1)) if m else title
        if limit and count >= limit:
            break
        count += 1
        for v in p.get("variants", []):
            label = (v.get("option1") or v.get("title") or "").strip()
            price = v.get("price")
            if price in (None, ""):
                continue
            data = norm_data(label)
            dm = re.search(r"(\d+)\s*day", label, re.I)
            days = int(dm.group(1)) if dm else ""
            rows.append({
                "date": today, "competitor": "Breeze", "country": country,
                "data": data, "days": days, "price_usd": float(price),
                "source_url": f"https://breezesim.com/products/{handle}",
            })
    return rows


# =========================================================================
#  DRIVER
# =========================================================================
def collect_ubigi(limit=None):
    """Ubigi embeds EVERY country's plans in ONE page as card attributes
    (data-iso / data-plantype / data-allowance / data-validity / data-price),
    so a single fetch gets them all."""
    url = ("https://cellulardata.ubigi.com/data-plans-and-coverage/"
           "ubigi-esim-data-plans/?destination=USA")
    code, html = fetch(url, retries=2, backoff=4)
    rows = []
    if code != 200:
        print(f"  [Ubigi] http={code} — no data")
        return rows
    today = datetime.date.today().isoformat()
    cards = re.findall(
        r'data-iso="([A-Z]{3})"[^>]*?data-plantype="COUNTRY"[^>]*?'
        r'data-allowance="([^"]*)"[^>]*?data-validity="([^"]*)"[^>]*?'
        r'data-price="([^"]*)"', html)
    seen = set()
    for iso, allow, valid, price in cards:
        country = ISO3.get(iso, iso)
        try:
            p = float(price)
        except ValueError:
            continue
        if p <= 0:
            continue
        data = f"{allow} GB" if str(allow).isdigit() else norm_data(str(allow))
        days = int(valid) if str(valid).isdigit() else ""
        k = (country, data, days, p)
        if k in seen:
            continue
        seen.add(k)
        rows.append({
            "date": today, "competitor": "Ubigi", "country": country,
            "data": data, "days": days, "price_usd": p,
            "source_url": "https://cellulardata.ubigi.com/data-plans-and-coverage/",
        })
    print(f"  [Ubigi] {len(rows)} packages "
          f"({len(set(r['country'] for r in rows))} countries)")
    return rows


PAGE_PROVIDERS = {
    "airalo": (enum_airalo, parse_airalo, "Airalo"),
    "holafly": (enum_holafly, parse_holafly, "Holafly"),
    "esimio": (enum_esimio, parse_esimio, "esim.io"),
    "pocketesim": (enum_pocketesim, parse_pocketesim, "PocketeSIM"),
}


def collect_page_provider(key, limit=None):
    enum, parser, label = PAGE_PROVIDERS[key]
    slugs = enum()
    if limit:
        slugs = slugs[:limit]
    print(f"  [{label}] enumerated {len(slugs)} countries; fetching...")
    today = datetime.date.today().isoformat()
    out = []

    def work(slug):
        rows, url, code = parser(slug)
        return slug, rows, url, code

    ok = fail = 0
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for slug, rows, url, code in ex.map(work, slugs):
            if code == 200 and rows:
                ok += 1
            else:
                fail += 1
            for r in rows:
                out.append({
                    "date": today, "competitor": label, "country": canon(slug),
                    "data": r["data"], "days": r["days"],
                    "price_usd": r["price_usd"], "source_url": url,
                })
    print(f"  [{label}] {ok} countries with data, {fail} empty/failed, "
          f"{len(out)} packages")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="max countries per provider (for testing)")
    ap.add_argument("--providers",
                    default="breeze,ubigi,airalo,holafly,esimio,pocketesim")
    args = ap.parse_args()
    provs = [p.strip() for p in args.providers.split(",") if p.strip()]

    today = datetime.date.today().isoformat()
    key2label = {k: v[2] for k, v in PAGE_PROVIDERS.items()}
    key2label.update({"breeze": "Breeze", "ubigi": "Ubigi"})

    # collect each requested provider separately
    fresh = {}
    for key in provs:
        label = key2label.get(key, key)
        if key in PAGE_PROVIDERS:
            fresh[label] = collect_page_provider(key, args.limit)
        elif key == "breeze":
            print("  [Breeze] fetching Shopify catalog...")
            br = collect_breeze(args.limit)
            print(f"  [Breeze] {len(br)} packages")
            fresh[label] = br
        elif key == "ubigi":
            print("  [Ubigi] fetching single-page catalog...")
            fresh[label] = collect_ubigi(args.limit)

    # RESILIENCE: a provider can be rate-limited/unreachable on any given run.
    # Save each success as the provider's "last good" snapshot; if a provider
    # returns nothing, carry its last-good data forward (keeping its original
    # collection date) so the daily file & dashboard are never blank for it.
    latest_dir = os.path.join(HERE, "data", "latest")
    os.makedirs(latest_dir, exist_ok=True)
    all_rows = []
    print("\n=== SUMMARY " + today + " ===")
    for label, rows in fresh.items():
        lp = os.path.join(latest_dir, label.replace("/", "_") + ".json")
        if rows:
            with open(lp, "w") as f:
                json.dump(rows, f)
            all_rows += rows
            print(f"  {label:11}: {len(rows)} packages (fresh)")
        elif os.path.exists(lp):
            carried = json.load(open(lp))
            all_rows += carried
            d = carried[0]["date"] if carried else "?"
            print(f"  {label:11}: FAILED this run — carried {len(carried)} "
                  f"from {d} (STALE)")
        else:
            print(f"  {label:11}: FAILED and no previous data")

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    base = os.path.join(HERE, "data", f"prices_{today}")
    with open(base + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "competitor", "country", "data",
                                          "days", "price_usd", "source_url"])
        w.writeheader()
        w.writerows(all_rows)
    with open(base + ".json", "w") as f:
        json.dump(all_rows, f, indent=1)
    print(f"  TOTAL      : {len(all_rows)} rows -> {base}.csv")


if __name__ == "__main__":
    main()
