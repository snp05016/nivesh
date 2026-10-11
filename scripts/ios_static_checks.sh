#!/usr/bin/env bash
# Static guards for iOS build breakers that have already reached main once:
# committed conflict markers and statements injected into closures and
# ViewBuilder bodies. Runs in iOS CI (static-checks job) and locally; no Xcode.
set -euo pipefail
cd "$(dirname "$0")/.."

status=0

# Run a check command; fail (after all checks ran) if it prints anything or errors.
fail_if_any() {
  local out rc=0
  out=$("$@" 2>&1) || rc=$?
  if [ -n "$out" ] || [ "$rc" -gt 1 ]; then
    echo "FAIL: $*"
    [ -z "$out" ] || echo "$out"
    status=1
  fi
}

SRC=ios/StockApp/stockme
# BSD grep skips a missing --include operand silently; never pass because the tree moved.
[ -d "$SRC" ] || { echo "ios_static_checks: $SRC not found"; exit 1; }
swift_grep() { grep -rnE --include='*.swift' -e "$1" "$SRC"; }

# Unresolved merge/stash conflict markers.
fail_if_any swift_grep '^(<<<<<<<|=======$|>>>>>>>)'
# A statement before a closure's parameter clause: `{ HapticManager.selection(); entry in`.
fail_if_any swift_grep '\{ *HapticManager\.[A-Za-z]+\([^)]*\); *[A-Za-z_][A-Za-z0-9_]*( *, *[A-Za-z_][A-Za-z0-9_]*)* +in( |$)'
# A statement inside a ViewBuilder: some-View function body, toolbar content, Button label.
fail_if_any swift_grep '-> some View *\{ *HapticManager'
fail_if_any swift_grep '\.toolbar *\{ *HapticManager'
fail_if_any swift_grep 'Button\([^()]*action: *[^(){}]*\) *\{ *HapticManager'
# Auth state has one owner: the @StateObject in stockmeApp, injected as an environment
# object. A static instance would be a second, stale source of truth (audit WIP-12).
fail_if_any swift_grep 'AuthManager\.shared\b|static +(let|var) +[A-Za-z_]+ *(: *AuthManager)? *= *AuthManager\('

if [ "$status" -ne 0 ]; then
  echo "ios_static_checks: FAILED"
  exit 1
fi
echo "ios_static_checks: OK"
