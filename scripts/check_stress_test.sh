#!/usr/bin/env bash
# Check status of the Stress Test engine on the Nivesh server
# Usage:
#   bash scripts/check_stress_test.sh
set -euo pipefail

echo "==> Checking Stress Test engine status on remote server (192.168.1.122)..."

ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && ../venv/bin/python3 scripts/check_stress_test_status.py"
