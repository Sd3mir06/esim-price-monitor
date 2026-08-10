# eSIM Competitor Price Monitor

Collects competitor eSIM **package prices for every country, every day**, and saves
them as a spreadsheet you can open in Excel / Google Sheets.

## What it collects

| Competitor | Countries | Method | Status |
|---|---|---|---|
| **Airalo** | ~216 | Public country pages (`/{country}-esim`, Nuxt data) | ✅ working |
| **Holafly** | ~413 (incl. cities) | Public country pages (`/esim-{country}`) | ✅ working |
| **esim.io** (“Esimio”) | ~188 | Public country pages (`/destinations/esim-{country}`) | ✅ working |
| **Breeze** | ~200 | Shopify catalog (`/products.json`) | ✅ working |
| **PocketeSIM** | ~197 | Public country pages (`/en/esim/{country}`) | ✅ working |
| **Ubigi** | ~167 | Single plans page, all countries (card attrs) | ✅ working |
| **Nomad** | — | JavaScript app — needs a headless browser | ⚠️ not included |
| **Yesim** | — | Country pages load prices via JavaScript | ⚠️ not included |
| **Simly** | — | App/SPA, prices from third-party API | ⚠️ not included |

Countries are re-discovered from each site on every run, so new destinations the
competitors add get picked up automatically. No login or paid API needed — all data
comes from public pages.

## Output

Each run writes, in `data/`:
- `prices_YYYY-MM-DD.csv` — one row per package: `date, competitor, country, data, days, price_usd, source_url`
- `prices_YYYY-MM-DD.json` — same data as JSON

One file per day, so you build a price history over time.

## Run it manually

```bash
cd "/Users/sukrudemir/general things/esim-price-monitor"
python3 collect.py                 # all countries, all 4 providers (~10 min)
python3 collect.py --limit 10      # quick test: 10 countries each
python3 collect.py --providers airalo,holafly   # subset of providers
```

## Daily automation (already installed)

A cron job runs it every day at **08:00**:

```
0 8 * * * "/Users/sukrudemir/general things/esim-price-monitor/run.sh"
```

- View/edit schedule: `crontab -e`   ·   list: `crontab -l`
- Logs: `logs/cron.log`
- **Note:** cron only runs while your Mac is **awake**. If it's often asleep at 8am,
  change the time, or ask me to switch it to a `launchd` job (runs at next wake) or a
  cloud schedule.
- macOS may need **Full Disk Access** for `cron` the first time (System Settings →
  Privacy & Security → Full Disk Access → add `/usr/sbin/cron`).

## Notes on the data

- **Airalo & Holafly** sell mostly *Unlimited* plans priced by duration → directly comparable.
- **esim.io & Breeze** sell mostly *fixed-GB* plans → compare on $/GB.
- Breeze GB plans don't publish a validity in the catalog, so `days` is blank for those.
- All prices are the public USD retail price shown to a US visitor.

## Adding Nomad later

Nomad (`nomadesim.com`) renders prices with JavaScript, so `curl` can't see them.
Options: (a) Playwright headless browser to load each country page, or (b) reverse-engineer
their internal product API. Ask me to build either.
