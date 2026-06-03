#!/bin/bash
echo "Stopping any process on port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 0.5
echo "Starting server..."
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload 
