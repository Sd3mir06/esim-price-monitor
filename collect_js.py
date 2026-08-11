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
            "https://www.nomadesim.com/en/country/united-states",
            "https://www.nomadesim.com/en/esim/united-states",
            "https://www.nomadesim.com/en/united-states-esim",
        ],
        "sitemap": "https://www.nomadesim.com/sitemap.xml",
    },
    "Saily": {
        "pages": [
            "https://saily.com/data-plans/",
            "https://saily.com/esim-usa/",
            "https://saily.com/esim-united-states/",
        ],
        "sitemap": "https://saily.com/sitemap.xml",
    },
    "Yesim": {
        "pages": [
            "https://yesim.app/country/united-states/",
            "https://yesim.app/esim/united-states/",
        ],
        "sitemap": "https://yesim.app/sitemap-index.xml",
    },
    "Simly": {
        "pages": [
            "https://www.simly.com/buy-plan",
            "https://www.simly.com/country/united-states",
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
            api = []
            page.on("response", lambda r: api.append((r.status, r.url)))
            for url in cfg["pages"]:
                item = {"requested": url}
                try:
                    await page.goto(url, wait_until="networkidle", timeout=35000)
                    await page.wait_for_timeout(2500)
                    txt = await page.inner_text("body")
                    item.update({"final_url": page.url, "title": await page.title(),
                                 "renders_prices": bool(PRICE_HINT.search(txt)),
                                 "text_sample": re.sub(r"\s+", " ", txt)[:1800]})
                except Exception as e:
                    item["error"] = str(e)[:200]
                rec["pages"].append(item)
            # interesting API/JSON endpoints seen while loading
            seen = []
            for st, u in api:
                if st == 200 and re.search(r"/api/|\.json|graphql|getnomad|glowingbud|saily|yesim", u):
                    if u not in seen:
                        seen.append(u)
            rec["api_calls"] = seen[:40]
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


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "discover"
    if mode == "discover":
        asyncio.run(discover())
    else:
        print("collect mode not implemented yet — run 'discover' first and build extractors")


if __name__ == "__main__":
    main()
