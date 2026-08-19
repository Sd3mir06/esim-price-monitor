#!/usr/bin/env python3
"""
Headless-browser collector for the JavaScript-based competitors that the plain
stdlib collector (collect.py) cannot read: Nomad, Saily, Yesim, Simly.

Runs in GitHub Actions (which CAN reach these hosts and install Chromium).
Uses Playwright. Two modes:

  python3 collect_js.py discover   -> load candidate pages, dump what renders +
                                      which JSON/API endpoints fire, to
                                      data/js_discovery.json  (used to BUILD the
                                      real extractors — run this first)
  python3 collect_js.py collect    -> (added once discovery reveals structure)
                                      produce data/prices_js_YYYY-MM-DD.csv

Local runs here time out on these hosts, so discovery is developed via CI.
"""
import asyncio
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Candidate entry points per competitor — homepage, a likely country/plans page,
# and the sitemap (for country enumeration). Discovery reports which ones render
# prices and what API calls fire, so we can pick the real strategy.
SITES = {
    "Nomad": {
        "pages": [
            "https://www.nomadesim.com/en/united-states-esim",
            "https://www.nomadesim.com/en/japan-esim",
        ],
        "sitemap": "https://www.nomadesim.com/sitemap.xml",
    },
    "Saily": {
        "pages": [
            "https://saily.com/esim-united-states/",
            "https://saily.com/esim-japan/",
        ],
        "sitemap": "https://saily.com/sitemap.xml",
    },
    "Yesim": {
        "pages": [
            "https://yesim.app/country/united-states/",
            "https://yesim.app/country/japan/",
        ],
        "sitemap": "https://yesim.app/sitemap-en.xml",
    },
    "Simly": {
        "pages": [
            "https://www.simly.com/buy-plan/choose-destination",
            "https://www.simly.com/buy-plan/plans?country=US",
        ],
        "sitemap": "https://www.simly.com/sitemap.xml",
    },
}

PRICE_HINT = re.compile(r"(\$|€|£)\s?\d|\d+\s?GB|\d+\s?day", re.I)


