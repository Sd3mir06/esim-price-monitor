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


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "discover"
    if mode == "discover":
        asyncio.run(discover())
    elif mode == "probe":
        asyncio.run(probe())
    else:
        print("collect mode not implemented yet — run 'discover'/'probe' first")


if __name__ == "__main__":
    main()
