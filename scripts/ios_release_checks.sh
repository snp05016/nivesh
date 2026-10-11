#!/usr/bin/env bash
# Static App Store readiness checks for the iOS app (macOS: needs plutil).
# Usage: bash scripts/ios_release_checks.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../ios/StockApp/stockme" && pwd)"
INFO="$APP_DIR/Info.plist"
# Every shipped binary (app + widget .appex) needs its own manifest (ITMS-91053).
PRIVACY_MANIFESTS=("$APP_DIR/stockme/PrivacyInfo.xcprivacy" "$APP_DIR/NiveshWidget/PrivacyInfo.xcprivacy")
ENTITLEMENTS="$APP_DIR/stockme.entitlements"
PBXPROJ="$APP_DIR/stockme.xcodeproj/project.pbxproj"

failures=0
fail() { echo "FAIL: $*" >&2; failures=$((failures + 1)); }
has_key() { plutil -extract "$2" raw -o /dev/null "$1" >/dev/null 2>&1; }

plutil -lint "$INFO" >/dev/null || fail "Info.plist does not lint"
if grep -q "NSAllowsArbitraryLoads" "$INFO"; then
    fail "Info.plist disables ATS (NSAllowsArbitraryLoads)"
fi
has_key "$INFO" "CFBundleURLTypes.0.CFBundleURLSchemes.0" || fail "Info.plist has no CFBundleURLTypes URL scheme"
has_key "$INFO" "NSFaceIDUsageDescription" || fail "Info.plist missing NSFaceIDUsageDescription"

for PRIVACY in "${PRIVACY_MANIFESTS[@]}"; do
    if [ ! -f "$PRIVACY" ]; then
        fail "PrivacyInfo.xcprivacy missing at $PRIVACY"
        continue
    fi
    plutil -lint "$PRIVACY" >/dev/null || fail "$PRIVACY does not lint"
    grep -q "NSPrivacyAccessedAPICategoryUserDefaults" "$PRIVACY" \
        || fail "$PRIVACY does not declare the UserDefaults required-reason API"
done
# The widget folder is not a synchronized group, so its manifest must be in the widget Resources phase.
grep -q "PrivacyInfo.xcprivacy in Resources" "$PBXPROJ" \
    || fail "project.pbxproj does not bundle NiveshWidget/PrivacyInfo.xcprivacy"

if [ ! -f "$ENTITLEMENTS" ]; then
    fail "entitlements file missing at $ENTITLEMENTS"
else
    has_key "$ENTITLEMENTS" "aps-environment" || fail "entitlements lack aps-environment (push)"
fi

grep -q "CODE_SIGN_ENTITLEMENTS" "$PBXPROJ" || fail "project.pbxproj does not set CODE_SIGN_ENTITLEMENTS"

if [ "$failures" -gt 0 ]; then
    echo "$failures iOS release check(s) failed" >&2
    exit 1
fi
echo "iOS release checks passed"
