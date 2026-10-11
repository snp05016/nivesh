#!/usr/bin/env bash
# ARCH-15 gates. Fails when:
#  - a view or component builds its own request (URLSession.shared / URLRequest(),
#    which skips NetworkManager's Bearer token and error mapping; add a
#    NetworkManager extension method instead);
#  - a Swift file outside the allowlist grows past MAX_LINES (SwiftUI stack-overflow
#    risk, AGENTS.md 6.6).
# Runs in iOS CI (static-checks job) and locally; no Xcode.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC=ios/StockApp/stockme/stockme
MAX_LINES=1500
# Existing god files, to be split (IOSUI-30). Do not add to this list.
ALLOW_LONG='^(Views/HomeScreen|Views/PortfolioScreen|Views/EarningsDashboardView|NetworkManager)\.swift$'
[ -d "$SRC" ] || { echo "lint_ios_networking: $SRC not found"; exit 1; }
FAIL=0

rc=0
hits=$(grep -rnE --include='*.swift' -e 'URLSession\.shared|URLRequest\(' "$SRC/Views" "$SRC/Components") || rc=$?
[ "$rc" -le 1 ] || { echo "lint_ios_networking: grep error $rc"; exit 1; }
hits=$(printf '%s\n' "$hits" | grep -vE '^[^:]+:[0-9]+:[[:space:]]*//' || true)
if [ -n "$hits" ]; then
  echo "FAIL [raw-networking-in-views]: route these through a NetworkManager method:"
  printf '%s\n' "$hits"
  FAIL=1
fi

while IFS= read -r -d '' f; do
  rel=${f#"$SRC"/}
  n=$(wc -l < "$f" | tr -d ' ')
  if [ "$n" -gt "$MAX_LINES" ] && ! printf '%s\n' "$rel" | grep -qE "$ALLOW_LONG"; then
    echo "FAIL [file-too-long]: $rel has $n lines (max $MAX_LINES); split it"
    FAIL=1
  fi
done < <(find "$SRC" -name '*.swift' -print0)

[ "$FAIL" -eq 0 ] && echo "lint_ios_networking: OK"
exit "$FAIL"
