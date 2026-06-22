# Feature Blueprint: Options Strategy Builder & Payoff Visualizer

## 1. Feature Overview
**Goal:** Build an institutional-grade, drag-and-drop interactive tool for constructing multi-leg options strategies (Iron Condors, Straddles, Spreads, etc.).
**Core Functionality:** Calculate maximum profit, maximum loss, breakeven points, and dynamically plot a P&L payoff graph against the underlying asset's price.
**Utility:** Allows traders to visually assess risk/reward before executing complex derivatives trades without relying on external third-party apps like Sensibull or Opstra.

---

## 2. Architectural Guardrails (Strict Compliance Required)

### 2.1 The Prime Directives (AGENTS.md)
You must strictly adhere to the guidelines set in `AGENTS.md` and `ARCHITECTURE.md`.
- **Zero Magic Strings:** All strings must be typed or mapped in a single dictionary source of truth.
- **Explicit over Implicit:** All formulas for Options Greeks (Delta, Gamma, Theta, Vega) and payoff calculations must be explicit.
- **Indian Numbering System:** All currency outputs must use the Lakhs/Crores format (`IndianFormatter`). "Million/Billion" is strictly forbidden.

### 2.2 Subagent-Driven Development
Because this is a mathematically and visually complex feature, you **MUST** deploy a team of agents sequentially:
1. **The Builder Agent:** Focus strictly on the core implementation (Backend math, Frontend UI components).
2. **The Reviewer Agent:** Validate code quality, Banknote Aesthetic compliance, correct Indian numbering, and verify the math formulas.
3. **The Verifier/Tester Agent:** Ensure the system boots properly, the endpoints connect, and no views crash due to malformed chart geometry.

---

## 3. Backend Requirements (FastAPI)

### 3.1 Controller-Service-Repository Paradigm
- **Router (`routers/options_strategy.py`):** Handle HTTP validation and routing. No business logic here.
- **Service (`services/options_engine.py`):** Contain the complex Black-Scholes calculations, payoff generation, and P&L curve array building.

### 3.2 Core Mathematical Engine
The service layer must calculate:
1. **Payoff Vector:** An array of `(underlying_price, profit_loss)` tuples covering a 20% range above and below the current spot price.
2. **Key Metrics:** 
   - `Max Profit` (can be infinite or capped).
   - `Max Loss` (can be infinite or capped).
   - `Breakeven Points` (array of prices where P&L crosses zero).
   - `Net Premium` (credit received or debit paid).
   - `Probability of Profit (POP)` (optional, based on standard deviation if applicable).

### 3.3 Endpoints
- `POST /api/v1/options/payoff`: Accepts a JSON payload of an array of "Legs" (Type: Call/Put, Position: Long/Short, Strike, Premium, Expiry). Returns the computed Payoff Vector and Key Metrics.

---

## 4. Frontend Requirements (SwiftUI)

### 4.1 The Banknote Aesthetic
All UI elements must use the established `Theme.*` tokens.
- **Colors:** No raw hex codes or `.green`/`.red`. Use `Theme.bullGreen`, `Theme.bearRed`, `Theme.inkPrimary`, `Theme.canvasDeep`.
- **Typography:** Use `Theme.serialNumberFont` for strike prices and premiums. Use `Theme.engravedSerif` for standard text.
- **Containers:** All strategy cards must use the `.banknoteCard()` modifier.
- **Separators:** Use `GuillocheDivider()`.

### 4.2 Interactive Payoff Chart
- Implement a `Chart` (using Swift Charts) that plots the Payoff Vector.
- The X-Axis represents the underlying stock price.
- The Y-Axis represents Profit/Loss (₹).
- **Critical Visuals:** Shade the area under the curve GREEN (`Theme.bullGreen`) when above zero, and RED (`Theme.bearRed`) when below zero.
- Include a vertical dotted line indicating the current Spot Price.

### 4.3 Drag-and-Drop / Interactive Leg Builder
- Users must be able to dynamically add or remove "Legs" to their strategy.
- Each Leg row must show: 
  - Buy/Sell toggle.
  - Call/Put toggle.
  - Stepper for Strike Price.
  - Current Premium.
- Changes to any leg must trigger an immediate state update and refresh the Payoff Chart.
- Every interactive tap MUST trigger haptic feedback using `HapticManager.selection()`.

---

## 5. Execution Steps

1. **Review Context:** Read `AGENTS.md` and `BACKEND_IOS_CONTRACT.md`.
2. **Backend Engine:** Create the `options_engine.py` to handle Black-Scholes and Payoff arrays. Create the `options_strategy.py` router. Register in `main.py`.
3. **Frontend Views:** Create `OptionsStrategyScreen.swift`. Build the Leg builder UI. Build the dynamic Swift Chart.
4. **Integration:** Connect the Swift UI to the FastAPI backend using a new function in `NetworkManager.swift`.
5. **Review & Test:** Spawn your Reviewer and Verifier agents to ensure the feature works flawlessly.
