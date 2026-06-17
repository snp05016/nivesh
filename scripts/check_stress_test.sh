#!/usr/bin/env bash
# Check status of the Stress Test engine on the Nivesh server
# Usage:
#   bash scripts/check_stress_test.sh <username> <password>
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <username> <password>" >&2
    exit 1
fi

echo "==> Checking Stress Test engine status on remote server (192.168.1.122)..."

REMOTE_BACKEND="/home/saumyapatel/Desktop/nivesh/backend"
REMOTE_PYTHON="/home/saumyapatel/Desktop/nivesh/venv/bin/python3"

printf -v USERNAME_Q "%q" "$1"
printf -v PASSWORD_Q "%q" "$2"

ssh saumyapatel@192.168.1.122 \
    "cd ${REMOTE_BACKEND} && ${REMOTE_PYTHON} scripts/check_stress_test_status.py ${USERNAME_Q} ${PASSWORD_Q}"
