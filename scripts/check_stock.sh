#!/usr/bin/env bash
# Check status of all running/recent analysis jobs on the Nivesh server
# Usage:
#   bash scripts/check_stock.sh              # show only RUNNING jobs
#   bash scripts/check_stock.sh --all        # show last 20 jobs
#   bash scripts/check_stock.sh --stuck      # show RUNNING jobs older than 15 min
#   bash scripts/check_stock.sh RELIANCE     # show jobs for a specific ticker
set -euo pipefail

MODE="${1:-running}"

ssh saumyapatel@192.168.1.122 /home/saumyapatel/Desktop/nivesh/venv/bin/python3 /home/saumyapatel/Desktop/nivesh/backend/scripts/check_jobs.py "${MODE}"
