# Feature package ai-copilot-ios: Copilot iOS: computed replies kept out of history, open-stock buttons, allowance line, quota copy, no signal chips

Cluster: ai (AI cost architecture and research surfaces); area: ios
Features covered: 10. I01 Paid-AI guard, 51. I24 Copilot fix

## Files (create or modify)
- ios/StockApp/stockme/stockme/Views/CopilotScreen.swift
- ios/StockApp/stockme/stockme/Views/CopilotSupportViews.swift
- ios/StockApp/stockme/stockme/Utilities/AIReplySupport.swift
- ios/StockApp/stockme/stockme/NetworkManager+AI.swift
- ios/StockApp/stockme/stockmeTests/AIReplySupportTests.swift

## Dependencies
- Feature packages (integrated before you start): ai-allowance-be, ai-copilot-be
- Declared in the plan: ai-copilot-be, ai-allowance-be, FIX:UX-28, FIX:IOSCORE-20, FIX:WIP-13, FIX:UX-34. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Pre-check: grep -n "var pending" ios/StockApp/stockme/stockme/Utilities/DeepLinkRoute.swift must match, which means FIX:IOSCORE-20 has landed. The worktree still has Utilities/DeepLink.swift with pendingTicker; if the grep fails, stop and report.

Current code (FIX:UX-28 has landed):
- ChatMessage has isWelcome and isError.
- CopilotScreen.historyPayload(from:) drops welcome, error and failed-question turns and keeps the last 20; send() captures history before appending.
- fetchCopilotResponse throws NetworkError.fromHTTP(status:data:endpoint:) on non-200: 401 becomes .unauthorized, others .fetchFailed(endpoint:status:body:) with a 300-character body prefix. friendlyError(_:) maps errors to copy.
- CopilotDisclaimerCaption shows 'AI-generated. Not investment advice.'
- CopilotResponse decodes reply and context_cards ([[String: AnyCodable]]), and the assistant bubble renders a bull/bear 'Signal:' chip from context_cards.

Backend contracts:
- GET /api/v1/ai/allowance returns 200 {'used_pct': Int, 'state': 'ok'|'low'|'exhausted'|'paused'}, or 404 when the flag is off.
- A 429 body contains 'AI_QUOTA_EXCEEDED'; a 503 body contains 'AI_PAUSED'.
- The chat response has an optional reply_source of 'ai' or 'computed'.
- The reply may contain nivesh://analyze/{SYMBOL}; context_cards may contain {type: 'open_analysis', ticker}.

1. New Utilities/AIReplySupport.swift (Foundation only)
enum CopilotReplyParser { static func split(reply: String, contextCards: [[String: Any]]?) -> (text: String, symbols: [String]) }
- NSRegularExpression nivesh://analyze/([^\s)\]>]+). For each match, remove the whole URL from the text, trim trailing '.,;:!?' from the captured token, then keep it only if DeepLinkRoute.from(url:) on URL(string: "nivesh://analyze/" + token) returns .stock(s); use s. The parser and the router validate the same way, so 'DROP;TABLE' is rejected as a whole instead of being cut to DROP.
- Cards whose 'type' is 'open_analysis' contribute their 'ticker' through the same validation.
- Dedupe in order; at most 3 symbols.
- Clean the text: collapse repeated spaces, trim whitespace and a trailing ':'.
enum AIErrorCopy { static func message(status: Int, body: String) -> String? }
- 429 and the body contains 'AI_QUOTA_EXCEEDED': "You've used today's AI allowance. It resets at midnight, India time."
- 503 and the body contains 'AI_PAUSED': 'AI features are paused for now. Everything else in Nivesh works.'
- other 503: 'Copilot is busy. Please retry shortly.'
- anything else: nil, so the existing copy applies (401 keeps 'Your session has expired. Please sign in again.').
Substring matching survives the 300-character body prefix.

2. New NetworkManager+AI.swift
- struct AIAllowanceDTO: Decodable, Equatable { let usedPct: Int; let state: String }, with CodingKeys used_pct and state.
- func fetchAIAllowance() async throws -> AIAllowanceDTO?: GET \(baseURL)/api/v1/ai/allowance via authRequest(url), timeoutInterval 10; 404 returns nil; other non-2xx throws NetworkError.fromHTTP(status:data:endpoint:); a decode failure throws NetworkError.decodingError.

