#!/bin/bash
# Nivesh Cache Cleanup — run nightly to expire stale cache files and rotate logs.
# macOS: add to crontab: 30 21 * * * /path/to/backend/scripts/cache_cleanup.sh
# Linux: use systemd timer at 21:30 UTC (03:00 IST)

CACHE_ROOT="${NIVESH_CACHE_DIR:-${HOME}/Library/Caches/nivesh}"
LOG_DIR="${HOME}/Library/Logs/nivesh"
LOG_FILE="${LOG_DIR}/cache_cleanup.log"

mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting cache cleanup" >> "$LOG_FILE"

find "${CACHE_ROOT}/yfinance"       -name "*.json.gz" -mmin +360  -delete 2>/dev/null
find "${CACHE_ROOT}/options"        -name "*.json.gz" -mmin +60   -delete 2>/dev/null
find "${CACHE_ROOT}/news_processed" -name "*.json.gz" -mmin +720  -delete 2>/dev/null
find "${CACHE_ROOT}/bhavcopy"       -name "*.json.gz" -mtime +7   -delete 2>/dev/null

BACKEND_DIR="$(dirname "$(dirname "$0")")"
TOKEN_LOG="${BACKEND_DIR}/token_log.jsonl"
if [ -f "$TOKEN_LOG" ]; then
    SIZE=$(stat -f%z "$TOKEN_LOG" 2>/dev/null || stat -c%s "$TOKEN_LOG" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt 5242880 ]; then
        ARCHIVE="${LOG_DIR}/token_log_$(date +%Y%m).jsonl.gz"
        gzip -c "$TOKEN_LOG" > "$ARCHIVE"
        > "$TOKEN_LOG"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Token log archived to $ARCHIVE" >> "$LOG_FILE"
    fi
fi

CACHE_SIZE=$(du -sh "$CACHE_ROOT" 2>/dev/null | cut -f1)
DISK_FREE=$(df -h / | awk 'NR==2 {print $4}')
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done. Cache: ${CACHE_SIZE:-unknown}, Disk free: ${DISK_FREE:-unknown}" >> "$LOG_FILE"
