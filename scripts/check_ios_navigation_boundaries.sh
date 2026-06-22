#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
content_view="$repo_root/ios/StockApp/stockme/stockme/ContentView.swift"
nl_screener="$repo_root/ios/StockApp/stockme/stockme/Views/NLScreenerScreen.swift"

if ! sed -n '/^struct MarketsView: View {/,/^}$/p' "$content_view" \
    | grep -q 'NavigationStack {'; then
    echo "FAIL: MarketsView must own the Markets navigation stack." >&2
    exit 1
fi

if ! sed -n '/private func sectionContent(_ section: MarketSection)/,/^    }/p' "$content_view" \
    | grep -q 'case \.nl_screener: NLScreenerScreen()'; then
    echo "FAIL: MarketsView must map .nl_screener to NLScreenerScreen()." >&2
    exit 1
fi

nl_screener_body="$({
    sed -n '/^struct NLScreenerScreen: View {/,/^    private var searchBar: some View {/p' "$nl_screener"
} || true)"

if grep -q 'NavigationStack {' <<<"$nl_screener_body"; then
    echo "FAIL: NLScreenerScreen is pushed by MarketsView and must not create a nested NavigationStack." >&2
    exit 1
fi

echo "PASS: NL Screener uses the parent Markets navigation stack."
