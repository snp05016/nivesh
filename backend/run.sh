#!/bin/bash
# LOCAL DEVELOPMENT ONLY - production runs under systemd (nivesh.service):
#   sudo systemctl restart nivesh && journalctl -u nivesh -f
# Never run this on the server: it kills whatever holds :8000 and starts an unsupervised --reload process.
echo "Stopping any process on port 8000..."
lsof -ti:8000 | xargs kill 2>/dev/null || true
sleep 0.5
echo "Starting server..."
source venv/bin/activate
uvicorn main:app --host "${HOST:-127.0.0.1}" --port 8000 --reload
