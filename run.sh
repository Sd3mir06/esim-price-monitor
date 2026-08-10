#!/bin/bash
# Daily eSIM competitor price collection. Invoked by cron.
# Logs each run to logs/ and keeps one dated CSV/JSON per day in data/.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
TS="$(date '+%Y-%m-%d_%H%M%S')"
echo "=== run $TS ===" >> "logs/cron.log"

# The Mac may have just woken for this cron job and its network may not be
# ready yet — wait until a host is reachable (up to ~5 min) before collecting.
for i in $(seq 1 30); do
  if curl -s -m 5 -o /dev/null "https://www.airalo.com/robots.txt"; then
    echo "  network ready after $((i-1)) retries" >> "logs/cron.log"
    break
  fi
  sleep 10
done

/usr/bin/python3 collect.py >> "logs/cron.log" 2>&1
/usr/bin/python3 build_dashboard.py >> "logs/cron.log" 2>&1
echo "=== done $TS ===" >> "logs/cron.log"
