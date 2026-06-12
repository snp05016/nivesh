# Extreme Analysis Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make extreme analysis run even while a normal analysis is active, fix the dead reformatter model, display the full StockProfile content inside the extreme result screen, add a no-credit decode-contract test, and ship a local `run_analysis.sh` runner.

**Architecture:** Backend dedup becomes one active job per `(user_id, scan_type)` with a stale-job guard, so extreme coexists with standard. iOS extracts `StockProfileView`'s sections into a reusable `StockProfileSections(vm:)` view that the extreme result screen embeds as profile tabs alongside the AI report. A pytest decode-contract test proves the iOS payload shape from cached data. A bash runner drives `/analyze` + polling against the live server.

**Tech Stack:** FastAPI, SQLAlchemy (sqlite), pytest (backend); SwiftUI (iOS, NOT compiled here); bash + curl + python3 (runner).

**Conventions:**
- After every Python edit: `python3 -m py_compile <file>`; fix recursively until clean.
- `gitnexus_detect_changes()` before each commit; scan diff for raw hex, magic spacing, `.system(size:)`, Western number scales (Million/Billion/Trillion), business logic in routers.
- Commit to `main` per task (AGENTS.md §6.4: `<verb> <component>: <desc>`, Co-Authored-By trailer).
- NEVER run `xcodebuild`. iOS tasks are edit + diff-review only.
- Server work uses `ssh root@165.22.221.18` with bounded timeouts; never read `.env`.

---

## Task 1: Scoped active-job lookup with stale-job guard (backend DAO)

**Files:**
- Modify: `backend/database.py` (near `get_active_job_for_user`, line ~928)
- Test: `backend/tests/test_job_dedup.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_job_dedup.py
import time
import database


def _mk_user_jobs(uid):
    """Create one standard QUEUED job; return its job_id."""
    j = database.create_job(uid, "RELIANCE", "NSE", "standard")
    return j["job_id"]


def test_scoped_lookup_ignores_other_scan_type():
    uid = 990001
    std_id = _mk_user_jobs(uid)
    # A standard job is active...
    assert database.get_active_job_for_user_and_type(uid, "standard") is not None
    # ...but an extreme lookup sees nothing, so extreme may start.
    assert database.get_active_job_for_user_and_type(uid, "extreme") is None
    database.update_job(std_id, status="SUCCEEDED")


def test_scoped_lookup_same_type_blocks():
    uid = 990002
    ext = database.create_job(uid, "TCS", "NSE", "extreme")
    assert database.get_active_job_for_user_and_type(uid, "extreme") is not None
    database.update_job(ext["job_id"], status="SUCCEEDED")


def test_stale_job_not_active():
    uid = 990003
    j = database.create_job(uid, "INFY", "NSE", "standard")
    # Force created_at far into the past (older than the 300s standard limit).
    with database.get_session() as s:
        row = s.query(database.AnalysisJob).filter_by(job_id=j["job_id"]).first()
        import datetime
        row.created_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=900)
        s.commit()
    assert database.get_active_job_for_user_and_type(uid, "standard") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_job_dedup.py -v`
Expected: FAIL — `AttributeError: module 'database' has no attribute 'get_active_job_for_user_and_type'`

- [ ] **Step 3: Implement the scoped lookup with stale guard**

Add to `backend/database.py` immediately after `get_active_job_for_user`:

```python
# Wall-clock limits mirror services.job_worker._WALLCLOCK_LIMITS so a crashed
# worker never permanently blocks new runs of the same scan_type.
_STALE_LIMITS = {"extreme": 600, "standard": 300}


def get_active_job_for_user_and_type(user_id: Optional[int], scan_type: str) -> Optional[dict]:
    """Active (QUEUED/RUNNING) job for this user AND scan_type, ignoring stale
    jobs older than their wall-clock limit. Lets extreme and standard coexist."""
    if user_id is None:
        return None
    import datetime
    cutoff_sec = _STALE_LIMITS.get(scan_type, 300)
    threshold = datetime.datetime.utcnow() - datetime.timedelta(seconds=cutoff_sec)
    with get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                       AnalysisJob.scan_type == scan_type,
                       AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
                       AnalysisJob.created_at >= threshold)
               .order_by(AnalysisJob.created_at.desc()).first())
        return _job_to_dict(j) if j else None
```

- [ ] **Step 4: py_compile + run tests**

