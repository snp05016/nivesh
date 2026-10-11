#!/usr/bin/env bash
# Grep gates for iOS app-source regressions found by the 2026-10 audit.
# Runs in iOS CI (static-checks job) and locally; no Xcode. Append one `gate` per rule.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC=ios/StockApp/stockme/stockme
[ -d "$SRC" ] || { echo "ios_lint_gates: $SRC not found"; exit 1; }
FAIL=0

# gate NAME PATTERN [EXCLUDE_REGEX] [DIR]: fail when PATTERN matches a Swift file under
# DIR (default: app sources). Lines matching EXCLUDE_REGEX, tested against
# "path:line:text", are allowed.
gate() {
  local name=$1 pattern=$2 exclude=${3:-} dir=${4:-$SRC} hits rc=0
  [ -d "$dir" ] || { echo "FAIL [$name]: $dir not found"; FAIL=1; return; }
  hits=$(grep -rnE --include='*.swift' -e "$pattern" "$dir") || rc=$?
  [ "$rc" -le 1 ] || { echo "FAIL [$name]: grep error $rc"; FAIL=1; return; }
  if [ -n "$exclude" ] && [ -n "$hits" ]; then
    hits=$(printf '%s\n' "$hits" | grep -vE -e "$exclude" || true)
  fi
  if [ -n "$hits" ]; then
    echo "FAIL [$name]:"
    printf '%s\n' "$hits"
    FAIL=1
  fi
}

# Empty Xcode template tests count as coverage while testing nothing (IOSCORE-28).
gate template-stub 'Write your test here' '' ios/StockApp/stockme/stockmeTests

# One environment-injected AuthManager; no shadow singleton or "act as user #1" fallback (IOSCORE-31).
gate auth-singleton 'AuthManager\.shared'
gate user-id-fallback 'userId \?\? 1([^0-9.]|$)'

[ "$FAIL" -eq 0 ] && echo "ios_lint_gates: OK"
exit "$FAIL"
