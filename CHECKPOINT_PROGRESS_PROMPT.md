# ANALYSIS CHECKPOINT PROGRESS — Implementation Prompt

Paste this entire message into Claude Code. Execute without asking questions.
Implement end-to-end, handle edge cases, ship a working product.

---

## OBJECTIVE

Replace the generic "AI ANALYSIS IN PROGRESS" spinner with a live, detailed checkpoint progress system showing exactly which agent is running, which LLM model it's using, and how far the analysis has progressed. The iOS `DialecticProgressView` already exists — this prompt upgrades the backend to emit real checkpoint events and updates the iOS fallback to match the actual pipeline.

---

## WHAT ALREADY EXISTS (DO NOT REBUILD)

| Component | File | Status |
|-----------|------|--------|
| iOS SSE client | `Components/DialecticProgressView.swift` → `AgentStreamClient` | ✅ Connects to `/api/v1/dashboard/stream?user_id=X&ticker=Y` |
| iOS progress UI | `Components/DialecticProgressView.swift` → `DialecticProgressView` | ✅ Timeline dots, status colors, fallback stages, scroll |
| iOS event model | `Components/DialecticProgressView.swift` → `AgentEvent` | ✅ agentName, status, message, timestamp |
| Backend SSE endpoint | `routers/dashboard.py` → `/api/v1/dashboard/stream` | ✅ StreamingResponse, polls every 2s |
| Backend analysis pipeline | `services/orchestrator.py` → `analyze()` | ✅ 8-stage pipeline |
| Subprocess runner | `tradingagents/nivesh/subprocess_runner.py` | ✅ multiprocessing.Process + Queue |

**What's missing:** The analysis pipeline doesn't emit checkpoint events. The SSE endpoint only sends generic dashboard snapshots. The iOS fallback stages don't match the real pipeline.

---

## THE REAL ANALYSIS PIPELINE (source of truth for checkpoints)

```
Stage  0: Factor Engine — Computing RSI, MACD, Bollinger, SMA (deterministic, no LLM)
Stage  1: Epistemic Feedback — Loading prior analysis audit
Stage  2: Governance Agent — DeepSeek V4 Flash
Stage  3: Market Analyst — DeepSeek V4 Flash  
Stage  4: Sentiment Analyst — DeepSeek V4 Flash
Stage  5: News Analyst — DeepSeek V4 Flash
Stage  6: Fundamentals Analyst — DeepSeek V4 Flash
Stage  7: Bull/Bear Debate Round 1/3 — DeepSeek V4 Flash
Stage  8: Bull/Bear Debate Round 2/3 — DeepSeek V4 Flash
Stage  9: Bull/Bear Debate Round 3/3 — DeepSeek V4 Flash
Stage 10: Research Manager — Claude Haiku 4.5 (Tier 2)
Stage 11: Trader — DeepSeek V4 Flash
Stage 12: Risk Committee: Aggressive — DeepSeek V4 Flash
Stage 13: Risk Committee: Conservative — DeepSeek V4 Flash
Stage 14: Risk Committee: Neutral — DeepSeek V4 Flash
Stage 15: Portfolio Manager — Claude Haiku 4.5 (Tier 2)
Stage 16: Claude Reformatter — Claude Sonnet (Tier 3)
Stage 17: Piotroski F-Score computation
Stage 18: Live price refresh + Advisor matrix load
Stage 19: Analysis complete
```

Total: 20 checkpoints. Each shows the agent name, LLM model, and a human-readable message.

---

## IMPLEMENTATION

### BACKEND: 3 files to modify

### FILE 1: backend/tradingagents-core/tradingagents/nivesh/subprocess_runner.py
**Change:** Add a second multiprocessing.Queue for progress events. The worker puts progress dicts on this queue as it moves through stages.

Add this BEFORE the existing `_worker()` function:

```python
# Progress event queue — the worker puts stage updates here,
# the parent reads them for SSE streaming.
def _worker_with_progress(
    result_queue: multiprocessing.Queue,
    progress_queue: multiprocessing.Queue,  # NEW
    ticker: str,
    trade_date: str,
    config_overrides: dict[str, Any],
) -> None:
    """Entry point with progress reporting."""
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        # Pass progress_queue into config so agents can report
        config = {**DEFAULT_CONFIG, **config_overrides, "_progress_queue": progress_queue}
        
        progress_queue.put({
            "agent": "Initialization",
            "status": "thinking",
            "message": "Initializing LangGraph agent graph...",
            "llm_model": "N/A",
            "stage": 0,
            "total_stages": 20,
        })
        
        graph = TradingAgentsGraph(
            selected_analysts=config_overrides.get(
                "selected_analysts", ["governance", "market", "news", "fundamentals"]
            ),
            config=config,
        )
        
        progress_queue.put({
            "agent": "Initialization",
            "status": "complete",
            "message": "Agent graph compiled successfully",
            "llm_model": "N/A",
            "stage": 0,
            "total_stages": 20,
        })
        
        final_state, decision = graph.propagate(ticker, trade_date)
        
        result_queue.put({
            "status": "ok",
            "final_trade_decision": final_state.get("final_trade_decision", ""),
            "decision": decision,
            "market_report": final_state.get("market_report", ""),
            "news_report": final_state.get("news_report", ""),
            "fundamentals_report": final_state.get("fundamentals_report", ""),
            "sentiment_report": final_state.get("sentiment_report", ""),
            "governance_report": final_state.get("governance_report", ""),
            "investment_plan": final_state.get("investment_plan", ""),
            "trader_investment_plan": final_state.get("trader_investment_plan", ""),
        })
    except Exception as exc:
        progress_queue.put({
            "agent": "Error",
            "status": "error",
            "message": str(exc)[:200],
            "llm_model": "N/A",
            "stage": -1,
            "total_stages": 20,
        })
        result_queue.put({"status": "error", "error": str(exc)})


def run_analysis_isolated(
    ticker: str,
    trade_date: str,
    user_id: int | None = None,
    config_overrides: dict[str, Any] | None = None,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run analysis in isolated subprocess with progress tracking.
    
    Returns: dict with keys "status", "result", "progress_events"
    """
    if user_id is not None and user_id in _running_analyses:
        raise AnalysisAlreadyRunningError(
            f"Analysis already running for user_id={user_id}. Please wait."
        )

    if user_id is not None:
        _running_analyses.add(user_id)

    result_queue: multiprocessing.Queue = multiprocessing.Queue()
    progress_queue: multiprocessing.Queue = multiprocessing.Queue()  # NEW
    progress_events: list[dict] = []
    
    process = multiprocessing.Process(
        target=_worker_with_progress,  # UPDATED
        args=(result_queue, progress_queue, ticker, trade_date, config_overrides or {}),
        daemon=True,
    )

    try:
        process.start()
        
        deadline = time.monotonic() + timeout_seconds
        result: dict[str, Any] | None = None

        while time.monotonic() < deadline:
            # Drain progress queue (non-blocking)
            while not progress_queue.empty():
                try:
                    event = progress_queue.get_nowait()
                    progress_events.append(event)
                except Exception:
                    break
            
            if not result_queue.empty():
                result = result_queue.get_nowait()
                break
            if not process.is_alive():
                if not result_queue.empty():
                    result = result_queue.get_nowait()
                break
            time.sleep(0.3)  # Poll faster (was 0.5s)

        # Drain any remaining progress events
        while not progress_queue.empty():
            try:
                progress_events.append(progress_queue.get_nowait())
            except Exception:
                break

        if result is None:
            process.terminate()
            process.join(timeout=5)
            raise TimeoutError(
                f"Analysis for {ticker} timed out after {timeout_seconds}s"
            )

        if result.get("status") == "error":
            raise RuntimeError(
                f"Worker failed for {ticker}: {result.get('error')}"
            )

        return {
            "status": "ok",
            "result": result,
            "progress_events": progress_events,  # NEW
        }

    finally:
        if user_id is not None:
            _running_analyses.discard(user_id)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
```

### FILE 2: backend/tradingagents-core/tradingagents/graph/trading_graph.py
**Change:** Add progress reporting at each agent stage. The `propagate()` method already calls agents sequentially — inject progress events before each major node.

Find the `propagate()` method. Before each major stage (after the graph is compiled, before `graph.invoke()`), emit progress events. Since we can't easily hook into the graph stream from the parent, use a simpler approach: put progress on the queue from the `_worker_with_progress` before calling `graph.propagate()`.

Actually, the cleanest approach: add progress hooks to `setup.py` agent nodes.

### FILE 3: backend/tradingagents-core/tradingagents/graph/setup.py
**Change:** Wrap each analyst node and debate node to emit progress before execution.

In `setup_graph()`, after creating each agent (e.g., `create_market_analyst(self.quick_thinking_llm)`), wrap it with a progress-emitting decorator:

```python
def _with_progress(agent_name: str, llm_model: str, stage: int, total: int, inner_fn):
    """Wrap an agent node to emit progress before and after execution."""
    def wrapped(state):
        config = state.get("_config", {})
        progress_queue = config.get("_progress_queue")
        if progress_queue:
            try:
                progress_queue.put({
                    "agent": agent_name,
                    "status": "thinking",
                    "message": f"Running {agent_name}...",
                    "llm_model": llm_model,
                    "stage": stage,
                    "total_stages": total,
                })
            except Exception:
                pass
        
        try:
            result = inner_fn(state)
        except Exception as e:
            if progress_queue:
                try:
                    progress_queue.put({
                        "agent": agent_name,
                        "status": "error",
                        "message": str(e)[:200],
                        "llm_model": llm_model,
                        "stage": stage,
                        "total_stages": total,
                    })
                except Exception:
                    pass
            raise
        
        if progress_queue:
            try:
                progress_queue.put({
                    "agent": agent_name,
                    "status": "complete",
                    "message": f"{agent_name} completed successfully",
                    "llm_model": llm_model,
                    "stage": stage,
                    "total_stages": total,
                })
            except Exception:
                pass
        
        return result
    return wrapped

# Then in setup_graph(), wrap each factory:
# "governance": lambda: _with_progress("Governance", "DeepSeek V4 Flash", 2, 20, 
#     create_governance_analyst(self.quick_thinking_llm)()),
# "market": lambda: _with_progress("Market Analyst", "DeepSeek V4 Flash", 3, 20,
#     create_market_analyst(self.quick_thinking_llm)()),
# ... etc for each agent
```

### FILE 4: backend/services/orchestrator.py
**Change:** 
1. Store progress events in a shared dict that the SSE endpoint reads from
2. Update `run_trading_agents()` to return progress events
3. Update the `analyze()` function to forward progress

Add at module level:
```python
# Shared progress state for SSE streaming
import threading
_analysis_progress_lock = threading.Lock()
_analysis_progress: dict[str, list[dict]] = {}  # ticker → list of checkpoint dicts

def get_analysis_progress(ticker: str) -> list[dict]:
    """Thread-safe read of analysis progress for SSE endpoint."""
    with _analysis_progress_lock:
        return _analysis_progress.get(ticker.upper(), [])

def set_analysis_progress(ticker: str, event: dict):
    """Thread-safe write of analysis progress."""
    with _analysis_progress_lock:
        key = ticker.upper()
        if key not in _analysis_progress:
            _analysis_progress[key] = []
        _analysis_progress[key].append(event)
        # Cleanup old entries (keep only 30 minutes)
        now = time.time()
        for k in list(_analysis_progress.keys()):
            if _analysis_progress[k]:
                last_ts = _analysis_progress[k][-1].get("timestamp", 0)
                if now - last_ts > 1800:
                    del _analysis_progress[k]
```

In the `run_trading_agents()` function, after the subprocess returns, store the progress events:
```python
    progress_events = isolated_result.get("progress_events", [])
    for event in progress_events:
        event["timestamp"] = time.time()
        set_analysis_progress(ticker, event)
```

### FILE 5: backend/routers/dashboard.py
**Change:** Update `event_generator()` to emit actual checkpoint events instead of generic snapshots.

```python
async def event_generator(request: Request):
    """Generate SSE events with live analysis checkpoint progress."""
    ticker = request.query_params.get("ticker", "")
    
    while True:
        if await request.is_disconnected():
            break
        
        if ticker:
            from services.orchestrator import get_analysis_progress
            events = get_analysis_progress(ticker)
            
            # Send each new event as an SSE message
            for event in events:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        
        await asyncio.sleep(0.5)  # Poll faster during analysis (was 2s)
```

---

### iOS: 1 file to modify

### FILE 6: ios/StockApp/stockme/stockme/Components/DialecticProgressView.swift
**Change:** Update the `fallbackStages` array to match the real 20-stage pipeline:

```swift
private static let fallbackStages: [(agent: String, message: String, llmModel: String)] = [
    ("Factor Engine", "Computing RSI, MACD, Bollinger Bands, SMA crossovers...", "Deterministic"),
    ("Epistemic Feedback", "Loading prior analysis audit and outcome tracking...", "N/A"),
    ("Governance Agent", "Scanning for auditor resignations, SEBI actions, promoter pledges...", "DeepSeek V4 Flash"),
    ("Market Analyst", "Analyzing price structure, volume profiles, DMA signals...", "DeepSeek V4 Flash"),
    ("Sentiment Analyst", "Processing social sentiment and news mood...", "DeepSeek V4 Flash"),
    ("News Analyst", "Scanning headlines, macro catalysts, red flags...", "DeepSeek V4 Flash"),
    ("Fundamentals Analyst", "Decomposing P&L quality, FCF, working capital...", "DeepSeek V4 Flash"),
    ("Bull/Bear Debate", "Round 1/3 — Building bullish thesis with catalysts...", "DeepSeek V4 Flash"),
    ("Bull/Bear Debate", "Round 2/3 — Bear researcher challenging assumptions...", "DeepSeek V4 Flash"),
    ("Bull/Bear Debate", "Round 3/3 — Final rebuttals and evidence weighing...", "DeepSeek V4 Flash"),
    ("Research Manager", "Synthesizing debate, assigning verdict with confidence...", "Claude Haiku 4.5"),
    ("Trader", "Computing entry, target, and stop-loss levels...", "DeepSeek V4 Flash"),
    ("Risk Committee", "Aggressive risk profile stress-testing levels...", "DeepSeek V4 Flash"),
    ("Risk Committee", "Conservative risk profile capital preservation check...", "DeepSeek V4 Flash"),
    ("Risk Committee", "Neutral risk profile blended assessment...", "DeepSeek V4 Flash"),
    ("Portfolio Manager", "Final verdict — synthesizing all prior nodes...", "Claude Haiku 4.5"),
    ("Claude Reformatter", "Reformatting output into structured JSON...", "Claude Sonnet"),
    ("Piotroski Score", "Computing 9-point financial health check...", "Deterministic"),
    ("Live Data Refresh", "Refreshing price, news, and advisor intelligence...", "N/A"),
    ("Analysis Complete", "Verdict ready — rendering results...", "N/A"),
]
```