Run: `cd backend && python3 -m py_compile database.py && python3 -m pytest tests/test_job_dedup.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/saumya/Desktop/nivesh
git add backend/database.py backend/tests/test_job_dedup.py
git commit -m "Add database: scoped active-job lookup per scan_type with stale guard

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Rewire analyze_endpoint dedup to allow extreme alongside normal

**Files:**
- Modify: `backend/routers/analysis.py:485-499` (the `get_active_job_for_user` block in `analyze_endpoint`)
- Test: `backend/tests/test_analyze_dedup_endpoint.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_analyze_dedup_endpoint.py
from fastapi.testclient import TestClient
from main import app
import database

client = TestClient(app)


def test_extreme_allowed_while_standard_active(monkeypatch):
    uid = 991001
    # Simulate an active standard job for this user.
    database.create_job(uid, "RELIANCE", "NSE", "standard")

    spawned = {}
    monkeypatch.setattr("services.job_manager.spawn_job",
                        lambda *a, **k: spawned.update(called=True))

    r = client.post("/analyze", json={
        "ticker": "RELIANCE", "exchange": "NSE",
        "user_id": uid, "scan_type": "extreme", "deep_scan": True})
    assert r.status_code == 200, r.text
    assert r.json()["scan_type"] == "extreme"
    assert spawned.get("called") is True


def test_duplicate_extreme_blocked(monkeypatch):
    uid = 991002
    database.create_job(uid, "TCS", "NSE", "extreme")
    monkeypatch.setattr("services.job_manager.spawn_job", lambda *a, **k: None)
    r = client.post("/analyze", json={
        "ticker": "TCS", "exchange": "NSE",
        "user_id": uid, "scan_type": "extreme", "deep_scan": True})
    assert r.status_code == 409
    assert r.json()["error_code"] == "ALREADY_RUNNING"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_analyze_dedup_endpoint.py -v`
Expected: FAIL — first test gets 409 (extreme blocked by the standard job under the old per-user check)

- [ ] **Step 3: Edit `analyze_endpoint`**

In `backend/routers/analysis.py`, replace the active-job block (currently lines ~485-499):

```python
    if req.user_id is not None:
        active = database.get_active_job_for_user(req.user_id)
        if active:
```

with the scan_type-scoped lookup:

```python
    if req.user_id is not None:
        active = database.get_active_job_for_user_and_type(req.user_id, req.scan_type)
        if active:
```

Leave the rest of the 409 payload unchanged (its `error_code`/`error_title`/`error_detail`/`job_id`/`ticker`/`suggested_action` shape stays identical for the iOS client).

- [ ] **Step 4: py_compile + run tests**

Run: `cd backend && python3 -m py_compile routers/analysis.py && python3 -m pytest tests/test_analyze_dedup_endpoint.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
cd /Users/saumya/Desktop/nivesh
git add backend/routers/analysis.py backend/tests/test_analyze_dedup_endpoint.py
git commit -m "Fix analysis.py: dedup per (user, scan_type) so extreme runs alongside normal

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Fix dead reformatter model (claude-3-5-sonnet-latest → claude-sonnet-4-6)

**Files:**
- Modify: `backend/services/orchestrator.py` (the `SONNET_MODEL` constant — confirm exact location with grep)
- Modify: `CLAUDE.md` §4.4 (note the retired ID)
- Test: `backend/tests/test_sonnet_model.py` (create)

- [ ] **Step 1: Locate the constant**

Run: `cd backend && grep -rn "claude-3-5-sonnet-latest\|SONNET_MODEL" services/ *.py | grep -v test`
Note the exact file(s) and line(s) that define `SONNET_MODEL`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_sonnet_model.py
import services.orchestrator as orch


def test_sonnet_model_is_valid_id():
    # The retired alias 404s on the Anthropic API; must be a current model.
    assert orch.SONNET_MODEL == "claude-sonnet-4-6"
    assert "3-5-sonnet-latest" not in orch.SONNET_MODEL
```

(If `SONNET_MODEL` lives in a different module per Step 1, import that module instead.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_sonnet_model.py -v`
Expected: FAIL — value is still `claude-3-5-sonnet-latest`

- [ ] **Step 4: Update the constant**

Change the definition found in Step 1:

```python
SONNET_MODEL = "claude-sonnet-4-6"    # Final reformatter (claude-3-5-sonnet-latest retired/404)
```

