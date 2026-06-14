# Feature Blueprint: Extreme Analysis Pipeline Upgrade

## 1. Objective
Refactor the "Extreme" tier of the AI Analysis pipeline to enforce structured JSON rendering, wire up missing data pipelines, and convert factor scoring to be mathematically sector-relative rather than hardcoded.

---

## 2. Requirements & Implementation Steps

### 2.1 Structured Extreme Thesis (No Markdown Blobs)
Currently, `prompts.py` asks the LLM for `extreme_thesis_md` as a single 1000-word markdown string. This violates the frontend UI density principles.
- **Action:** Modify the prompt to require a structured JSON array for the extreme analysis.
- **Schema:**
  ```json
  "extreme_thesis": [
    {
      "section_title": "Management Integrity & Promoter Risk",
      "content": "..."
    },
    {
      "section_title": "Retail Sentiment & Herding",
      "content": "..."
    },
    {
      "section_title": "Historical Drawdown Stress",
      "content": "..."
    }
  ]
  ```

### 2.2 Wire Up Missing Deterministic Bundles
In `backend/services/extreme_enrichers.py`, several functions return dummy data.
- **Action:** Implement `_peer_comparison` to fetch actual sector peers (using `yfinance` or a local database query) instead of returning `[]`.
- **Action:** Implement a basic `growth` factor score by looking at the last 3 years of revenue/net profit trends.

### 2.3 Sector-Relative Factor Scoring
In `extreme_enrichers.py`, `_value_score` uses absolute clamping (e.g., PE 40+ = 0 score).
- **Action:** Instead of hardcoded `40.0` or `8.0`, calculate or fetch the **Sector Median P/E** and **Sector Median P/B**.
- **Math:** Score the stock based on its standard deviation from the sector median. A PE of 45 in a sector where the median is 50 should score highly.

---

## 3. Execution Directives (AGENTS.md)
- Follow the **Sequential Subagent Pipeline**.
- **Builder Agent:** Update `prompts.py` schema, adjust `orchestrator.py` extraction logic, and rewrite the `extreme_enrichers.py` math.
- **Reviewer Agent:** Ensure the LLM system prompt explicitly bans raw markdown blocks for the extreme thesis.
- **Verifier Agent:** Run a test extreme scan and verify the JSON output strictly matches the new schema and iOS can parse it.
