#!/bin/bash
# Nivesh API endpoint health check
# Usage: BASE_URL="https://api.nivesh.app" bash health_check.sh
#    or: BASE_URL="http://localhost:8000" bash health_check.sh
set -e

BASE_URL="${BASE_URL:-https://api.nivesh.app}"
TICKER="${TICKER:-RELIANCE}"
PASS=0
FAIL=0

check() {
    local label="$1" url="$2" code="$3"
    printf "%-55s " "$label"
    r=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url")
    if [ "$r" = "$code" ]; then
        echo "✅ $r"; PASS=$((PASS+1))
    else
        echo "❌ $r (expected $code)"; FAIL=$((FAIL+1))
    fi
}

check_body() {
    local label="$1" url="$2" code="$3"
    printf "%-55s " "$label"
    r=$(curl -s -w "\n%{http_code}" --max-time 10 "$url")
    http=$(echo "$r" | tail -1)
    body=$(echo "$r" | head -n -1)
    if [ "$http" = "$code" ] && [ -n "$body" ] && [ "$body" != "null" ] && [ "$body" != "[]" ] && [ "$body" != "{}" ]; then
        echo "✅ $http ($(echo "$body" | wc -c | tr -d ' ')b)"
        PASS=$((PASS+1))
    else
        echo "❌ $http body=$(echo "$body" | head -c 60)"
        FAIL=$((FAIL+1))
    fi
}

echo "═══ Nivesh API Health Check ═══"
echo "BASE: $BASE_URL | TICKER: $TICKER"
echo ""

echo "── Health ──"
check      "GET /health"                                     "$BASE_URL/health"                                   200

echo "── Market (public, no auth) ──"
check_body "GET /quick-info?ticker="                         "$BASE_URL/quick-info?ticker=$TICKER&exchange=NSE"   200
check_body "GET /nifty-history?days=30"                      "$BASE_URL/nifty-history?days=30"                    200
check_body "GET /search?q=REL"                               "$BASE_URL/search?q=REL&limit=5"                     200
check_body "GET /market-indices"                             "$BASE_URL/market-indices"                           200

echo "── Stock Profile (public) ──"
check_body "GET /api/v1/stock-profile?ticker="               "$BASE_URL/api/v1/stock-profile?ticker=$TICKER&exchange=NSE" 200
check_body "GET /api/v1/market/stock-history?ticker="        "$BASE_URL/api/v1/market/stock-history?ticker=$TICKER&exchange=NSE&period=1mo" 200
check_body "GET /quarterly-financials?ticker="               "$BASE_URL/quarterly-financials?ticker=$TICKER&exchange=NSE" 200
check      "GET /fundamentals/piotroski/{ticker}"            "$BASE_URL/fundamentals/piotroski/$TICKER"          200
check      "GET /analyst-ratings?ticker="                    "$BASE_URL/analyst-ratings?ticker=$TICKER&exchange=NSE" 200

echo "── Screener ──"
check_body "GET /screener?preset=quality_value"              "$BASE_URL/screener?preset=quality_value"            200
check_body "GET /screener?preset=52w_low_bullish"            "$BASE_URL/screener?preset=52w_low_bullish"          200

echo "── Sector / Earnings ──"
check_body "GET /sector-performance"                         "$BASE_URL/sector-performance"                       200
check_body "GET /api/v1/earnings/feed?sort=upcoming"         "$BASE_URL/api/v1/earnings/feed?sort=upcoming"       200

echo "── Option Chain ──"
check      "GET /option-chain?ticker=NIFTY&expiry=nearest"   "$BASE_URL/option-chain?ticker=NIFTY&expiry=nearest" 200

echo "── Auth (public, should 422 on missing fields) ──"
check      "POST /login (missing creds → 422)"               "$BASE_URL/login" -X POST -H "Content-Type: application/json" -d '{}' 422
check      "POST /register (missing creds → 422)"            "$BASE_URL/register" -X POST -H "Content-Type: application/json" -d '{}' 422

echo ""
echo "═══ Results: $PASS passed, $FAIL failed ═══"
[ "$FAIL" -eq 0 ] && echo "All endpoints healthy ✅" || echo "Some endpoints failed ❌"
