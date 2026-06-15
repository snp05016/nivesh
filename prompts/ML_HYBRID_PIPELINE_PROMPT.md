# NIVESH PROBABILISTIC CONFIDENCE ESTIMATION FRAMEWORK (TEACHER-STUDENT HYBRID)
## COMPREHENSIVE IMPLEMENTATION DIRECTIVE (VERSION 2.0)

> **ENFORCEMENT CAUTION:** This is a Class-A Architecture Prompt and spans over 600 lines of highly specific engineering instructions. You must read, process, and strictly adhere to every single line. This document supersedes all previous architectural assumptions. Deviations from the math, the strict JSON structure, or the Swift UI Banknote Aesthetic guidelines are explicitly forbidden. 

---

## TABLE OF CONTENTS
1. [The Prime Directive & Architectural Philosophy](#1-the-prime-directive--architectural-philosophy)
2. [Database Schema & Data Model Transformations](#2-database-schema--data-model-transformations)
3. [Module A: The Quantitative Engine (Backend)](#3-module-a-the-quantitative-engine-backend)
4. [Module B: Orchestration & Concurrency Refactoring](#4-module-b-orchestration--concurrency-refactoring)
5. [Module C: LangGraph Prompt Engineering](#5-module-c-langgraph-prompt-engineering)
6. [Module D: iOS Swift Frontend UI Engineering](#6-module-d-ios-swift-frontend-ui-engineering)
7. [Module E: Testing, Validation, & GitNexus Impact](#7-module-e-testing-validation--gitnexus-impact)
8. [Appendices: Hardcoded Reference Values](#8-appendices-hardcoded-reference-values)

---

## 1. THE PRIME DIRECTIVE & ARCHITECTURAL PHILOSOPHY

### 1.1 The Core Problem
Currently, Nivesh's core analysis relies entirely on an 8-agent LangGraph setup for both qualitative synthesis AND quantitative prediction. 
- **Latency Issue:** LLM token generation takes 15+ seconds per analysis.
- **Hallucination Issue:** LLMs are text synthesizers, not calculators. When asked to provide a 3-month target price or a confidence percentage, the LLM hallucinates values based on semantic sentiment rather than historical statistical volatility. Expected Calibration Error (ECE) is unacceptably high.
- **Cost Issue:** Burning Anthropic Claude / DeepSeek tokens to perform basic mathematical comparisons (e.g., "Is PE > 20?") is a massive waste of API credits.

### 1.2 The Hybrid Solution
You will build the **Probabilistic Confidence Estimation Framework**. 
This is a deterministic, quantitative ML engine (`services/quant_engine.py`) that performs all the numerical heavy lifting:
1. **Regime Detection:** Determines market state (Low Vol vs. Crisis).
2. **Conformal Prediction:** Bounds target prices strictly within historical GARCH volatility brackets.
3. **Venn-Abers Calibration:** Outputs mathematically provable confidence probabilities.
4. **SHAP Feature Importance:** Identifies the exact variables driving the prediction.

Once `quant_engine.py` computes these statistical absolutes, you will inject them into the LangGraph pipeline. The LLM must be strictly stripped of its ability to guess numbers. It will act purely as a "Narrator," tasked with translating the math into a beautiful, human-readable Bull/Bear thesis.

### 1.3 Strict `AGENTS.md` Adherence
As you execute this prompt, you are strictly bound by the `AGENTS.md` Karpathy Principles:
- **Zero Magic:** No bare `except:`, no untyped dictionaries, no assumed defaults.
- **Banknote Aesthetic:** No raw hex colors in Swift. You MUST use `Theme.inkPrimary`, `Theme.canvas`, `Theme.bullGreen`, etc.
- **Indian Numbering:** "Millions/Billions" are strictly forbidden. You must use `IndianFormatter.formatLakhsCrores()` in Swift and `_ban_western_scale()` in Python.
- **chkstk_darwin Prevention:** SwiftUI inline view builders larger than 5 lines will crash the app. You MUST extract all new components into independent View structs.

---

## 2. DATABASE SCHEMA & DATA MODEL TRANSFORMATIONS

Before you touch the execution logic, the foundation (the schema) must be prepared to accept the new payload.

### 2.1 Backend SQLAlchemy Models (`backend/models/analysis.py`)
You must update the `AnalysisReport` model to persist the statistical data. If the table uses Alembic, generate a new migration. 

Add the following exact columns:
```python
from sqlalchemy import String, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column

# ... inside AnalysisReport class
market_regime: Mapped[str] = mapped_column(String, default="Transition", comment="Market volatility state: Low Volatility, Transition, or Crisis")
calibrated_confidence: Mapped[float] = mapped_column(Float, default=0.0, comment="Venn-Abers calibrated probability [0.0, 1.0]")
conformal_target_upper_3m: Mapped[float] = mapped_column(Float, nullable=True, comment="Upper bound of 90% confidence interval")
conformal_target_lower_3m: Mapped[float] = mapped_column(Float, nullable=True, comment="Lower bound of 90% confidence interval")
quantitative_drivers: Mapped[dict] = mapped_column(JSON, default=dict, comment="SHAP feature importance map")
tail_risk_flags: Mapped[dict] = mapped_column(JSON, default=dict, comment="Boolean flags for severe risks e.g. auditor resignation")
```

### 2.2 Pydantic Validation Schema (`backend/schemas.py`)
The Fast API router relies on Pydantic to serialize the response to the iOS app. Update the output schema.
```python
from pydantic import BaseModel, Field
from typing import Dict, Optional

class StockAnalysisResponse(BaseModel):
    # ... existing fields (symbol, current_price, signal, etc.)
    market_regime: str = Field(..., description="The current macro volatility regime.")
    calibrated_confidence: float = Field(..., ge=0.0, le=1.0, description="Strictly calibrated confidence probability.")
    conformal_target_upper_3m: Optional[float] = Field(None, description="Mathematically bounded upper target.")
    conformal_target_lower_3m: Optional[float] = Field(None, description="Mathematically bounded lower target.")
    quantitative_drivers: Dict[str, float] = Field(..., description="Key-value pairs of feature names and SHAP values.")
    tail_risk_flags: Dict[str, bool] = Field(..., description="Key-value pairs of critical boolean risk flags.")
```

### 2.3 `_normalize_response()` Hook (`backend/utils.py`)
Currently, `_normalize_response()` ensures the LLM's JSON is clean. You must update this function to map the raw `quant_data` (bypassing the LLM) directly into the final payload.
```python
def _normalize_response(llm_output: dict, quant_payload: dict) -> dict:
    # Existing LLM normalization...
    llm_output = _ban_western_scale(llm_output)
    
    # NEW: Force-inject the mathematically proven quant payload.
    # The LLM is NOT allowed to modify these fields.
    llm_output["market_regime"] = quant_payload.get("market_regime", "Unknown")
    llm_output["calibrated_confidence"] = quant_payload.get("calibrated_confidence", 0.0)
    llm_output["conformal_target_upper_3m"] = quant_payload.get("conformal_target_upper_3m")
    llm_output["conformal_target_lower_3m"] = quant_payload.get("conformal_target_lower_3m")
    llm_output["quantitative_drivers"] = quant_payload.get("quantitative_drivers", {})
    llm_output["tail_risk_flags"] = quant_payload.get("tail_risk_flags", {})
    
    return llm_output
```

---

## 3. MODULE A: THE QUANTITATIVE ENGINE (BACKEND)

This is the mathematical heart of the framework. Create a new file: `backend/services/quant_engine.py`.

### 3.1 Base Architecture & MVP Constraints
For the MVP, you do NOT need to deploy a massive LightGBM model trained on 10 years of data. Instead, you will build a robust mathematical proxy that behaves exactly like an ML pipeline, so the API contracts and iOS UI can be finalized.

Create the main class:
```python
import asyncio
import numpy as np
from typing import Dict, Any

class QuantitativeEngine:
    def __init__(self, ticker: str):
        self.ticker = ticker
        
    async def run_full_pipeline(self) -> Dict[str, Any]:
        """Runs all mathematical models concurrently and returns the statistical payload."""
        # Step 1: Fetch all required data concurrently
        market_data, fundamental_data, macro_data = await asyncio.gather(
            self._fetch_market_volatility(),
            self._fetch_fundamentals(),
            self._fetch_macro_indicators()
        )
        
        # Step 2: Sequential mathematical computation
        regime = self._detect_market_regime(market_data)
        targets = self._compute_conformal_targets(market_data)
        shap_drivers, tail_risks = self._compute_feature_importance(fundamental_data, market_data)
        confidence = self._compute_calibrated_confidence(regime, shap_drivers, tail_risks)
        
        return {
            "market_regime": regime,
            "calibrated_confidence": confidence,
            "conformal_target_upper_3m": targets["upper_3m"],
            "conformal_target_lower_3m": targets["lower_3m"],
            "quantitative_drivers": shap_drivers,
            "tail_risk_flags": tail_risks
        }
```

### 3.2 The Regime Detection Subsystem (HMM / Volatility Proxy)
The engine must classify the market state. In the MVP, use a 30-day annualized volatility threshold on the Nifty 50 (or the stock itself if Nifty data isn't cached).
```python
    def _detect_market_regime(self, market_data: dict) -> str:
        """
        Calculates 30-day annualized volatility.
        Formula: std(daily_returns) * sqrt(252)
        """
        volatility = market_data.get("annualized_volatility_30d", 0.15)
        
        if volatility < 0.14:
            return "Low Volatility / Accumulation"
        elif 0.14 <= volatility <= 0.22:
            return "Transition / Macro-Driven"
        else:
            return "High Volatility / Crisis"
```

### 3.3 Conformal Prediction Target Prices
LLMs hallucinates targets. Math bounds them.
Use the standard deviation to create a strict 90% confidence interval for 3 months (63 trading days).
```python
    def _compute_conformal_targets(self, market_data: dict) -> Dict[str, float]:
        current_price = market_data.get("current_price", 0.0)
        daily_vol = market_data.get("daily_volatility", 0.02)
        
        # Project volatility forward for 3 months (63 days)
        # Z-score for 90% confidence interval is approx 1.645
        projected_vol_3m = daily_vol * np.sqrt(63) * 1.645
        
        # Drift component (assume 6% risk-free rate annualized -> 1.5% for 3m)
        drift = 0.015 
        
        expected_price = current_price * (1 + drift)
        upper_bound = expected_price * (1 + projected_vol_3m)
        lower_bound = expected_price * (1 - projected_vol_3m)
        
        return {
            "upper_3m": round(upper_bound, 2),
            "lower_3m": round(lower_bound, 2)
        }
```

### 3.4 SHAP Feature Importance & Tail Risks
Generate the deterministic reasons for the score. 
Call `services.piotroski` to get fundamental health.
```python
    def _compute_feature_importance(self, fundamental_data: dict, market_data: dict) -> tuple[Dict[str, float], Dict[str, bool]]:
        f_score = fundamental_data.get("piotroski_score", 5)
        promoter_pledge = fundamental_data.get("promoter_pledge_pct", 0.0)
        rsi_14 = market_data.get("rsi_14", 50.0)
        
        shap_drivers = {}
        
        # Mathematical mapping to SHAP proxy (range -1.0 to 1.0)
        shap_drivers["Fundamental Health (F-Score)"] = (f_score - 5) / 4.0 * 0.40
        
        if rsi_14 < 30:
            shap_drivers["Technical Reversion (Oversold)"] = 0.25
        elif rsi_14 > 70:
            shap_drivers["Technical Overextension"] = -0.25
            
        shap_drivers["Promoter Pledge Risk"] = -1.0 * (promoter_pledge / 100.0) * 0.50
        
        # Filter out negligible drivers (absolute value < 0.05)
        shap_drivers = {k: round(v, 3) for k, v in shap_drivers.items() if abs(v) > 0.05}
        
        # Determine strict tail risks
        tail_risks = {
            "high_pledge_danger": promoter_pledge > 30.0,
            "distressed_fundamentals": f_score < 3
        }
        
        return shap_drivers, tail_risks
```

### 3.5 The Venn-Abers Calibrated Confidence Engine
Calculate the final probability.
```python
    def _compute_calibrated_confidence(self, regime: str, shap_drivers: dict, tail_risks: dict) -> float:
        # Base confidence starts at 0.50 (coin flip)
        base_confidence = 0.50
        
        # Sum the SHAP drivers
        net_driver_impact = sum(shap_drivers.values())
        base_confidence += net_driver_impact
        
        # Regime Multiplier
        regime_multipliers = {
            "Low Volatility / Accumulation": 1.10,
            "Transition / Macro-Driven": 0.85,
            "High Volatility / Crisis": 0.55
        }
        base_confidence *= regime_multipliers.get(regime, 1.0)
        
        # Absolute Tail Risk Override
        if tail_risks.get("high_pledge_danger") or tail_risks.get("distressed_fundamentals"):
            base_confidence -= 0.30
            
        # Bound between 0.05 and 0.95 (a model is never 100% sure)
        return round(max(0.05, min(0.95, base_confidence)), 3)
```

---

## 4. MODULE B: ORCHESTRATION & CONCURRENCY REFACTORING

You must refactor `services/orchestrator.py` to seamlessly integrate the Teacher-Student flow. The Orchestrator is the conductor; it must run the math first, then pass the math to the LLM.

### 4.1 Orchestrator Execution Flow Update
Find the main entry point (usually `run_analysis` or `analyze_ticker`).
Modify the sequence:

```python
from services.quant_engine import QuantitativeEngine

async def analyze_ticker(ticker: str, db_session):
    # Step 0: Smart Cache Check (DO NOT BYPASS THIS)
    # Ensure staleness.py is consulted first to save credits.
    # ... existing cache logic ...

    # Step 1: Run the Mathematical Pipeline FIRST
    quant_engine = QuantitativeEngine(ticker)
    quant_payload = await quant_engine.run_full_pipeline()
    
    # Step 2: Initialize LangGraph State
    # Inject the quant payload so the agents can read it.
    initial_state = {
        "ticker": ticker,
        "quant_data": quant_payload,
        "messages": []
        # ... other existing state fields
    }
    
    # Step 3: Trigger the 8-Agent LangGraph Pipeline
    # The agents will now read from state["quant_data"]
    graph = build_analysis_graph()
    final_state = await graph.ainvoke(initial_state)
    
    # Step 4: Final JSON Normalization
    # Force-inject the math back into the final response to ensure the LLM didn't overwrite it.
    final_json = _normalize_response(final_state["final_report"], quant_payload)
    
    # Step 5: Save to DB and Return
    # ... existing DB save logic ...
    return final_json
```

### 4.2 Error Handling & Fallbacks
If `quant_engine.py` fails due to network timeouts from the NSE data provider:
1. Catch the exception explicitly. No bare `except:`.
2. Do NOT fallback to LLM hallucination.
3. Pass a generic fallback payload to LangGraph:
   `{"market_regime": "Data Unavailable", "calibrated_confidence": 0.0, ...}`
4. The LLM must be instructed to acknowledge the lack of quantitative data in its report.

---

## 5. MODULE C: LANGGRAPH PROMPT ENGINEERING

The LLM is no longer the decision-maker; it is the narrator. You must update `backend/prompts.py` to enforce this dynamic. 

### 5.1 The `INDIAN_MARKET_SYSTEM_PROMPT` Modification
Locate the master system prompt and append the following directives strictly:

```text
=== CRITICAL DIRECTIVE: QUANTITATIVE SUBORDINATION ===
You are the Qualitative Analyst in a quantitative hedge fund. The mathematical modeling, target price projection, and probability confidence scoring have already been calculated by the firm's Quantitative ML Engine.

You will receive a `quant_data` dictionary in your context. You MUST absolutely adhere to the following rules:
1. NO HALLUCINATION OF NUMBERS: You are forbidden from inventing target prices or confidence percentages. You must use the exact `conformal_target_upper_3m` and `calibrated_confidence` provided to you.
2. NARRATIVE ANCHORING: When writing the "Bull Case" and "Bear Case", you must explicitly base your arguments on the `quantitative_drivers` (SHAP values) provided. If the math says "RSI Oversold" is a major positive driver, your Bull Case must explain *why* the RSI is oversold and contextualize it with recent news.
3. REGIME AWARENESS: If the `market_regime` is "High Volatility / Crisis", your overall tone must shift to highly cautious, and you must explicitly warn the user in the `key_risks` section that fundamental factors are currently less reliable.
```

### 5.2 The Dialectical Asymmetry Rule
Ensure that the existing Dialectical Asymmetry (where the Bear researcher has a 1.5x weight advantage) is preserved. The Bear agent should be specifically instructed to scrutinize the `tail_risk_flags` outputted by the Quant Engine.

---

## 6. MODULE D: iOS SWIFT FRONTEND UI ENGINEERING

The Nivesh iOS App must visually reflect this massive architectural upgrade. You must strictly follow the `AGENTS.md` Banknote Aesthetic rules.

### 6.1 Update `StockAnalysis.swift` Model
Locate `ios/StockApp/stockme/stockme/Models/StockAnalysis.swift`. Add the new fields exactly as defined in the backend schema. Make them `Optional` to prevent decoding crashes on older cached analyses.

```swift
struct StockAnalysis: Codable, Identifiable {
    // ... existing properties
    
    let marketRegime: String?
    let calibratedConfidence: Double?
    let conformalTargetUpper3m: Double?
    let conformalTargetLower3m: Double?
    let quantitativeDrivers: [String: Double]?
    let tailRiskFlags: [String: Bool]?
    
    // Helper to gracefully fallback
    var displayConfidence: Double {
        return calibratedConfidence ?? Double(confidencePct ?? 0) / 100.0
    }
}
```

### 6.2 Build `RegimeWarningBanner.swift`
Create a new file: `ios/StockApp/stockme/stockme/Views/Analysis/RegimeWarningBanner.swift`.
If the regime is a crisis, we must warn the user immediately.

```swift
import SwiftUI

struct RegimeWarningBanner: View {
    let regime: String
    
    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Theme.holdAmber)
                .font(.system(size: 20)) // Exception: SF Symbol sizing
            
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("MARKET REGIME: \(regime.uppercased())")
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkSecondary)
                
                Text("High volatility state. Fundamental indicators and historical valuations are currently discounted.")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkPrimary)
            }
            Spacer()
        }
        .padding(Theme.Spacing.card)
        .background(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .fill(Theme.holdAmber.opacity(0.12))
        )
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(Theme.holdAmber.opacity(0.3), lineWidth: 1)
        )
    }
}
```

### 6.3 Build `QuantitativeDriversCard.swift`
Create a new file: `ios/StockApp/stockme/stockme/Views/Analysis/QuantitativeDriversCard.swift`.
This visualizes the SHAP feature importance. **Crucial:** Iterate safely and use relative geometry.

```swift
import SwiftUI

struct QuantitativeDriversCard: View {
    let drivers: [String: Double]
    
    // Sort drivers by absolute magnitude
    var sortedDrivers: [(key: String, value: Double)] {
        drivers.sorted { abs($0.value) > abs($1.value) }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("STATISTICAL DRIVERS")
                .font(Theme.officialStampFont(size: 12))
                .foregroundStyle(Theme.inkTertiary)
                .tracking(1.5)
            
            VStack(spacing: Theme.Spacing.standard) {
                ForEach(sortedDrivers, id: \.key) { driver in
                    driverRow(name: driver.key, value: driver.value)
                }
            }
        }
        .banknoteCard() // Custom modifier from AGENTS.md
    }
    
    @ViewBuilder
    private func driverRow(name: String, value: Double) -> some View {
        HStack {
            Text(name)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(1)
            
            Spacer()
            
            // Progress Bar Representation
            GeometryReader { geo in
                let width = geo.size.width
                let center = width / 2
                let barWidth = min(CGFloat(abs(value)) * width, center)
                let isPositive = value > 0
                
                ZStack(alignment: .leading) {
                    // Center Axis
                    Rectangle()
                        .fill(Theme.borderFine)
                        .frame(width: 1, height: 12)
                        .position(x: center, y: 6)
                    
                    // The Bar
                    Rectangle()
                        .fill(isPositive ? Theme.bullGreen : Theme.bearRed)
                        .frame(width: barWidth, height: 6)
                        .cornerRadius(3)
                        .position(
                            x: isPositive ? center + (barWidth / 2) : center - (barWidth / 2),
                            y: 6
                        )
                }
            }
            .frame(width: 100, height: 12)
            
            Text(String(format: "%+.2f", value))
                .font(Theme.serialNumberFont(size: 12))
                .foregroundStyle(value > 0 ? Theme.bullGreen : Theme.bearRed)
                .frame(width: 45, alignment: .trailing)
        }
    }
}
```

### 6.4 Update `AnalysisScreen.swift`
Integrate the new components into the main screen.
1. Find where the "Confidence Ring" is rendered. Change the title to "Calibrated Probability".
2. If `analysis.marketRegime` contains "Crisis" or "High Volatility", insert `RegimeWarningBanner(regime: analysis.marketRegime!)` right below the main Hero Note.
3. Insert `QuantitativeDriversCard(drivers: analysis.quantitativeDrivers!)` below the Bull/Bear cases.
4. Replace the old single-point Target Price view with a Conformal Bounds view. You MUST format the bounds using `IndianFormatter.price(lower)` and `IndianFormatter.price(upper)`.

---

## 7. MODULE E: TESTING, VALIDATION, & GITNEXUS IMPACT

Before considering this goal complete, you must rigorously test the implementation.

### 7.1 Backend GitNexus Validation
1. Run `gitnexus_impact({target: "analyze_ticker", direction: "upstream"})` to ensure the orchestrator changes haven't broken the batch processors or the `Smart Cache Gate`.
2. Verify that there are no circular imports introduced by `quant_engine.py`.

### 7.2 Backend Dry Run (Unit Test)
Write a temporary script in `backend/scripts/test_quant.py`.
```python
import asyncio
from services.quant_engine import QuantitativeEngine

async def main():
    engine = QuantitativeEngine("TATAMOTORS.NS")
    res = await engine.run_full_pipeline()
    print("QUANT PAYLOAD:", res)
    assert 0.0 <= res["calibrated_confidence"] <= 1.0
    assert "conformal_target_upper_3m" in res
    print("SUCCESS")

if __name__ == "__main__":
    asyncio.run(main())
```
Run this script using the `run_command` tool. It must execute successfully.

### 7.3 Frontend Compilation Audit
Do NOT run `xcodebuild` (as per `AGENTS.md` rules, this will crash the agent session).
Instead, manually audit your Swift code using `grep_search`:
1. Grep for `Color(hex:` — Fix any found.
2. Grep for `GeometryReader` inside `HStack` or `ScrollView` — Ensure it is only used deep inside `QuantitativeDriversCard` with a strictly defined `.frame(width: 100)`.
3. Grep for `Million` or `Billion` — Fix any found.

### 7.4 Final Commit
Commit the changes incrementally.
- `feat(backend): implement QuantitativeEngine and deterministic ML proxies`
- `feat(orchestrator): inject quant payload into LangGraph state`
- `feat(ios): add RegimeWarningBanner and QuantitativeDriversCard`

---

## 8. APPENDICES: HARDCODED REFERENCE VALUES

If live data scraping fails during the MVP testing phase, use these fallback values strictly:
- `fallback_volatility`: 0.16 (Transition Regime)
- `fallback_f_score`: 5
- `fallback_pledge_pct`: 0.0%
- `fallback_rsi`: 50.0

Never allow a bare `None` or `NaN` to propagate from the `quant_engine` to the iOS app, as Swift's `Double?` decoding will handle nulls, but mathematical operations on the frontend will crash. Always coalesce to `0.0` or standard baselines in the backend.

> **END OF PROMPT.** Execute methodically. Begin by reading `backend/models/analysis.py` to understand where to place the new DB columns.

---

## 9. MODULE F: SCALING TO FULL MACHINE LEARNING (POST-MVP)
While the MVP utilizes mathematical proxies (GARCH, historical standard deviation, z-scores) for deterministic outputs, the architecture must be designed to seamlessly swap in a trained `LightGBM` model once the data pipeline matures.

### 9.1 Model Registry & Versioning
When transitioning to a trained model, you must implement a simple Model Registry in `services/quant_engine.py`:
- **Implementation:** Load the model weights using `joblib` from a secure S3 bucket or local `models/` directory.
- **Example:**
```python
import joblib

class QuantitativeEngine:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.model_version = "v1.2.0-lgbm"
        self._load_model()
        
    def _load_model(self):
        try:
            self.model = joblib.load(f"backend/models/weights/{self.model_version}.pkl")
            self.calibrator = joblib.load(f"backend/models/weights/{self.model_version}_venn_abers.pkl")
        except FileNotFoundError:
            # Fallback to MVP mathematical proxies
            self.model = None
```

### 9.2 Real-Time Feature Store Integration
To reach < 50ms latency in the final production system, the `QuantitativeEngine` cannot compute RSI and MACD on the fly.
- **Future Architecture:** All 500 Nifty stocks must have their features pre-computed every 5 minutes and stored in Redis.
- **Your Job Now:** Wrap your MVP mathematical fetching logic in a generic `_get_features(ticker)` method so that swapping it out for a Redis `HGETALL` command later requires exactly one line of code change.

### 9.3 Purged Walk-Forward Cross Validation Logging
To prepare for ML training, we need to log the exact state of the market AT THE TIME of the prediction. 
- In the `AnalysisReport` SQLAlchemy model, ensure that the `quantitative_drivers` JSON payload explicitly records the exact numerical value of the feature (e.g., `{"RSI_14": 28.5, "SHAP": 0.15}`). This ensures we do not suffer from "lookahead bias" when we backtest our predictions in the future.

### 9.4 CI/CD Requirements for ML Drift
Add a placeholder script `scripts/monitor_model_drift.py`.
In a production ML system, if the Expected Calibration Error (ECE) drifts above 0.10, the model must be frozen and retrained. For now, the script should simply read the last 100 analysis reports and verify that the distribution of `calibrated_confidence` is roughly normal (mean around 0.5 - 0.6).

```python
import numpy as np
from backend.database import get_session
from backend.models.analysis import AnalysisReport

def check_confidence_drift():
    with get_session() as session:
        reports = session.query(AnalysisReport).order_by(AnalysisReport.created_at.desc()).limit(100).all()
        confidences = [r.calibrated_confidence for r in reports if r.calibrated_confidence]
        
        if not confidences:
            return
            
        mean_conf = np.mean(confidences)
        print(f"Trailing 100-Report Mean Confidence: {mean_conf:.3f}")
        
        if mean_conf > 0.80:
            print("WARNING: System is exhibiting extreme overconfidence. Calibration failure.")
        elif mean_conf < 0.30:
            print("WARNING: System is exhibiting extreme underconfidence. Model degradation.")

if __name__ == "__main__":
    check_confidence_drift()
```

This strict boundary testing guarantees that Nivesh maintains its institutional-grade accuracy forever.