async def discover():
    from playwright.async_api import async_playwright
    out = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"))
        for name, cfg in SITES.items():
            rec = {"pages": [], "api_calls": [], "sitemap": None}
            page = await ctx.new_page()
            responses = []
            page.on("response", lambda r: responses.append(r))
            for url in cfg["pages"]:
                item = {"requested": url}
                try:
                    await page.goto(url, wait_until="networkidle", timeout=35000)
                    await page.wait_for_timeout(3000)
                    txt = await page.inner_text("body")
                    item.update({"final_url": page.url, "title": await page.title(),
                                 "renders_prices": bool(PRICE_HINT.search(txt)),
                                 "text_sample": re.sub(r"\s+", " ", txt)[:4000]})
                except Exception as e:
                    item["error"] = str(e)[:200]
                rec["pages"].append(item)
            # capture the actual JSON BODIES of pricing/product APIs
            bodies, seen = [], []
            for r in responses:
                u = r.url
                if u in seen:
                    continue
                seen.append(u)
                if re.search(r"getnomad|glowingbud", u) and re.search(
                        r"product|plan|countr|catalog|price", u, re.I):
                    try:
                        bodies.append({"url": u, "status": r.status,
                                       "body": (await r.text())[:3500]})
                    except Exception as e:
                        bodies.append({"url": u, "err": str(e)[:80]})
            rec["api_calls"] = [u for u in seen if re.search(r"getnomad|glowingbud|/api/", u)][:30]
            rec["api_bodies"] = bodies[:8]
            # sitemap peek (country enumeration source)
            try:
                await page.goto(cfg["sitemap"], wait_until="domcontentloaded", timeout=25000)
                sm = await page.content()
                locs = re.findall(r"<loc>([^<]+)</loc>", sm)
                rec["sitemap"] = {"url": cfg["sitemap"], "count": len(locs), "sample": locs[:15]}
            except Exception as e:
                rec["sitemap"] = {"url": cfg["sitemap"], "error": str(e)[:150]}
            out[name] = rec
            await page.close()
        await browser.close()
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    dst = os.path.join(HERE, "data", "js_discovery.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1)
    for name, rec in out.items():
        rp = [pg for pg in rec["pages"] if pg.get("renders_prices")]
        print(f"{name}: {len(rp)}/{len(rec['pages'])} pages render prices | "
              f"{len(rec['api_calls'])} api calls | sitemap {rec['sitemap'].get('count','?')} urls")
    print(f"-> {dst}")


CID = "67b6bcade70516276739823d"   # Simly's public customerId (embedded in their frontend)
PROBE_URLS = [
    # Simly (glowingbud) — country list + plans (global + per-country param guesses)
    f"https://api-eu.glowingbud.com/countries?customerId={CID}&currency=USD",
    f"https://api-eu.glowingbud.com/plans?groupSelected=Global&isCountry=false&currency=USD&customerId={CID}",
    f"https://api-eu.glowingbud.com/plans?groupSelected=United States&isCountry=true&currency=USD&customerId={CID}",
    f"https://api-eu.glowingbud.com/plans?groupSelected=US&isCountry=true&currency=USD&customerId={CID}",
    f"https://api-eu.glowingbud.com/plans?country=US&currency=USD&customerId={CID}",
    # Nomad product API — country list + product/plans endpoint guesses
    "https://api.getnomad.app/product/api/v3/product/get_countries",
    "https://api.getnomad.app/product/api/v3/product/get_products?country=US",
    "https://api.getnomad.app/product/api/v3/product/get_products?countryCode=US",
    "https://api.getnomad.app/product/api/v3/product/products?country=US",
    "https://api.getnomad.app/product/api/v3/product/get_country_products?country=US",
]


async def probe():
    from playwright.async_api import async_playwright
    out = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        for u in PROBE_URLS:
            try:
                r = await ctx.request.get(u, timeout=25000)
                body = await r.text()
                out.append({"url": u, "status": r.status, "len": len(body),
                            "body": body[:2200]})
            except Exception as e:
                out.append({"url": u, "err": str(e)[:150]})
        await browser.close()
    json.dump(out, open(os.path.join(HERE, "data", "js_probe.json"), "w"), indent=1)
    for o in out:
        print(f"[{o.get('status','ERR')}] len={o.get('len','?')} {o['url'][:95]}")


# url slugs for the render-based sites (major eSIM destinations; extend freely).
# Playwright rendering is slow + Saily is behind Cloudflare, so we cover the top
# ~60 markets rather than every country.
COUNTRIES = [
    "united-states", "canada", "mexico", "brazil", "argentina", "chile", "colombia", "peru",
    "united-kingdom", "france", "germany", "spain", "italy", "portugal", "netherlands",
    "belgium", "switzerland", "austria", "ireland", "greece", "poland", "czech-republic",
    "sweden", "norway", "denmark", "iceland", "croatia", "serbia", "turkey", "russia",
    "japan", "south-korea", "china", "hong-kong", "taiwan", "thailand", "vietnam",
    "singapore", "malaysia", "indonesia", "philippines", "india", "sri-lanka", "nepal",
    "cambodia", "laos", "united-arab-emirates", "saudi-arabia", "qatar", "israel", "jordan",
    "egypt", "morocco", "south-africa", "kenya", "tanzania", "australia", "new-zealand", "fiji",
]


def norm_data(s):
    s = s.strip()
    if re.search(r"unlim", s, re.I):
        return "Unlimited"
    m = re.search(r"([\d.]+)\s*(GB|MB|TB)", s, re.I)
    return f"{m.group(1)} {m.group(2).upper()}" if m else s


def slug_to_name(slug):
    fix = {"united-states": "United States", "united-kingdom": "United Kingdom"}
    return fix.get(slug, slug.replace("-", " ").title())


async def collect():
    from playwright.async_api import async_playwright
    today = datetime.date.today().isoformat()
    rows = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"))
        page = await ctx.new_page()

        async def grab(url, retries=1):
            """Load a page; retry once if it fails or renders no price (Saily's
            Cloudflare can challenge under load)."""
            for attempt in range(retries + 1):
                try:
                    await page.goto(url, wait_until="networkidle", timeout=35000)
                    await page.wait_for_timeout(2200)
                    txt = await page.inner_text("body")
                    if PRICE_HINT.search(txt):
                        return txt
                except Exception:
                    pass
                await page.wait_for_timeout(2500)   # back off then retry
            return ""

        for slug in COUNTRIES:
            country = slug_to_name(slug)
            # NOMAD: "1 GB For 7 DAYS USD5" — price may be before OR after "USD"
            txt = await grab(f"https://www.nomadesim.com/en/{slug}-esim")
            n = 0
            for m in re.finditer(
                    r"([\d.]+\s*GB|Unlimited)\s+For\s+(\d+)\s*DAYS?\s+(?:USD\s*)?([\d.]+)",
                    txt, re.I):
                rows.append({"date": today, "competitor": "Nomad", "country": country,
                             "data": norm_data(m.group(1)), "days": int(m.group(2)),
                             "price_usd": float(m.group(3)),
                             "source_url": f"https://www.nomadesim.com/en/{slug}-esim"})
                n += 1
            # SAILY: "1 GB 7 days US$3.99" (GB) + "Unlimited 15 days US$45.99"
            txt = await grab(f"https://saily.com/esim-{slug}/")
            s = 0
            for m in re.finditer(r"([\d.]+)\s*GB\s+(\d+)\s*days?\s+US\$\s*([\d.]+)", txt, re.I):
                rows.append({"date": today, "competitor": "Saily", "country": country,
                             "data": f"{m.group(1)} GB", "days": int(m.group(2)),
                             "price_usd": float(m.group(3)),
                             "source_url": f"https://saily.com/esim-{slug}/"})
                s += 1
            for m in re.finditer(r"Unlimited\s+(\d+)\s*days?\s+US\$\s*([\d.]+)", txt, re.I):
                rows.append({"date": today, "competitor": "Saily", "country": country,
                             "data": "Unlimited", "days": int(m.group(1)),
                             "price_usd": float(m.group(2)),
                             "source_url": f"https://saily.com/esim-{slug}/"})
                s += 1
            print(f"  {country:16} Nomad={n} Saily={s}")
        await browser.close()

    # dedup
    seen, uniq = set(), []
    for r in rows:
        k = (r["competitor"], r["country"], r["data"], r["days"], r["price_usd"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    _merge_into_dataset(uniq, today)
    print(f"\nJS collected {len(uniq)} rows "
          f"(Nomad {sum(1 for r in uniq if r['competitor']=='Nomad')}, "
          f"Saily {sum(1 for r in uniq if r['competitor']=='Saily')})")


def _merge_into_dataset(js_rows, today):
    """Merge JS-collected competitors into today's prices CSV + latest/, then
    rebuild the dashboard and history."""
    import csv
    import glob
    fields = ["date", "competitor", "country", "data", "days", "price_usd", "source_url"]
    labels = sorted(set(r["competitor"] for r in js_rows))
    base = os.path.join(HERE, "data", f"prices_{today}.csv")
    existing = []
    if os.path.exists(base):
        existing = [r for r in csv.DictReader(open(base)) if r["competitor"] not in labels]
    else:  # no run today yet — start from most recent snapshot
        prev = sorted(glob.glob(os.path.join(HERE, "data", "prices_*.csv")))
        if prev:
            for r in csv.DictReader(open(prev[-1])):
                if r["competitor"] not in labels:
                    r["date"] = today
                    existing.append(r)
    merged = existing + [{k: str(r[k]) for k in fields} for r in js_rows]
    with open(base, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(merged)
    with open(base.replace(".csv", ".json"), "w") as f:
        json.dump(merged, f)
    os.makedirs(os.path.join(HERE, "data", "latest"), exist_ok=True)
    for lbl in labels:
        with open(os.path.join(HERE, "data", "latest", lbl + ".json"), "w") as f:
            json.dump([r for r in js_rows if r["competitor"] == lbl], f)
    import subprocess  # trusted fixed args (no user input) — rebuild outputs
    subprocess.run(["python3", "build_dashboard.py"], cwd=HERE, check=False)
    subprocess.run(["python3", "build_history.py"], cwd=HERE, check=False)


AUDIT_PAGES = {
    "Airalo": "https://www.airalo.com/united-states-esim",
    "Ubigi": "https://cellulardata.ubigi.com/data-plans-and-coverage/ubigi-esim-data-plans/?destination=USA",
    "Holafly": "https://esim.holafly.com/esim-usa/",
    "esim.io": "https://esim.io/destinations/esim-united-states-of-america",
    "PocketeSIM": "https://www.pocketesim.com/en/esim/united-states",
    "Nomad": "https://www.nomadesim.com/en/united-states-esim",
    "Saily": "https://saily.com/esim-united-states/",
}
DISCOUNT_KW = ["compare_at", "original", "discount", "old-price", "oldprice",
               "line-through", "strike", "was ", "regular", "sale", "% off", "promo",
               "crossed", "net_price", "netPrice", "originalPrice", "salePrice"]


async def priceaudit():
    """Dump each competitor's US-page price structure to spot discounted vs list
    prices (visible price vs what our parser reads, plus struck-through originals)."""
    from playwright.async_api import async_playwright
    out = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"))
        page = await ctx.new_page()
        for name, url in AUDIT_PAGES.items():
            rec = {"url": url}
            try:
                await page.goto(url, wait_until="networkidle", timeout=40000)
                await page.wait_for_timeout(2500)
                html = await page.content()
                rec["discount_kw"] = {k: html.lower().count(k.lower())
                                      for k in DISCOUNT_KW if html.lower().count(k.lower())}
                # raw HTML around the first few price markers
                snips = []
                for m in list(re.finditer(r'US?\$\s?\d|USD\s?\d|data-price="', html))[:4]:
                    i = m.start()
                    snips.append(re.sub(r"\s+", " ", html[max(0, i-260):i+180]))
                rec["snippets"] = snips
            except Exception as e:
                rec["error"] = str(e)[:150]
            out[name] = rec
            print(f"  {name}: discount-kw={list(rec.get('discount_kw',{}).keys())}")
        await browser.close()
    json.dump(out, open(os.path.join(HERE, "data", "price_audit.json"), "w"), indent=1)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "discover"
    if mode == "discover":
        asyncio.run(discover())
    elif mode == "probe":
        asyncio.run(probe())
    elif mode == "collect":
        asyncio.run(collect())
    elif mode == "priceaudit":
        asyncio.run(priceaudit())
    else:
        print("unknown mode")


if __name__ == "__main__":
    main()
