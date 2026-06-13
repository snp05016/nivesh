#!/bin/bash
cd "$(dirname "$0")/../ios/StockApp/stockme/stockme"
echo "=== Nivesh Crash Pattern Lint ==="
echo ""

echo "--- ForEach(id: \.self) on String arrays (potential crash) ---"
grep -rn 'ForEach.*id: *\\\.self' --include="*.swift" Views/ Utilities/ Components/ 2>/dev/null | grep -v "0\." | grep -v "\.allCases" || echo "  None found"

echo ""
echo "--- ForEach without id: on non-Identifiable types ---"
grep -rn 'ForEach([a-zA-Z_].*id:' --include="*.swift" Views/ Utilities/ Components/ 2>/dev/null | head -20

echo ""
echo "--- Force-unwraps (!) ---"
grep -rn '!$' --include="*.swift" Views/ Utilities/ Components/ 2>/dev/null | grep -v 'import\|//\|nil!' | grep -v '"!' | head -20 || echo "  None found"

echo ""
echo "Done."