- [ ] **Step 5: Update CLAUDE.md §4.4**

In `CLAUDE.md`, change the LLM Config block line:

```python
SONNET_MODEL = "claude-sonnet-4-6"           # Final reformatter (3.5 alias retired)
```

- [ ] **Step 6: py_compile + run test**

Run: `cd backend && python3 -m py_compile services/orchestrator.py && python3 -m pytest tests/test_sonnet_model.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/saumya/Desktop/nivesh
git add backend/services/orchestrator.py backend/tests/test_sonnet_model.py CLAUDE.md
git commit -m "Fix orchestrator: SONNET_MODEL to claude-sonnet-4-6 (retired alias 404d)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Capture extreme fixture + decode-contract test (no LLM credits)

**Files:**
- Create: `backend/tests/fixtures/extreme_reliance.json`
- Test: `backend/tests/test_extreme_decode_contract.py` (create)

- [ ] **Step 1: Capture the fixture from the server**

Run:
```bash
mkdir -p /Users/saumya/Desktop/nivesh/backend/tests/fixtures
timeout 40 ssh -o ConnectTimeout=15 root@165.22.221.18 \
  'cd /root/nivesh/backend && sqlite3 stockapp.db "SELECT full_json FROM analysis_history WHERE scan_type=\"extreme\" ORDER BY id DESC LIMIT 1;"' \
  > /Users/saumya/Desktop/nivesh/backend/tests/fixtures/extreme_reliance.json
python3 -c "import json; json.load(open('/Users/saumya/Desktop/nivesh/backend/tests/fixtures/extreme_reliance.json')); print('valid json')"
```
Expected: `valid json`. If the file is empty, there is no extreme row — STOP and tell the user (do not fabricate a fixture).

- [ ] **Step 2: Write the decode-contract test**

```python
# backend/tests/test_extreme_decode_contract.py
import json
import os
from services.orchestrator import _normalize_response

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "extreme_reliance.json")


def _load():
    with open(FIXTURE) as f:
        return json.load(f)


def test_required_ios_fields_present_and_typed():
    """Mirrors the non-optional fields in iOS StockAnalysis.init(from:)."""
    r = _normalize_response(_load(), scan_type="extreme")
    assert isinstance(r["ticker"], str)
    assert isinstance(r["company_name"], str)
    assert isinstance(r["analysis_date"], str)
    assert isinstance(r["signal"], str)
    assert isinstance(r["confidence_pct"], int) and 0 <= r["confidence_pct"] <= 100
    assert isinstance(r["current_price_inr"], (int, float))
    for k in ("short_term_3m", "medium_term_12m", "long_term_36m"):
        assert k in r["target_prices"]
        assert isinstance(r["target_prices"][k], (int, float))
    for k in ("short_term", "medium_term", "long_term"):
        assert k in r["upside_downside_pct"]
    for arr in ("bull_case", "bear_case", "key_risks"):
        assert isinstance(r[arr], list) and len(r[arr]) > 0
    assert isinstance(r["disclaimer"], str)


def test_extreme_superset_blocks_present():
    r = _normalize_response(_load(), scan_type="extreme")
    assert r["analysis_tier"] == "extreme"
    assert isinstance(r["factor_scores"], dict)
    assert isinstance(r["piotroski"], dict)
    assert isinstance(r["financial_trends"], dict)
    assert isinstance(r["extreme_thesis_md"], str)
    # Optional/nullable per iOS decodeIfPresent — keys exist with safe types.
    assert "scenarios" in r and "valuation_bands" in r


def test_normalize_is_idempotent():
    once = _normalize_response(_load(), scan_type="extreme")
    twice = _normalize_response(dict(once), scan_type="extreme")
    assert twice["analysis_tier"] == "extreme"
    assert twice["signal"] == once["signal"]
```

- [ ] **Step 3: Run test to verify it passes (the contract already holds)**

Run: `cd backend && python3 -m pytest tests/test_extreme_decode_contract.py -v`
Expected: PASS (3 passed). If any assertion fails, that field is the real decode bug — fix `_normalize_response`'s extreme branch (`orchestrator.py` §16, line ~800) so the field is guaranteed, then re-run.

- [ ] **Step 4: Commit**

```bash
cd /Users/saumya/Desktop/nivesh
git add backend/tests/fixtures/extreme_reliance.json backend/tests/test_extreme_decode_contract.py
git commit -m "Add tests: extreme decode-contract test + cached fixture (no-credit hit check)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `run_analysis.sh` — local runner against the live server

