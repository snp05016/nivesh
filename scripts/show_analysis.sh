#!/usr/bin/env bash
# Display the latest AI analysis result for a stock
# Usage: bash scripts/show_analysis.sh RELIANCE
set -euo pipefail

TICKER="${1:?Usage: bash scripts/show_analysis.sh TICKER}"

ssh root@165.22.221.18 /root/nivesh/venv/bin/python3 /root/nivesh/backend/scripts/show_result.py "${TICKER}"
