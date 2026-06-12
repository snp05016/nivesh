# Analysis Engine v2 — iOS Observability (Phase 2)

> **Goal:** The app knows when analysis is running, shows live progress anywhere, survives navigation/background, and renders extreme output as charts. Backend job API is frozen and merged.

**Architecture:** A new `AnalysisEngineManager` (`@Observable`, injected via `.environmentObject()`) polls `GET /analyze/active` + `/analyze/job/{id}`. A global running pill overlays the `TabView`. The `AnalysisScreen` switches from the blocking old `NetworkManager.analyze()` to the v2 job model (`POST`→get `job_id`→poll→decode). Extreme bundles get Codable model structs and chart-rendering views in `AnalysisScreen`.

**Working dir:** `/Users/saumya/Desktop/nivesh/ios/StockApp/stockme/stockme`

**No `xcodebuild` per AGENTS.md §6.2.**

---

### Task 1: `NetworkManager` — v2 job API methods

**Files:** Modify `NetworkManager.swift`

- [ ] Add `startAnalysisJob(ticker, exchange, userId, scanType)` → POST /analyze → returns `{job_id, status}`
- [ ] Add `pollJob(jobId, userId)` → GET /analyze/job/{jobId}?user_id={userId} → returns `JobStatus` struct
- [ ] Add `cancelJob(jobId, userId)` → POST /analyze/{jobId}/cancel?user_id={userId}
- [ ] Add `activeJob(userId)` → GET /analyze/active?user_id={userId}
- [ ] Add `JobStatus` Codable struct in Models.swift (id, status, stage, progressPct, checkpoints[], tokensUsed, error, result?)

---

### Task 2: `AnalysisEngineManager` (new Observable)

**Files:** Create `AnalysisEngineManager.swift`

- [ ] Polls `/analyze/active` every 3s
- [ ] On active job: polls `/analyze/job/{id}` every 2s for checkpoints
- [ ] Exposes: `isRunning`, `activeJobId`, `stage`, `progressPct`, `checkpoints` (last 5), `error`
- [ ] `cancel()` → calls /cancel + stops polling
- [ ] On SUCCEEDED/FAILED/TIMEOUT: fires local notification
- [ ] Persists last-known result so app can show it when user taps "View Report"
- [ ] Injected as `.environmentObject()` in `stockmeApp`

---

### Task 3: Global running indicator

**Files:** Modify `ContentView.swift`

- [ ] Add a `GlobalRunningPillView` overlay at top of `mainTabView`
- [ ] Shows when `engineManager.isRunning`: gold pulsing pill with ticker + progress %
- [ ] Tap → navigates to an Engine Activity sheet or screen
- [ ] Banknote-compliant (Theme tokens, haptics, EKPressStyle)

---

### Task 4: Engine Activity screen

**Files:** Create `Views/EngineActivityView.swift`

- [ ] Shows live checkpoints list, progress ring/bar, stage, cancel button
- [ ] Renders `CheckpointRow` for each emitted event with timestamp + message
- [ ] Fully Banknote-compliant

---

### Task 5: `AnalysisViewModel` → v2 job model

**Files:** Modify `Views/AnalysisScreen.swift`

- [ ] `fetchAnalysis` becomes: POST /analyze → get job_id → spin up a polling `Task` that reads JobStatus every 2s
- [ ] Loading state shows engine checkpoints (not just a generic spinner)
- [ ] `cancelAnalysis()` calls the cancel endpoint
- [ ] On SUCCEEDED: decode result from JobStatus.result (which is the full_json)
- [ ] `onDisappear` no longer cancels (the analysis survives)
- [ ] URLSession timeout drops from 1200s to 30s (no more connection-tied runs)

---

### Task 6: Extreme model extensions + chart rendering

**Files:** Modify `Models.swift`, modify `Views/AnalysisScreen.swift`

- [ ] Add Codable structs: `FactorScores`, `ScenarioBundle`, `ValuationBands`, `ExtendedThesis`, `GovernanceFlag`, `FinancialTrends`, `OwnershipTrends`
- [ ] Add optional extreme fields to `StockAnalysis`
- [ ] `AnalysisScreen` gains a `chartsTab` (or inline sections) rendering factor radar, scenarios, financial trends, ownership chart — using Theme colors, no 3D, labeled axes, with `GuillocheDivider` separators

---

### Task 7: `NetworkManager` timeout fix + `StockActionHubView` copy update

**Files:** Modify `NetworkManager.swift`, modify `Views/StockActionHubView.swift`

- [ ] `URLSessionConfiguration.timeoutIntervalForRequest` = 30 (was 1200 — the connection-tied era)
- [ ] Extreme scan card subtitle updated: "DeepSeek reasoning, 4 graph bundles, 10-min deep report"