**Files:**
- Create: `scripts/run_analysis.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Run a Nivesh analysis (normal | deep | extreme) against the live server and
# poll the v2 job API to completion. Local tool; talks to the remote API.
set -euo pipefail

HOST="http://165.22.221.18"   # matches iOS NetworkManager.defaultURL (port 80)
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

# Safe upper-limit timeout: extreme 600s, others 300s (override with --timeout).
if [[ -z "$TIMEOUT" ]]; then
  [[ "$SCAN_TYPE" == "extreme" ]] && TIMEOUT=600 || TIMEOUT=300
fi

jqget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('$1',''))"; }

echo "==> POST /analyze  ticker=$TICKER mode=$MODE scan_type=$SCAN_TYPE deep=$DEEP user=$USER_ID"
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
  printf "    [%3ss] %-10s %-24s %s%%\n" "$ELAPSED" "$STATUS" "${STAGE:-—}" "${PROG:-0}"
  case "$STATUS" in
    SUCCEEDED)
      echo "==> DONE"
      echo "$JOB" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('result') or {};print('signal      :',r.get('signal'));print('confidence  :',r.get('confidence_pct'));print('tier        :',r.get('analysis_tier','standard'));print('targets     :',r.get('target_prices'))"
      exit 0;;
    FAILED|CANCELLED|TIMEOUT)
      echo "==> $STATUS: $(echo "$JOB" | jqget error)"; exit 1;;
  esac
  sleep 5
done
```

- [ ] **Step 2: Make executable + bash syntax check**

Run: `chmod +x scripts/run_analysis.sh && bash -n scripts/run_analysis.sh && echo "syntax ok"`
Expected: `syntax ok`

- [ ] **Step 3: Smoke test usage/validation (no network)**

Run: `scripts/run_analysis.sh --mode extreme 2>&1 | head -1`
Expected: prints `Usage:` (missing --ticker/--user) and exits non-zero.

- [ ] **Step 4: Commit**

```bash
cd /Users/saumya/Desktop/nivesh
git add scripts/run_analysis.sh
git commit -m "Add scripts/run_analysis.sh: run normal/deep/extreme via job API with safe timeout

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Extract reusable `StockProfileSections(vm:)` from StockProfileView (iOS — no build)

**Files:**
- Create: `ios/StockApp/stockme/stockme/Views/StockProfileSections.swift`
- Modify: `ios/StockApp/stockme/stockme/Views/StockProfileView.swift`

**Note:** iOS is NOT compiled (AGENTS.md §6.2). Each edit is followed by a careful diff review. Preserve every `Theme.*` token, `Theme.Spacing.*`, haptic call, `.banknoteCard()`, and `GuillocheDivider()` exactly.

- [ ] **Step 1: Map the sections to extract**

Run: `cd ios/StockApp/stockme/stockme && grep -n "private func .*Section\|private func .*Tab\|TabView\|case overview\|case governance\|case macro\|case charts\|enum .*Tab\|activeTab" Views/StockProfileView.swift`
Identify the tab enum cases and the `private func` section builders bound to `vm` (overview, charts/technical, governance, macro/financials, financials table). Record their exact signatures.

- [ ] **Step 2: Create `StockProfileSections.swift`**

Create a view that owns NO state and renders each section from an injected `@ObservedObject var vm: StockProfileViewModel`, plus the active-tab binding. Move the section `private func` bodies verbatim into this view as methods (do not rewrite their internals — copy exactly to preserve ordinance compliance):

```swift
import SwiftUI

/// Reusable profile sections (overview, charts, governance, macro, financials)
/// driven by a StockProfileViewModel. Rendered by both StockProfileView and the
/// extreme analysis result screen. Logic is copied verbatim from StockProfileView
/// to keep the Banknote ordinance (Theme tokens, haptics, GuillocheDivider) intact.
struct StockProfileSections: View {
    @ObservedObject var vm: StockProfileViewModel
    @Binding var activeTab: StockProfileTab   // shared enum (see Step 3)

