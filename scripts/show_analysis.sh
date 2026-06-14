#!/usr/bin/env bash
# Display the latest AI analysis result for a stock
# Usage: bash scripts/show_analysis.sh RELIANCE
set -euo pipefail

TICKER="${1:?Usage: bash scripts/show_analysis.sh TICKER}"

ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && PYTHONPATH=.:../tradingagents-core ../venv/bin/python3 scripts/show_result.py \"${TICKER}\""