Also update `AgentEvent` to include `llmModel`:
```swift
struct AgentEvent: Identifiable, Equatable {
    let id = UUID()
    let agentName: String
    let status: String
    let message: String
    let llmModel: String       // NEW — e.g. "DeepSeek V4 Flash", "Claude Haiku 4.5"
    let stage: Int             // NEW — 0-19
    let totalStages: Int       // NEW — 20
    let timestamp: Date
    
    static func == (lhs: AgentEvent, rhs: AgentEvent) -> Bool { lhs.id == rhs.id }
}
```

Update `AgentEventRow` to show the LLM model as a small badge/tag next to the agent name:
```swift
// Inside AgentEventRow body, add after agentName Text:
if !event.llmModel.isEmpty && event.llmModel != "N/A" {
    Text(event.llmModel)
        .font(.system(size: 7, weight: .semibold, design: .monospaced))
        .foregroundStyle(Theme.securityGold.opacity(0.7))
        .padding(.horizontal, 4).padding(.vertical, 1)
        .background(Theme.securityGold.opacity(0.1))
        .clipShape(Capsule())
}
```

Add a progress bar at the top of `DialecticProgressView`:
```swift
// Progress bar showing completed stages / total
let completedStages = max(client.events.filter { $0.status == "complete" }.count, 
                          fallbackStep > 0 ? fallbackStep : 0)
let totalStages = 20

GeometryReader { geo in
    ZStack(alignment: .leading) {
        RoundedRectangle(cornerRadius: 2)
            .fill(Theme.inkTertiary.opacity(0.1))
            .frame(height: 3)
        RoundedRectangle(cornerRadius: 2)
            .fill(Theme.securityGold)
            .frame(width: geo.size.width * CGFloat(completedStages) / CGFloat(totalStages), height: 3)
            .animation(.easeInOut(duration: 0.4), value: completedStages)
    }
}
.frame(height: 3)
.padding(.bottom, Theme.Spacing.standard)

// Stage counter
Text("Stage \(completedStages)/\(totalStages)")
    .font(.system(size: 8, weight: .medium, design: .monospaced))
    .foregroundStyle(Theme.inkTertiary)
    .padding(.bottom, Theme.Spacing.card)
```

---

## VERIFICATION

1. Trigger an analysis on any stock
2. The loading screen should show the 20-stage checkpoint timeline
3. Each checkpoint shows: agent name, LLM model badge, human-readable message
4. Completed stages show green dots, current stage shows pulsing gold dot
5. Progress bar at top fills as stages complete
6. Stage counter shows "Stage 7/20" etc.
7. Fallback works when SSE doesn't connect (shows animated sequential stages)

---

## CRITICAL "DO NOT" RULES

- Do NOT change the existing analysis logic or agent prompts
- Do NOT change the LangGraph node wiring
- Do NOT change how `DialecticProgressView` connects/disconnects (scenePhase handling)
- Do NOT add new dependencies
- Do NOT change the SSE event format (`agent`, `status`, `message` keys must remain)
- The progress_queue is optional — agents skip progress if queue is None
- Keep the existing `AgentEventRow` design (timeline dots, status colors)

---

## EXPECTED RESULT

When a user triggers any AI analysis:
- They see a live, 20-stage checkpoint progress view
- Each stage shows the agent name, what it's doing, and which LLM model
- Green checkmarks for completed stages, pulsing gold for current
- A progress bar fills left-to-right as stages complete
- "Stage 14/20 — Portfolio Manager — Claude Haiku 4.5" is visible
- The user understands exactly what's happening and how long until done
- If SSE fails, animated fallback shows the same stages sequentially