    var body: some View {
        TabView(selection: $activeTab) {
            overviewTab.tag(StockProfileTab.overview)
            chartsTab.tag(StockProfileTab.charts)
            governanceTab.tag(StockProfileTab.governance)
            macroTab.tag(StockProfileTab.macro)
            financialsTab.tag(StockProfileTab.financials)
        }
        .tabViewStyle(.page(indexDisplayMode: .never))
    }

    // <-- Move the section builder funcs (overviewTab, chartsTab, governanceTab,
    //     macroTab, financialsTab and their helper funcs like chartSection_RSI,
    //     harvesterGovernanceSection, governancePromoterSection, etc.) here
    //     VERBATIM from StockProfileView.swift. -->
}
```

- [ ] **Step 3: Promote the tab enum to a shared, non-private type**

If the tab enum is currently nested/private inside `StockProfileView`, move it to file scope in `StockProfileSections.swift` (or a small shared file) so both views reference the same cases:

```swift
enum StockProfileTab: Hashable {
    case overview, charts, governance, macro, financials
}
```

- [ ] **Step 4: Rewire `StockProfileView` to use `StockProfileSections`**

In `StockProfileView.swift`, replace the inline `TabView { ... }` body (line ~509) with:

```swift
StockProfileSections(vm: vm, activeTab: $activeTab)
```

Keep the surrounding header, horizontal tab selector (line ~478), `.task`/fetch calls, and navigation exactly as they were. Delete the section `private func`s that were moved (they now live in `StockProfileSections`).

- [ ] **Step 5: Diff review (no compile)**

Run: `cd /Users/saumya/Desktop/nivesh && git diff --stat ios/ && git diff ios/StockApp/stockme/stockme/Views/StockProfileView.swift | grep -nE "Color\(hex|\.system\(size|padding\([0-9]|Divider\(\)$" || echo "no ordinance violations in diff"`
Expected: `no ordinance violations in diff`. Manually confirm no section body was altered (only moved) and every moved func compiles by inspection (balanced braces, all referenced helpers moved together).

- [ ] **Step 6: Commit**

```bash
cd /Users/saumya/Desktop/nivesh
git add ios/StockApp/stockme/stockme/Views/StockProfileSections.swift ios/StockApp/stockme/stockme/Views/StockProfileView.swift
git commit -m "Refactor StockProfileView: extract reusable StockProfileSections(vm:)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Embed full profile tabs in the extreme result screen (iOS — no build)

**Files:**
- Modify: `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift` (extreme rendering near line ~387 `extremeChartSections` and the result body)

- [ ] **Step 1: Add a StockProfileViewModel owned by the extreme result view**

In the view that renders the analysis result (the one holding `analysis.analysisTier == "extreme"` at line ~387), add:

```swift
@StateObject private var profileVM: StockProfileViewModel
@State private var profileTab: StockProfileTab = .overview
@State private var extremeTab: ExtremeReportTab = .aiReport
```

Initialize `profileVM` from the ticker/exchange already in scope (add an `init` if the struct lacks one), e.g.:

```swift
init(ticker: String, exchange: String, /* existing params */ ) {
    _profileVM = StateObject(wrappedValue: StockProfileViewModel(ticker: ticker, exchange: exchange))
    // assign existing stored props...
}
```

Define the top-level tab enum at file scope:

```swift
enum ExtremeReportTab: Hashable { case aiReport, overview, charts, governance, macro, financials }
```

- [ ] **Step 2: Wrap the extreme result in a TabView (AI report + profile sections)**

Where the extreme branch renders today, gate on tier and present:

```swift
if analysis.analysisTier == "extreme" {
    TabView(selection: $extremeTab) {
        ScrollView {                        // existing AI report content
            VStack(spacing: Theme.Spacing.card) {
                // ...existing extreme AI sections + extremeChartSections(analysis)...
            }
            .padding(.horizontal, Theme.screenPadding)
        }
        .tag(ExtremeReportTab.aiReport)

        StockProfileSections(vm: profileVM, activeTab: $profileTab)
            .tag(ExtremeReportTab.overview)
    }
    .tabViewStyle(.page(indexDisplayMode: .never))
    .task { await loadProfile() }
}
```

(If embedding `StockProfileSections` as a single tab, keep its internal tab bar; alternatively flatten by mapping each `ExtremeReportTab` case to the matching `StockProfileTab` — choose the single-embed form to minimize risk.)

- [ ] **Step 3: Load profile data using the existing fetch methods**

Add the loader that fires the same endpoints `StockProfileView` uses:

```swift
private func loadProfile() async {
    await profileVM.fetchStockProfile()
    await profileVM.fetchChart()
    await profileVM.fetchFinancials()
    await profileVM.fetchHolders()
}
```

- [ ] **Step 4: Add a labeled tab selector (Banknote-compliant)**

Above the TabView, render a horizontal selector using the existing tab-chip pattern from `StockProfileView` (reuse its component/style). Each chip: `Theme.officialStampFont` label with `.tracking(1.5)`, `EKPressStyle`, and `HapticManager.selection()` in the tap closure. NO raw colors, NO `.system(size:)`, spacing via `Theme.Spacing.*`.

- [ ] **Step 5: Diff review (no compile)**

Run: `cd /Users/saumya/Desktop/nivesh && git diff ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift | grep -nE "Color\(hex|\.system\(size|padding\([0-9]|Divider\(\)$" || echo "no ordinance violations in diff"`
Expected: `no ordinance violations in diff`. Confirm standard (non-extreme) analyses still hit the original single-scroll path (the `if analysisTier == "extreme"` gate leaves the else branch untouched).

- [ ] **Step 6: Commit**

```bash
cd /Users/saumya/Desktop/nivesh
git add ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "Add AnalysisScreen: full StockProfile tabs inside extreme result (AI report + profile)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Deploy backend to server + verify extreme runs (cache-first, one optional live run)

**Files:** none (deploy + verify)

- [ ] **Step 1: Run the full affected backend test subset locally**

Run: `cd backend && python3 -m pytest tests/test_job_dedup.py tests/test_analyze_dedup_endpoint.py tests/test_sonnet_model.py tests/test_extreme_decode_contract.py -v`
Expected: all PASS.

- [ ] **Step 2: gitnexus detect changes**

Run `gitnexus_detect_changes()` and confirm only the expected backend symbols/files changed (database.py, analysis.py, orchestrator.py, tests). Report scope to the user.

- [ ] **Step 3: Deploy to server**

Run: `timeout 120 ssh -o ConnectTimeout=15 root@165.22.221.18 'cd /root/nivesh && git pull --ff-only && systemctl restart nivesh && sleep 3 && systemctl is-active nivesh'`
Expected: `active`. (Push to `main` first if not already: `git push origin main`.)

- [ ] **Step 4: Cache-first verification (no credits)**

Run: `scripts/run_analysis.sh --ticker RELIANCE --mode extreme --user <real-user-id>` only if the user wants a live run. Otherwise verify the dedup fix by confirming an extreme POST is NOT rejected while a standard job exists, via:
```bash
timeout 30 ssh -o ConnectTimeout=15 root@165.22.221.18 \
  'cd /root/nivesh/backend && python3 -c "import database; print(database.get_active_job_for_user_and_type(1, \"extreme\"))"'
```
Expected: prints `None` or a job dict — proving the new DAO is importable on the server.

- [ ] **Step 5: Confirm reformatter no longer 404s**

After any run, check the log tail for the Anthropic reformat line:
```bash
timeout 30 ssh -o ConnectTimeout=15 root@165.22.221.18 'journalctl -u nivesh --no-pager -n 40 | grep -i "reformat\|not_found\|claude-sonnet" | tail'
```
Expected: no `not_found_error` / `claude-3-5-sonnet-latest` 404 lines on new runs.

- [ ] **Step 6: Report** the verification results to the user. No commit needed (deploy only).

---

## Self-Review Notes

- **Spec coverage:** D1 → Tasks 1,2 (+3 model fix); D2 → Tasks 6,7; D3 → Task 4; D4 → Task 5; deploy/verify → Task 8. All covered.
- **Type consistency:** `get_active_job_for_user_and_type(user_id, scan_type)` defined in Task 1, called identically in Task 2 and Task 8. `StockProfileTab` defined in Task 6, reused in Task 7. `StockProfileSections(vm:activeTab:)` signature consistent across Tasks 6–7.
- **iOS caveat:** Tasks 6–7 cannot be compiled here; they rely on verbatim-move + diff review. The executor must inspect brace balance and that all helper funcs referenced by a moved section move together.
- **Stale-limit DRY:** `_STALE_LIMITS` in database.py duplicates `_WALLCLOCK_LIMITS` values from job_worker.py by intent (avoids a cross-import cycle); kept in sync via comment.
