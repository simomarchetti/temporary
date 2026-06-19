#!/bin/bash
# London Eye price monitor — run via launchd (see com.simomarchetti.londoneye-monitor.plist).
# Appends to data/london_eye_prices.csv with a UTC scrape timestamp each run.
cd /Users/simone.marchetti@feverup.com/PycharmProjects/eye-scraper || exit 1
echo "=== run $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> data/run.log
/usr/local/bin/python3 main.py --engine api --days 7 >> data/run.log 2>&1
