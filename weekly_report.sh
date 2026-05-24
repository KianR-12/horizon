#!/usr/bin/env bash
# weekly_report.sh — Weekly ROI and CLV review
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

echo "════════════════════════════════════════════════════"
echo "  EDGE FINDER — WEEKLY REPORT  $(date +%Y-%m-%d)"
echo "════════════════════════════════════════════════════"

python3 edge_finder.py --weekly --bankroll 68

echo ""
echo "────────────────────────────────────────────────────"
if [ -f bet_tracker.csv ]; then
  echo "Recent bets (bet_tracker.csv):"
  tail -20 bet_tracker.csv
fi
echo "────────────────────────────────────────────────────"
echo "CLV tracking: check .edge_cache/calibration.json"
echo "Log files:    ls daily_log/"
