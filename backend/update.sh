#!/bin/bash
# Nivesh backend — push code updates to running droplet.
# Run as root on the droplet: bash update.sh
set -e

APP_DIR=/home/nivesh/stocks
SERVICE=nivesh

echo "=== Stopping $SERVICE ==="
systemctl stop "$SERVICE"

echo "=== Copying Python files ==="
# Copy all .py files and static assets from current directory
# Assumes you've already rsync'd or scp'd the new code to this directory.
# If running this script from /Desktop/stocks on dev machine mapped to droplet:
if [ -d "/Desktop/stocks" ]; then
    cp /Desktop/stocks/*.py "$APP_DIR/"
    cp /Desktop/stocks/requirements.txt "$APP_DIR/"
    if [ -f "/Desktop/stocks/prompts.py" ]; then
        cp /Desktop/stocks/prompts.py "$APP_DIR/"
    fi
fi

echo "=== Updating dependencies ==="
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q

echo "=== Fixing permissions ==="
chown -R nivesh:nivesh "$APP_DIR"

echo "=== Starting $SERVICE ==="
systemctl start "$SERVICE"
sleep 2

echo "=== Status ==="
systemctl status "$SERVICE" --no-pager

echo ""
echo "=== Liveness check ==="
curl -s http://localhost/ping && echo "" || echo "WARNING: /ping did not respond"

echo ""
echo "Update complete. Tail logs: journalctl -u $SERVICE -f"
