# FINANCIAL COPILOT — Autonomous Build for Antigravity CLI

Paste into Antigravity CLI. Do not ask questions. Build everything end-to-end.
Reuse existing infrastructure aggressively. Timebox: 6 hours.

## GOAL

Build an ambitious, context-aware "Financial Copilot" chatbot for Nivesh.
It shouldn't just be a generic LLM wrapper. It must:
1. Know what the user is currently viewing (e.g., if on the Reliance screen, prompt starts with "Ask about Reliance").
2. Run a LangGraph-based workflow on the backend, reusing the Dialectical Asymmetry (Bull vs Bear) system for stock queries.
3. Handle token limits aggressively: summarize past conversation history, only keeping the last 3 turns raw to save costs and context window limits.
4. Adhere strictly to the Banknote Aesthetic on iOS (serif fonts, haptics, `banknoteCard()`).

---

## BACKEND: Copilot Engine & Router

### FILE: `backend/routers/copilot.py`
- Expose `POST /api/v1/copilot/chat`
- Accepts: `user_message` (str), `conversation_history` (list), `current_context` (dict, e.g. `{"screen": "stock_detail", "ticker": "RELIANCE.NS"}`).
- Validate via Pydantic. Spawns `multiprocessing.Process` if deep analysis is required to protect the main thread.
- **Strictly no business logic in the router.** Pass everything to `copilot_service.py`.

### FILE: `backend/services/copilot_service.py`
- Implements a LangGraph workflow:
  1. **Intent Router**: (Uses `deepseek-chat` / Tier 1 to save cost) Determines if query is:
     - *General* (e.g. "What is PE ratio?") -> Fast response.
     - *Deep Analysis* (e.g. "Is HDFC bank a buy?") -> Trigger existing `services/analysis.py` Bull/Bear multi-agent flow.
     - *Portfolio* (e.g. "How is my portfolio doing?") -> Query DB via `get_session()`.
  2. **Token Management (Crucial)**: Auto-summarize the `conversation_history` if it exceeds 2000 tokens before passing to the next LLM. Provide the summary + last 3 messages to the model.
  3. **Response Normalizer**: Strip emojis using `stripEmoji()`, enforce Indian currency (Lakhs/Crores) via `_ban_western_scale()`.

---

## iOS: The Copilot Interface

### FILE: `ios/StockApp/stockme/stockme/Views/CopilotScreen.swift`
- **UI Architecture**: A persistent floating button that opens a `.sheet` or `.fullScreenCover` with a dynamic blurred background (`Theme.canvasShadow`).
- **Chat Bubbles**: 
  - User bubbles: `Theme.inkPrimary` text on `Theme.canvasDeep` background.
  - Copilot bubbles: `banknoteCard()` styling with `Theme.officialStampFont` for headers, `Theme.engravedSerif` for body.
- **Micro-interactions**: 
  - Typing indicator: Three bouncing dots synchronized with `HapticManager.selection()`.
  - Haptic feedback on send (`.heavy()`) and receive (`.success()`).
- **Context Chips**: Above the text input, show context chips based on where the user opened the chat (e.g. `[ Reliance Industries ]`).
- **Data Rendering**: If the backend returns structured analysis (like Bull/Bear cases), render it as rich UI cards inside the chat, not just plain text.

---

## CRITICAL RULES & CONSTRAINTS

1. **Token Limits & Cost Engineering**: Default to Tier 1 (`deepseek-chat`) for the Intent Router and summarization. Only use Tier 2 (`claude-haiku-4-5-20251001`) for final synthesis. Never use `claude-sonnet` for the chatbot unless it's an explicit, manually triggered "Deep Dive" request.
2. **Architectural Ordinance**: Do not use `xcodebuild`. All DB interactions via `get_session()`. No unprotected global state.
3. **Indian Market Constraints**: "Million/Billion" are absolutely forbidden. Always use Lakhs and Crores. Apply `IndianFormatter` for all numeric outputs.
4. **Aesthetic Enforcement**: Raw colors forbidden. Use `Theme.bullGreen`, `Theme.securityGold`, etc. Spacing must use the 8pt grid (`Theme.Spacing.card`, etc.). All interactive buttons must use `EKPressStyle()`.

---

## EXECUTION & VERIFICATION

1. **Work Until Verified**: You must continue working autonomously until the chatbot is fully functional, integrated, and completely verified. Do not stop early.
2. **Robustness**: Make the implementation test and fail-proof. Handle LLM timeouts, malformed JSON, and empty contexts gracefully without crashing.
3. **Validation Run**: You may run the chatbot backend endpoint **ONLY ONCE** locally to verify it is working. Do not spam the endpoint or run redundant tests in order to conserve LLM credits.
