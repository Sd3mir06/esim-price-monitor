#!/usr/bin/env python3
"""
Aggregate every dated data/prices_YYYY-MM-DD.csv into docs/history.json,
which powers the price-trend charts in the dashboard.

Structure (compact, aligned to a shared date axis):
  {
    "dates": ["2026-08-10", "2026-08-17", ...],
    "countries": {
       "United States": {
          "Airalo|Unlimited|7":  [25.0, 24.5, ...],   # price per date, null if absent
          "Ubigi|10 GB|30":      [14.0, null, ...],
          ...
       }, ...
    }
  }
Key = "<competitor>|<data>|<days>"  (days "" = no fixed validity).
Cheapest price kept when a competitor lists several variants for the same key.
"""
import csv
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def main():
    files = sorted(glob.glob(os.path.join(DATA, "prices_*.csv")))
    dates = []
    # country -> key -> {date: price}
    hist = {}
    for f in files:
        m = re.search(r"prices_(\d{4}-\d{2}-\d{2})\.csv$", os.path.basename(f))
        if not m:
            continue
        date = m.group(1)
        dates.append(date)
        for r in csv.DictReader(open(f)):
            try:
                price = float(r["price_usd"])
            except (ValueError, KeyError):
                continue
            key = f'{r["competitor"]}|{r["data"]}|{r["days"]}'
            cd = hist.setdefault(r["country"], {}).setdefault(key, {})
            if date not in cd or price < cd[date]:
                cd[date] = price

    out = {"dates": dates, "countries": {}}
    for country, keys in hist.items():
        out["countries"][country] = {
            k: [series.get(d) for d in dates] for k, series in keys.items()
        }

    os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
    dst = os.path.join(HERE, "docs", "history.json")
    with open(dst, "w") as fp:
        json.dump(out, fp, separators=(",", ":"))
    n_series = sum(len(v) for v in out["countries"].values())
    print(f"History built: {dst}  ({len(dates)} snapshots, "
          f"{len(out['countries'])} countries, {n_series} package series)")


if __name__ == "__main__":
    main()
