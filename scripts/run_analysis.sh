#!/usr/bin/env bash
# Run a Nivesh analysis (normal | deep | extreme) against the live server and
# poll the v2 job API to completion. Local tool; talks to the remote API.
set -euo pipefail

HOST="http://192.168.1.122:8000"   # matches iOS NetworkManager.defaultURL
TICKER=""; MODE="normal"; USER_ID=""; EXCHANGE="NSE"; TIMEOUT=""

usage() {
  echo "Usage: $0 --ticker SYM --mode normal|deep|extreme --user ID [--exchange NSE] [--host URL] [--timeout SEC]"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ticker)   TICKER="$2"; shift 2;;
    --mode)     MODE="$2"; shift 2;;
    --user)     USER_ID="$2"; shift 2;;
    --exchange) EXCHANGE="$2"; shift 2;;
    --host)     HOST="$2"; shift 2;;
    --timeout)  TIMEOUT="$2"; shift 2;;
    -h|--help)  usage;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

[[ -z "$TICKER" || -z "$USER_ID" ]] && usage

case "$MODE" in
  normal)  SCAN_TYPE="standard"; DEEP="false";;
  deep)    SCAN_TYPE="standard"; DEEP="true";;
  extreme) SCAN_TYPE="extreme";  DEEP="true";;
  *) echo "Invalid --mode: $MODE"; usage;;
esac

# Safe upper-limit timeout: extreme 1200s (20 min), others 600s (10 min) (override with --timeout).
if [[ -z "$TIMEOUT" ]]; then
  [[ "$SCAN_TYPE" == "extreme" ]] && TIMEOUT=1200 || TIMEOUT=600
fi

jqget() { python3 -c "import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    print(''); raise SystemExit
print(d.get('$1','') if isinstance(d, dict) else '')"; }

echo "==> POST /analyze  ticker=$TICKER mode=$MODE scan_type=$SCAN_TYPE deep=$DEEP user=$USER_ID host=$HOST"
RESP=$(curl -s -X POST "$HOST/analyze" -H 'Content-Type: application/json' \
  -d "{\"ticker\":\"$TICKER\",\"exchange\":\"$EXCHANGE\",\"user_id\":$USER_ID,\"scan_type\":\"$SCAN_TYPE\",\"deep_scan\":$DEEP}")

ERR=$(echo "$RESP" | jqget error_code)
if [[ "$ERR" == "ALREADY_RUNNING" ]]; then
  echo "BLOCKED: $(echo "$RESP" | jqget error_detail)"; exit 1
fi
JOB_ID=$(echo "$RESP" | jqget job_id)
[[ -z "$JOB_ID" ]] && { echo "No job_id in response: $RESP"; exit 1; }
echo "==> job_id=$JOB_ID  (timeout ${TIMEOUT}s)"

START=$(date +%s)
JOB=""
while true; do
  NOW=$(date +%s); ELAPSED=$((NOW - START))
  if (( ELAPSED > TIMEOUT )); then
    echo "TIMEOUT after ${ELAPSED}s; last poll:"; echo "$JOB" | python3 -m json.tool 2>/dev/null || echo "$JOB"
    exit 124
  fi
  JOB=$(curl -s "$HOST/analyze/job/$JOB_ID?user_id=$USER_ID")
  STATUS=$(echo "$JOB" | jqget status)
  STAGE=$(echo "$JOB" | jqget stage)
  PROG=$(echo "$JOB" | jqget progress_pct)
  printf "    [%4ss] %-10s %-26s %s%%\n" "$ELAPSED" "${STATUS:-?}" "${STAGE:-—}" "${PROG:-0}"
  case "$STATUS" in
    SUCCEEDED)
      echo "==> DONE"
      echo "$JOB" | python3 -c "import sys,json
d=json.load(sys.stdin); r=d.get('result') or {}
print('signal      :', r.get('signal'))
print('confidence  :', r.get('confidence_pct'))
print('tier        :', r.get('analysis_tier','standard'))
print('targets     :', r.get('target_prices'))"
      exit 0;;
    FAILED|CANCELLED|TIMEOUT)
      echo "==> $STATUS: $(echo "$JOB" | jqget error)"; exit 1;;
  esac
  sleep 5
done