3. New Views/CopilotSupportViews.swift
struct CopilotAllowanceLine: View { let allowance: AIAllowanceDTO }
- 'low': "Today's AI allowance: \(allowance.usedPct)% used" with SF Symbol gauge.with.dots.needle.67percent;
- 'exhausted': "Today's AI allowance is used up. It resets at midnight, India time.";
- 'paused': 'AI features are paused for now. Everything else in Nivesh works.';
- 'ok' and any other state: EmptyView;
- Theme.inkTertiary, Theme.engravedSerif(size: 11, relativeTo: .caption), accessibilityElement(children: .combine).
struct CopilotReportLinkButton: View { let symbol: String; let action: () -> Void }
- label 'Open \(symbol)' with arrow.up.right.square;
- Theme.securityGold text and a 0.5pt capsule stroke;
- minHeight 44;
- accessibilityLabel 'Open \(symbol) in Nivesh'.

4. Changes to Views/CopilotScreen.swift
- Delete the context-cards 'Signal:' chip block in the assistant bubble (the bullGreen/bearRed signal rendering).
- ChatMessage gains `let replySource: String` (default 'ai') and `let linkSymbols: [String]` (default []), added to init with those defaults.
- historyPayload(from:): also drop every message whose replySource == 'computed', and drop a user message whose next message is computed (extend the existing failed-question rule). A computed reply contains the user's holdings and must never go back to an LLM. The server scrubs these too, for older builds.
- On a reply: parsed = CopilotReplyParser.split(reply: response.reply, contextCards: response.context_cards?.map { $0.mapValues { $0.value } }); append ChatMessage(role: 'assistant', content: parsed.text, replySource: response.reply_source ?? 'ai', linkSymbols: parsed.symbols). CopilotResponse gains `let reply_source: String?` and its CodingKeys case.
- Assistant bubble: Text(stripEmoji(msg.content)), then ForEach(msg.linkSymbols, id: \.self) of CopilotReportLinkButton, whose action sets DeepLinkRouter.shared.pending = .stock(symbol) and calls dismiss().
- CopilotDisclaimerCaption takes `source: String`: 'computed' shows 'Computed from your Nivesh holdings. Not investment advice.'; otherwise 'AI-generated. Not investment advice.'
- Allowance:
  - @State private var allowance: AIAllowanceDTO?;
  - .task { await refreshAllowance() }, and call refreshAllowance() again only in send()'s failure branch (not after every reply);
  - refreshAllowance sets allowance = try? await NetworkManager.shared.fetchAIAllowance(), so any error gives nil and hides the line;
  - show CopilotAllowanceLine above the input row when allowance is non-nil;
  - the TextField and send button stay enabled in every state; a send that hits the limit shows the quota copy, and portfolio questions still work because they make no LLM call.
- friendlyError(_:): first `if case let NetworkError.fetchFailed(_, status, body) = error, let copy = AIErrorCopy.message(status: status, body: body) { return copy }`, then the existing mapping.
- Welcome copy:
  - hero subtitle: 'I can explain market terms, summarise your holdings and help you find features.';
  - Portfolio Insights subtitle: 'Ask about your holdings and overall gain or loss';
  - replace the 'Stock Analysis' row with title 'Stock pages', subtitle 'Ask about a company and open its page in Nivesh', icon doc.text.magnifyingglass, colour Theme.securityGold;
  - delete the 'Market Intel' row;
  - keep App Navigation and Market Terms.

5. Tests, stockmeTests/AIReplySupportTests.swift (@testable import stockme)
- split extracts 'nivesh://analyze/RELIANCE' and removes it from the text;
- 'nivesh://analyze/TCS.' yields TCS (trailing period trimmed);
- RELIANCE appearing in both the URL and a card is deduped;
- 'nivesh://analyze/DROP;TABLE' yields no symbol;
- at most 3 symbols are returned; 'tcs' comes back uppercased from DeepLinkRoute;
- AIErrorCopy: 429 with 'AI_QUOTA_EXCEEDED' gives the quota copy, 429 without it gives nil, 503 with 'AI_PAUSED' gives the paused copy, other 503 gives the busy copy, 500 gives nil;
- AIAllowanceDTO decodes {'used_pct': 40, 'state': 'low'};
- CopilotScreen.historyPayload(from:) drops a computed reply and the question before it, and keeps an 'ai' reply and its question.

Constraints: Theme tokens only; no GeometryReader; no new NavigationStack; view helpers longer than 5 lines are structs; stripEmoji on reply text.

## Acceptance checks
1. The pre-check grep matches (FIX:IOSCORE-20 landed).
2. swiftc -parse succeeds on the four Swift sources and the test file.
3. In CopilotScreen.swift, 'Signal:', 'bullGreen', 'bearRed' and 'Market Intel' each return 0; 'DeepLinkRouter.shared.pending' and 'replySource == "computed"' each return at least 1.
4. No GeometryReader or NavigationStack is added.
5. AIReplySupportTests run in CI (FIX:TEST-17 / ENG:ci-research).
6. Manual: a 429 shows the allowance copy; an 'Open TCS' button lands on the TCS stock hub; no allowance line appears at low usage.

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
