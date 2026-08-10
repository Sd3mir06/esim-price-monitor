# eSIM Competitor Price Monitor

Collects competitor eSIM **package prices for every country** on a schedule, stores the
history, and publishes a bilingual (TR/EN) **competitor-intelligence dashboard**.

**🔗 Live dashboard:** https://sd3mir06.github.io/esim-price-monitor/

---

## What it does

- Scrapes 6 competitors' public pricing pages → one row per package (country · data · days · price).
- Runs in the cloud (GitHub Actions) — **weekly** baseline, plus **daily near big events**.
- Keeps every run as a dated snapshot → price **history** accumulates.
- Rebuilds a self-contained dashboard: market KPIs, per-competitor positioning, country
  drill-down, smart price table, price-trend charts, and an upcoming-events section with a
  live countdown.

## Competitors

| Collected (6) | How |
|---|---|
| Airalo, Holafly, esim.io, Breeze, PocketeSIM, Ubigi | public SSR pages / Shopify / catalog JSON |

Not collected (prices load via JavaScript → need a headless browser): **Nomad, Yesim, Simly**.

## How it runs

GitHub Actions triggers **daily** (`0 6 * * *` UTC), but `should_collect.py` gates it —
it actually collects only:
- on **Mondays** (weekly baseline), or
- within **7 days before → end** of an event in `events.json` (event-driven close monitoring).

Other days it's a cheap no-op. Results are committed back; GitHub Pages serves `docs/`.

## File map

```
collect.py           # THE COLLECTOR — scrapes all 6 competitors -> data/prices_YYYY-MM-DD.csv
build_dashboard.py   # builds docs/index.html (the dashboard) from the latest CSV
build_history.py     # aggregates all dated CSVs -> docs/history.json (powers trend charts)
should_collect.py    # gate: should today's run actually collect? (Monday / near-event)
events.json          # big global events (2026-27): name, country, dates, flag
HANDOFF.md           # detailed runbook (setup, per-competitor parsing, reliability, maintenance)
.github/workflows/collect.yml   # the daily cloud cron
data/
  prices_YYYY-MM-DD.csv/json    # dated snapshots (history — never deleted)
  latest/<Competitor>.json      # each competitor's last-good data (carry-forward)
docs/
  index.html                    # published dashboard  ← GitHub Pages serves this
  history.json                  # price history for the trend charts
```

**No dependencies:** all scripts use only the Python standard library — no `pip install`.

## Run locally

```bash
python3 collect.py            # all competitors, all countries (~2-10 min)
python3 build_dashboard.py    # -> docs/index.html
python3 build_history.py      # -> docs/history.json
```

Then open `docs/index.html`. (Price-trend charts fetch `history.json`, so they load on the
live Pages URL or via a local server — not via `file://`.)

## Data & reliability

- **CSV columns:** `date, competitor, country, data, days, price_usd, source_url`
- **Carry-forward:** if a competitor is rate-limited/unreachable on a run, its last-good data
  is kept (dashboard shows a `⚠ stale` note) so nothing goes blank.
- **Airalo currency guard:** Airalo prices are USD only when collected from a US IP (GitHub
  runners are US) — a guard drops non-USD rows to avoid corrupt data.

Full details, per-competitor parsing, and maintenance steps are in **[HANDOFF.md](HANDOFF.md)**.
