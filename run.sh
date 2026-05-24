#!/usr/bin/env bash
# run.sh — Daily edge_finder workflow
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source environment variables
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Create log directory
mkdir -p daily_log

DATE=$(date +%Y-%m-%d)
LOG="daily_log/${DATE}.txt"

echo "Running edge_finder — $(date)" | tee "$LOG"
echo "────────────────────────────────────────────────────────" | tee -a "$LOG"

python3 edge_finder.py --once --bankroll 68 2>&1 | tee -a "$LOG"

echo ""
echo "────────────────────────────────────────────────────────"
echo "Output saved to: $LOG"
echo "To review bets: grep -E 'STRONG BET|^  BET ' $LOG"
