#!/bin/bash
# 24/7 Persistent Autonomous Trader Daemon
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

echo "Starting 24/7 Autonomous Polymarket Trader Daemon..."

# Keep running in a persistent loop with auto-restart on crash
while true; do
    echo "[$(date)] Launching FastAPI Engine & Opportunity Hunter..."
    uv run uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 >> "$DIR/autotrader.log" 2>&1 || true
    echo "[$(date)] Engine crashed or stopped. Restarting in 5 seconds..."
    sleep 5
done
