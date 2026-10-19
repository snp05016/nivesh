# Feature package ai-copilot-be: Copilot v2: computed portfolio answers, history scrub, advice backstop, reply provenance, reply fixtures

Cluster: ai (AI cost architecture and research surfaces); area: backend
Features covered: 51. I24 Copilot fix, 50. I13 Offline eval harness, 10. I01 Paid-AI guard

## Files (create or modify)
- backend/routers/copilot.py
- backend/services/copilot_service.py
- backend/services/advisory_guard.py
- backend/tests/test_copilot_v2.py
- backend/tests/fixtures/copilot_replies.json
- backend/tests/test_ai_consent_gate.py
- backend/tests/test_copilot_service.py
- backend/tests/feature_tests/ai_orchestration/test_copilot_service.py
- backend/tests/test_llm_budget.py

## Dependencies
- Feature packages (integrated before you start): ai-allowance-be
- Declared in the plan: ai-allowance-be, FIX:LLM-02, FIX:LLM-13, FIX:DB-20, FIX:REL-24, FIX:REL-22, FIX:FINSEC-04, FIX:REG-02, FIX:LLM-21, FIX:ARCH-03, FIX:TEST-13, ENG:be-cutover. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Build after the Copilot fix items. Several have already landed in the worktree: FINSEC-04's consent gate and tests, REL-24's shares and holdings filter, and UX-28 on iOS. The rest: FIX:LLM-13 (sync route, payload caps, fixed system prompt, no per-turn summary), FIX:DB-20, FIX:REL-22 + ENG:be-cutover (DEEP_ANALYSIS returns a fixed sentence plus nivesh://analyze/{SYMBOL}), FIX:REG-02 (creates services/advisory_guard.py with NON_ADVISORY_RULES), FIX:LLM-02 (require_llm_budget, guard) and ai-allowance-be (Retry-After, AI_PAUSED), which also edits routers/copilot.py.

1. routers/copilot.py
- CopilotResponse gains `reply_source: Literal['ai', 'computed'] = 'ai'` (additive; shipped builds ignore it).
- The chat route takes `user_id: int = Depends(require_auth)` (core.security) instead of `Depends(require_llm_budget('copilot'))`. First statement of the handler: `if not copilot_service.is_portfolio_question(req.user_message): llm_budget.guard(user_id, 'copilot')`. guard() binds the ledger context and raises 429 AI_QUOTA_EXCEEDED or 503 AI_PAUSED (with Retry-After) before any LLM call. Portfolio questions skip it because they make no LLM call, so they work when the allowance is used up or AI is paused. No token still gives 401.

2. services/copilot_service.py
a. Imports: `from services.yfinance_client import _yf_price, _to_ns`; `from helpers import format_indian_currency, _ban_western_scale`; `from services import advisory_guard`; `from repositories.research_repo import normalize_symbol`; `from concurrent.futures import ThreadPoolExecutor, wait`; `from decimal import Decimal`.
b. Constants and helper:
- COMPUTED_REPLY_FOOTER = 'These figures are computed from your Nivesh holdings using the latest available prices. They are not investment advice.'
- _PORTFOLIO_RE = re.compile(r'\bmy\s+(?:portfolio|holdings|investments)\b', re.IGNORECASE)
- def is_portfolio_question(msg: str) -> bool: return bool(_PORTFOLIO_RE.search(msg or '')). It needs 'my', so 'What is a portfolio?' still goes to the intent router.
c. _scrub_history(history: list[dict]) -> list[dict]: return a new list without every assistant entry whose content contains COMPUTED_REPLY_FOOTER, and without the user entry immediately before each removed one; other entries keep their order. Call it as the first statement of process_copilot_request, before managed history or any LLM message list is built; GENERAL, DEEP_ANALYSIS without a ticker and the western-scale retry all read the scrubbed list. Put this comment above it: 'FINSEC-04 invariant: DB holdings reach an LLM only with ai_processing consent. No Copilot branch puts holdings or a computed reply in a prompt; a branch that ever does must call kyc_consent_service.has_active_consent first.' Old app builds send computed replies back in history, so this server-side scrub is what protects them.
d. Routing: if is_portfolio_question(user_message), take the computed path with no intent call. Otherwise run the existing intent call; intent PORTFOLIO also takes the computed path.
e. Computed path (replaces the whole PORTFOLIO body: FINSEC-04's consent check, the DB-20/REL-24 holdings prompt and the claude_haiku call): reply = portfolio_summary_reply(user_id); reply_source = 'computed'; context_cards = None. No LLM call.
f. portfolio_summary_reply(user_id: int, *, price_fn=None, max_priced: int = 50, budget_s: float = 10.0) -> str
Reading:
- inside `with get_session()`, read Portfolio rows with user_id, group_name == 'holdings' and is_virtual false; copy (ticker, shares, buy_price) tuples and leave the session before any network call;
- aggregate by normalize_symbol(ticker), because Portfolio stores one row per lot as 'TCS' or 'TCS.NS': shares = sum of shares, invested = sum of Decimal(str(shares)) * Decimal(str(buy_price)); drop symbols whose summed shares <= 0; n = number of distinct symbols;
- n == 0 returns "You have no holdings in Nivesh yet. Add one from the Portfolio tab to see a summary here."
Pricing:
- sort symbols by invested, descending; price the first max_priced with price_fn (default `lambda s: _yf_price(_to_ns(s))[0]`, the Portfolio tab's source) through ThreadPoolExecutor(max_workers=min(n, 10)); wait(futures, timeout=budget_s); then executor.shutdown(wait=False, cancel_futures=True);
- unfinished futures, exceptions, None and values <= 0 count as unpriced; symbols beyond max_priced are unpriced.
Maths (Decimal, as in routers/portfolio.portfolio_endpoint): invested_all over all symbols; over priced symbols invested_p, value_p = sum of shares * price, change = value_p - invested_p, pct = change / invested_p * 100 (skip pct when invested_p == 0); weights by value among priced symbols; the top 3 as 'SYMBOL w.w%'.
Sentences, skipping any whose inputs are missing. Money uses format_indian_currency on absolute values; the sign is '+' or U+2212 and is omitted when the change is 0; percentages have one decimal.
- 'You hold {n} stocks.' ('You hold 1 stock.' when n == 1)
- 'Amount invested: {invested_all}.'
- 'Current value of the {k} with a price: {value_p}, against {invested_p} invested, a change of {sign}{abs change} ({sign}{abs pct}%).'
- 'Largest by current value: {A}, {B}, {C}.'
- when m > 0 symbols are unpriced: 'Prices were unavailable for {m} holding{s} ({first three symbols}, … if more), so they are left out of the value figures.'
- always last: COMPUTED_REPLY_FOOTER.
g. Normaliser: a computed reply gets strip_emoji, then _ban_western_scale inside try/except ValueError that logs and keeps the reply. A computed reply is never sent to an LLM (no rewrite retry). An 'ai' reply keeps the existing path (strip_emoji, then _ban_western_scale with its retry over the scrubbed history), then the advice backstop: if advisory_guard.find_advice(reply) is non-empty, logger.info('copilot advice guard matched %s', ids) with pattern ids only, never the text, and reply = advisory_guard.ADVICE_REFUSAL_TEXT.
h. Return {'reply', 'context_cards', 'reply_source'}.

3. services/advisory_guard.py additions
ADVICE_REFUSAL_TEXT = "I can't give buy, sell or hold views, price targets or stop-loss levels. I can explain how something works, summarise your holdings, or open a stock's page in Nivesh."
Copy this block verbatim. It was checked against all 33 fixtures plus 11 extra sentences, and Python 3.11 supports the scoped (?-i:...) groups that keep ticker and name matching case-sensitive:
_ACT = r"(?:buy|sell|hold|accumulat|exit|book|add|averag|switch|invest|trim|enter)\w*"
_START = r"(?:^\s*(?:[-*•]\s*|\d+[.)]\s+)?|(?<=[.!?])\s+)"
ADVICE_PATTERNS = {
    "first_person_advice": r"\b(?:i|we)(?:['’]d|\s+would)?\s+(?:strongly\s+)?(?:recommend|suggest|advise)\s+(?:you\s+)?(?:to\s+)?" + _ACT,
    "my_recommendation": r"\bmy\s+(?:recommendation|advice|suggestion)\s+(?:is|would\s+be)\s+to\s+" + _ACT,
    "you_should_act": r"\byou\s+(?:should|must|ought\s+to|might\s+want\s+to|may\s+want\s+to|could\s+consider)\s+(?:consider\s+)?" + _ACT,
    "consider_acting": r"\b(?:consider|try)\s+(?:buy|sell|accumulat|exit|book)\w*",
    "act_now": r"\b(?:buy|sell|accumulate|exit)\s+(?:now|today|immediately|on\s+dips|at\s+(?:₹|rs\.?|inr)?\s?\d)",
    "imperative": _START + r"(?:buy|sell|accumulate|avoid|exit|book\s+profits?(?:\s+(?:in|on))?)\s+(?:it|this|that|these|those|now|today|here|immediately|the\s+stock)\b|" + _START + r"(?:buy|sell|accumulate|avoid|exit|book\s+profits?\s+(?:in|on))\s+(?-i:[A-Z][A-Z0-9&.\-]{1,19}\b|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    "level_with_number": r"\b(?:target\s+price|price\s+target|stop[\s-]?loss|entry\s+(?:price|level))\s*(?:of|at|is|:|near|around)?\s*(?:₹|rs\.?|inr)?\s?\d",
    "hype_terms": r"\b(?:strong\s+(?:buy|sell)|top\s+pick|multi-?bagger|sure[\s-]?shot)\b",
    "guaranteed_returns": _START + r"(?![^.!?]*\b(?:no|not|never|nothing|cannot|can't)\b)[^.!?]*?\b(?:guaranteed|risk[\s-]?free)\s+(?:returns?|profits?|gains?)\b",
    "good_buy": r"\b(?:is|looks|seems)\s+(?:like\s+)?(?:a\s+)?(?:good|great|bad|strong|solid)\s+(?:buy|sell|bet|investment)\b",
    "worth_acting": r"\bworth\s+(?:buying|holding|selling|accumulating|adding)\b",
    "timing": r"\b(?:good|right|best|bad|ideal)\s+time\s+to\s+(?:buy|sell|invest|enter|exit|book)\b",
    "view_terms": r"\b(?:bullish|bearish)\s+on\s+(?-i:[A-Z])",
    "hinglish": r"\b(?:kharid|khareed|bech)\s*(?:lo|do|lijiye|dijiye)\b",
}
_COMPILED = {k: re.compile(v, re.IGNORECASE | re.MULTILINE) for k, v in ADVICE_PATTERNS.items()}
def find_advice(text: str) -> list[str]: return [k for k, rx in _COMPILED.items() if rx.search(text)]
Notes: guaranteed_returns is exempt when its sentence contains a negation, so 'No mutual fund offers guaranteed returns.' passes. imperative fires only at a sentence or bullet start, and only before a ticker, a capitalised name, or words such as 'it', 'this', 'now' and 'today'; so 'Exit load is ...', 'Sell orders are ...', 'buyback' and 'selling pressure' pass. level_with_number still blocks an explanation that quotes a stop-loss price (accepted as conservative).

4. backend/tests/fixtures/copilot_replies.json: a list of {id, text, expect} with exactly these 33 entries.
Block (expect 'block'):
b01 "You should buy Reliance now before results."
b02 "I would recommend accumulating HDFC Bank on dips."
b03 "Set a stop loss at 1450 and a target price of ₹1,700."
b04 "This is a multibagger in the making."
b05 "TCS looks like a good buy at these levels."
b06 "Buy now while it is cheap."
b07 "You might want to consider selling Infosys."
b08 "We suggest booking profits in metal stocks."
b09 "This fund gives guaranteed returns of 12%."
b10 "Analysts call it a strong buy."
b11 "Now is a good time to invest in PSU banks."
b12 "ITC is worth holding for the long term."
b13 "I'd recommend buying TCS for the long term."
b14 "Consider buying TCS before the results."
b15 "Buy TCS."
b16 "Avoid Yes Bank for now."
b17 "We are bullish on HDFC Bank."
b18 "Abhi kharid lo, price aur badhega."
b19 "My recommendation is to buy Infosys."
Pass (expect 'pass'):
p01 "Exit load is a fee some mutual funds charge when you redeem units before a set period."
p02 "A call option gives the buyer the right, but not the obligation, to buy the underlying at the strike price before expiry."
p03 "A stop-loss order becomes a market or limit order once the trigger price is reached."
p04 "Target maturity funds hold bonds that mature around a fixed date."
p05 "A buyback is when a company purchases its own shares from existing shareholders."
p06 "Selling pressure means more shares are being offered than buyers want at current prices."
p07 "Promoters hold 52% of the company's shares."
p08 "You can buy mutual fund units through a SIP or as a lump sum."
p09 "The Nifty 50 is an index of 50 large companies listed on the NSE."
p10 "SEBI-registered investment advisers must disclose conflicts of interest."
p11 "The RBI's inflation target is 4%, with a band of 2% to 6%."
p12 "Holding period decides whether a capital gain is short-term or long-term."
p13 "No mutual fund offers guaranteed returns."
p14 "A stop-loss order is an instruction to sell if the price falls to a level you choose."

5. Tests, backend/tests/test_copilot_v2.py (hermetic; monkeypatch copilot_service.deepseek_chat with a scripted side_effect and copilot_service.claude_haiku with a Mock; pass price_fn or monkeypatch copilot_service._yf_price and _to_ns):
(a) 'How is my portfolio doing?' with holdings TCS (5 @ 3500) and INFY (10 @ 1500), a watchlist row for WIPRO, and prices 4000 and 1400: the reply contains 'You hold 2 stocks', '₹32,500', '₹34,000', '+₹1,500', '(+4.6%)' and 'TCS 58.8%'; it does not contain 'WIPRO'; deepseek_chat and claude_haiku are not called; reply_source is 'computed'; the reply ends with COMPUTED_REPLY_FOOTER.
(b) two lots 'TCS.NS' (3 @ 3400) and 'TCS' (2 @ 3650) priced at 4000: 'You hold 1 stock', 'Amount invested: ₹17,500', and the sentence 'Largest by current value: TCS 100.0%.' with TCS listed once.
(c) 'How am I doing overall?' with deepseek_chat returning 'PORTFOLIO': the computed reply, and deepseek_chat is called exactly once (the intent call).
(d) no holdings: the no-holdings sentence.
(e) one price None: 'Prices were unavailable for 1 holding' and the totals exclude it.
(f) GENERAL with the scripted reply 'You should buy RELIANCE now.': reply == ADVICE_REFUSAL_TEXT and reply_source 'ai'.
(g) parametrized over the fixture file: bool(find_advice(text)) == (expect == 'block').
(h) the computed reply passes _ban_western_scale unchanged.
(i) privacy, calling process_copilot_request directly: a GENERAL request (deepseek_chat scripted 'GENERAL', then a reply) whose conversation_history holds a user question and a computed reply ('You hold 1 stock. Amount invested: ₹17,500. Largest by current value: TCS 100.0%. ' + COMPUTED_REPLY_FOOTER): no argument of any deepseek_chat or claude_haiku call contains 'TCS', '17,500' or COMPUTED_REPLY_FOOTER. Plus a unit test of _scrub_history: it removes the computed reply and the question before it and keeps the other turns in order.
(j) route: with an LlmUsage row over the user's daily cap (LLM-02 test pattern, llm_budget._reset_cache()), POST /api/v1/copilot/chat with 'How is my portfolio doing?' returns 200 with reply_source 'computed'; 'hello' returns 429 AI_QUOTA_EXCEEDED and deepseek_chat is not called; no token returns 401.

6. Update tests that assert the old PORTFOLIO LLM path:
- test_ai_consent_gate.py::test_copilot_portfolio_intent_without_consent: now expects the computed summary with claude_haiku not called. Consent is not needed because no holdings reach an LLM.
- test_copilot_service.py::test_portfolio_intent_uses_shares: expects a computed reply with shares-based totals, the watchlist row excluded, and no claude_haiku call.
- feature_tests/ai_orchestration/test_copilot_service.py: the same change for its PORTFOLIO test.
- test_llm_budget.py (FIX:LLM-02): edit only if a Copilot 429 test posts a message that matches is_portfolio_question; change that message to 'hello'.
- Leave every DEEP_ANALYSIS test (REL-22, LLM-13, be-cutover) unchanged. Replies never contain the word 'signal'.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean on the changed Python files.
2. test_copilot_v2.py and the updated tests pass in CI; the LLM-13, REL-22, be-cutover and LLM-02 tests stay green.
3. No claude_haiku( or deepseek_chat( call inside portfolio_summary_reply or the computed path, and _scrub_history runs before the first LLM message list is built.
4. CopilotResponse has reply_source; the chat route depends on require_auth and calls llm_budget.guard only for non-portfolio messages.
5. All 33 fixtures behave as expected.
6. No migration and no new dependency.

## Cluster spec
docs/feature-specs/spec_ai.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
