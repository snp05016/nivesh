#!/bin/bash
# Nivesh API endpoint health check
# Usage: BASE_URL="https://api.nivesh.qzz.io" bash health_check.sh
#    or: BASE_URL="http://localhost:8000" bash health_check.sh
# Exits non-zero when any check fails. Portable to macOS (BSD) and Linux (GNU).
set -uo pipefail

BASE_URL="${BASE_URL:-https://api.nivesh.qzz.io}"
TICKER="${TICKER:-RELIANCE}"
PASS=0
FAIL=0

# check LABEL EXPECTED_CODE URL [extra curl args...]
check() {
    local label="$1" code="$2" url="$3"
    shift 3
    printf "%-55s " "$label"
    r=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$@" "$url" || true)
    if [ "$r" = "$code" ]; then
        echo "✅ $r"; PASS=$((PASS+1))
    else
        echo "❌ $r (expected $code)"; FAIL=$((FAIL+1))
    fi
}

# check_body LABEL EXPECTED_CODE URL  (also requires a non-empty body)
check_body() {
    local label="$1" code="$2" url="$3"
    printf "%-55s " "$label"
    r=$(curl -s -w "\n%{http_code}" --max-time 10 "$url" || true)
    http=$(printf '%s\n' "$r" | tail -n 1)
    body=$(printf '%s\n' "$r" | sed '$d')
    if [ "$http" = "$code" ] && [ -n "$body" ] && [ "$body" != "null" ] && [ "$body" != "[]" ] && [ "$body" != "{}" ]; then
        echo "✅ $http ($(printf '%s' "$body" | wc -c | tr -d ' ')b)"
        PASS=$((PASS+1))
    else
        echo "❌ $http body=$(printf '%s' "$body" | head -c 60)"
        FAIL=$((FAIL+1))
    fi
}

echo "═══ Nivesh API Health Check ═══"
echo "BASE: $BASE_URL | TICKER: $TICKER"
echo ""

echo "── Health ──"
check      "GET /ping (liveness)"                            200 "$BASE_URL/ping"
# /health is still the always-200 iOS alias (routers/health.py); it becomes a real
# DB readiness check once REL-18 lands. /healthz returns 503 when a critical component is down.
check      "GET /health"                                     200 "$BASE_URL/health"
check      "GET /healthz (readiness)"                        200 "$BASE_URL/healthz"

echo "── Market (public, no auth) ──"
check_body "GET /quick-info?ticker="                         200 "$BASE_URL/quick-info?ticker=$TICKER&exchange=NSE"
check_body "GET /nifty-history?days=30"                      200 "$BASE_URL/nifty-history?days=30"
check_body "GET /search?q=REL"                               200 "$BASE_URL/search?q=REL&limit=5"
check_body "GET /market-indices"                             200 "$BASE_URL/market-indices"

echo "── Stock Profile (public) ──"
check_body "GET /api/v1/stock-profile?ticker="               200 "$BASE_URL/api/v1/stock-profile?ticker=$TICKER&exchange=NSE"
check_body "GET /api/v1/market/stock-history?ticker="        200 "$BASE_URL/api/v1/market/stock-history?ticker=$TICKER&exchange=NSE&period=1mo"
check_body "GET /quarterly-financials?ticker="               200 "$BASE_URL/quarterly-financials?ticker=$TICKER&exchange=NSE"
check      "GET /fundamentals/piotroski/{ticker}"            200 "$BASE_URL/fundamentals/piotroski/$TICKER"
check      "GET /analyst-ratings?ticker="                    200 "$BASE_URL/analyst-ratings?ticker=$TICKER&exchange=NSE"

echo "── Screener ──"
check_body "GET /screener?preset=quality_value"              200 "$BASE_URL/screener?preset=quality_value"
check_body "GET /screener?preset=52w_low_bullish"            200 "$BASE_URL/screener?preset=52w_low_bullish"

echo "── Sector / Earnings ──"
check_body "GET /sector-performance"                         200 "$BASE_URL/sector-performance"
check_body "GET /api/v1/earnings/feed?sort=upcoming"         200 "$BASE_URL/api/v1/earnings/feed?sort=upcoming"

echo "── Option Chain ──"
check      "GET /api/v1/options/chain/NIFTY"                 200 "$BASE_URL/api/v1/options/chain/NIFTY"

echo "── Auth (public, should 422 on missing fields) ──"
check      "POST /login (missing creds → 422)"               422 "$BASE_URL/login" -X POST -H "Content-Type: application/json" -d '{}'
check      "POST /register (missing creds → 422)"            422 "$BASE_URL/register" -X POST -H "Content-Type: application/json" -d '{}'

echo ""
echo "═══ Results: $PASS passed, $FAIL failed ═══"
if [ "$FAIL" -eq 0 ]; then
    echo "All endpoints healthy ✅"
else
    echo "Some endpoints failed ❌"
fi
[ "$FAIL" -eq 0 ]
