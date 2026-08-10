#!/usr/bin/env python3
"""
Gate for the daily GitHub Actions run: decide whether to actually collect today.

Collect when ANY of:
  - triggered manually (workflow_dispatch)
  - it is Monday            -> the normal weekly snapshot
  - today is within LEAD days before an event's start, through its end
    -> "close monitoring" so we catch event-driven price moves

Otherwise skip (no collection that day). Writes `run=true|false` to GITHUB_OUTPUT.
"""
import datetime
import json
import os

LEAD = datetime.timedelta(days=7)   # start daily collection this many days before an event


def decide():
    today = datetime.date.today()
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        return True, "manual run"
    if today.weekday() == 0:         # Monday
        return True, "weekly Monday"
    try:
        events = json.load(open(os.path.join(os.path.dirname(__file__), "events.json")))
    except Exception:
        events = []
    for e in events:
        try:
            start = datetime.date.fromisoformat(e["start"])
            end = datetime.date.fromisoformat(e.get("end", e["start"]))
        except Exception:
            continue
        if start - LEAD <= today <= end:
            return True, f'near event: {e["name"]["en"]} ({e["country"]})'
    return False, "not Monday and no nearby event"


def main():
    run, reason = decide()
    print(f"gate: run={run}  ({reason})")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"run={'true' if run else 'false'}\n")


if __name__ == "__main__":
    main()
