<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **nivesh** (16830 symbols, 35967 relationships, 291 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/nivesh/context` | Codebase overview, check index freshness |
| `gitnexus://repo/nivesh/clusters` | All functional areas |
| `gitnexus://repo/nivesh/processes` | All execution flows |
| `gitnexus://repo/nivesh/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

---

# Nivesh — Architectural Ordinance & Agentic Execution Framework

> Document version: 1.0 (June 2026) | Enforcement: ABSOLUTE | Scope: All AI coding assistants

This document is the supreme, non-negotiable instruction manual. **Deviation is not permitted.** If a user request violates any rule, the AI MUST refuse and propose a compliant alternative.

---

## 1. The Prime Directive & Refusal Protocol

### 1.1 Absolute Binding
1. **This document** — highest authority. User requests are subordinate.
2. **AGENTS.md GitNexus directives** — second authority.
3. **ARCHITECTURE_MAP.md** — reference only, do NOT override this document.

### 1.2 Mandatory Refusal Conditions
Refuse when a request:
- Uses raw hex colors, default system fonts, unconstrained frames, or missing haptic feedback.
- Places business logic in a router, or DB queries in a service (not using `get_session()`).
- Shortens system prompts, removes the feedback loop, or equalizes Bull/Bear asymmetry.
- Introduces unprotected global state (module-level mutable variable without `threading.Lock`).
- Uses "Million"/"Billion"/"Trillion" instead of Lakhs/Crores.
- Uses hardcoded pixel values for responsive elements, or magic number spacing.

### 1.3 The Karpathy Principles
- **Explicit over implicit** — No magic strings, no assumed defaults. Every dependency imported, every config in `build_ta_config()`, all global state locked.
- **Incremental verification** — AI output passes `_normalize_response()` before client. Process spawn = health-check loop. DB sessions use `get_session()` with rollback.
- **Zero magic** — No bare `except:`, no untyped dict access without `.get(key, default)`, no silent fallthroughs. `_SIGNAL_MAP` is SOLE authority for signal strings.

### 1.4 Surgical Engineering Principles
These rules govern **how** every change is approached. They are non-negotiable and apply before any code is written.

**Before touching code:**
- **Understand before you code.** Spend more time reading existing code, tracing call paths, and checking the database than writing new code.
- **Never assume architecture.** Always verify the actual structure from the repository before concluding how something works.
- **Never assume database behavior.** Read the ORM models, active Alembic migrations, and run schema checks — never infer what columns exist.
- **Never assume API contracts.** Inspect the actual Pydantic models, router decorators, and live OpenAPI spec before forming opinions about request/response shapes.
- **Prefer repository evidence over inference.** If you cannot find explicit proof in the code or docs, say so — do not fill the gap with guesses.
- **Document reasoning before implementation.** Write out *why* a change is needed and *which files* are in scope before making any edit.

**When modifying code:**
- **Follow existing repository patterns exactly.** Adopt the same naming conventions, error-handling patterns, and abstraction layers already in use.
- **Reuse abstractions before creating new ones.** Check whether a helper, service, or utility already exists before writing a new one.
- **Minimize architectural drift.** Do not introduce new patterns, dependencies, or structural layers unless the user explicitly requests them.
- **Avoid duplicate logic.** If the same logic exists elsewhere, call or import it — do not copy-paste.
- **Keep changes scoped to the task.** Only modify files directly required by the stated task. Do not "clean up" unrelated code in the same commit.

### 1.5 Sequential Subagent Pipeline (Subagent-Driven Development)
When executing complex tasks, you MUST deploy a team of specialized subagents working sequentially to maintain context hygiene:
1. **The Builder Agent:** Focuses strictly on writing the core implementation (e.g., backend logic, SwiftUI views).
2. **The Reviewer Agent:** A separate subagent spawned specifically to perform a rigorous code quality review. It checks for architectural compliance, Banknote Aesthetic usage, correct Indian numbering, and zero magic strings.
3. **The Verifier/Tester Agent:** Ensures the system actually runs locally without missing modules, syntax errors, or circular imports.
Do not attempt to write, review, and verify massive features in a single context window. Divide and conquer.


---

## 2. Pillar I: Frontend Guardrails (SwiftUI & Banknote Aesthetic)

### 2.1 Color & Theming — No Raw Values
Every color MUST be a `Theme.*` token. `.blue`, `.red`, `.green`, `.primary`, `.secondary` FORBIDDEN (except as opacity bases like `.primary.opacity(0.88)`). Raw hex codes FORBIDDEN.

**Tokens:** `Theme.canvas` | `Theme.canvasDeep` | `Theme.canvasShadow` | `Theme.inkPrimary` | `Theme.inkSecondary` | `Theme.inkTertiary` | `Theme.securityGold` | `Theme.securityGoldLight` | `Theme.bullGreen` | `Theme.bullGreenLight` | `Theme.bearRed` | `Theme.bearRedLight` | `Theme.holdAmber` | `Theme.signalEmerald`(=bullGreen) | `Theme.signalRuby`(=bearRed) | `Theme.borderFine` | `Theme.borderSage`

### 2.2 Spatial Geometry — Relative Sizing Only
Full-width elements: `.frame(maxWidth: .infinity).padding(.horizontal, Theme.screenPadding)`. Hardcoded pixel widths FORBIDDEN (exception: avatars, ornamentations, YouTubeCompactCard max 240pt).

**Spacing tokens (multiples of 4pt, base 8pt):** `Theme.Spacing.xSmall`(2) | `.small`(4) | `.tight`(6) | `.medium`(8) | `.standard`(12) | `.card`(16) | `.screen`(20) | `.large`(24) | `.xLarge`(32). Use `Theme.screenPadding`(20pt) for horizontal margins, `Theme.sectionSpacing`(32pt) for major sections. ALWAYS use spacing tokens in VStack/HStack/LazyVGrid/LazyHGrid. Arbitrary values (7,9,13,14,18pt) FORBIDDEN.

**Corner radius:** `Theme.CornerRadius.small`(4) | `.tight`(6) | `.medium`(8) | `.large`(12) | `.card`(16)

### 2.3 Component Anatomy & Haptics
- Every card: `.banknoteCard()` modifier.
- Every interactive element: `.buttonStyle(EKPressStyle())` (or `.ekPress()`) + `HapticManager.selection()`.
- Section separators: ONLY `GuillocheDivider()`. Plain `Divider()` FORBIDDEN.

**Haptics:** `HapticManager.selection()` | `.soft()` | `.light()` | `.rigid()` | `.heavy()` | `.impact(.medium)` | `.success()` | `.warning()` | `.error()`

### 2.4 Typography — No Default System Fonts
No `.font(.system(size:...))`. Use Theme font methods or semantic fonts with `.monospaced()`/`.fontDesign(.serif)`.

- **Serif body:** `Theme.engravedSerif(size:weight:relativeTo:)` (Georgia)
- **Numbers:** `Theme.serialNumberFont(size:relativeTo:)` (monospaced)
- **Labels:** `Theme.officialStampFont(size:relativeTo:)` + `.tracking(1.5)` (condensed medium)
- **Hindi:** `Theme.hindiFont(size:relativeTo:)` (italic Georgia)
- **Badges:** `Theme.labelStyle` (caption, bold, small caps)

### 2.5 The 8pt Grid & Responsive Sizing
| If you need... | Use... | Not... |
|----------------|--------|--------|
| Full-width element | `.frame(maxWidth:.infinity).padding(.horizontal,Theme.screenPadding)` | `.frame(width:350)` |
| Card in horizontal scroll | `.frame(width: UIScreen.main.bounds.width * 0.62)` | `.frame(width:240)` |
| Grid of cards | `LazyVGrid` with `GridItem(.flexible())` | `GridItem(.fixed(N))` |
| Table column width | `colW * proportion` where `colW = screenWidth - 2*Theme.screenPadding` | `GeometryReader` |
| Section separator | `GuillocheDivider().padding(.horizontal,Theme.screenPadding)` | `Divider()` |
| Card spacing | `VStack(spacing:Theme.Spacing.card)` | `VStack(spacing:12)` |
| Screen margin | `Theme.screenPadding`(20pt) | `16` or `24` |

**GeometryReader prohibition:** NEVER inside ScrollView/HStack (causes sibling overlap). Use `UIScreen.main.bounds.width * proportion`. Only permitted for decorative ornamentation (watermarks, guilloche).

### 2.6 Component Hierarchy — Unidirectional Data Flow
- Data flows DOWN: Parent→Child via `let` or `@Binding`.
- Events flow UP: Child→Parent via closures (`onTap:() -> Void`, `onSelect:(Ticker) -> Void`).
- `@Environment` for cross-cutting concerns ONLY (AuthManager). Max depth: 5 levels.
- Children must NOT access parent's ViewModel. ViewModels must NOT be passed 4+ levels deep.

### 2.7 View Taxonomy (condensed)
**Core layouts:** Dashboard (ScrollView+VStack), List (LazyVStack), Table (VStack with .banknoteCard()), Grid (LazyVGrid .flexible), Detail (single-entity deep dive), Empty/Loading/Error states, Bottom Sheet (.sheet), Modal (NavigationStack+DenominationBackground), Tab View

**Financial views:** Portfolio (HeroNote+RiskCard+ChartsCarousel), Holdings (HoldingNoteRow with aligned columns), Transactions (monospaced table), Market Overview (MarketPulseDashCard+IndexChip), Screener (filter chips+table), Order Book (monospaced ladder)

**Analytics charts:** MUST use Theme.bullGreen/bearRed, label axes (₹,%,Cr,L). Max heights: thumbnail 30% screen height, full 55%. NO 3D, <6 pie slices, radial gauges. Prefer bar (comparison), line (trends), scatter (correlation).

### 2.8 The 10 Commandments of Financial UI
1. **Data Density** — Information over decoration. <3 actionable data points = wasteful.
2. **Accessibility** — Dynamic Type (`relativeTo:`), 44×44pt targets, VoiceOver, 4.5:1 contrast, respect ReduceMotion.
3. **Performance** — Skeleton <100ms, data <2000ms. Lazy-load, cache. No network in `body`/`init`.
4. **Forms** — Validate on keystroke. Preserve data across errors. `.numberPad`/`.decimalPad`. Inline errors.
5. **Navigation** — `NavigationStack` with `.navigationDestination(for:)`. Max 3 levels deep. NEVER nest NavigationStacks.
6. **Charts** — Labeled axes, consistent scales, annotation highlights. No 3D or dual-axis without legends.
7. **Consistency** — Every Button=EKPressStyle, every value=IndianFormatter, every section=GuillocheDivider, every card=.banknoteCard().
8. **Feedback** — Every tap=haptic. Every async=loading indicator. Every success=confirmation. Every error=specific+actionable.
9. **Mobile** — Critical actions bottom 60%. Swipe gestures. Proportional sizing (SE→Pro Max).
10. **Apple HIG** — SF Symbols for icons. Respect safe areas. Native controls over custom. Banknote Aesthetic is a SKIN, not replacement.

### 2.9 UI Refusal Templates
```
REFUSED — AGENTS.md §2.2: Responsive Sizing
.frame(width: 350) forbidden. Use: .frame(maxWidth: .infinity).padding(.horizontal, Theme.screenPadding)

REFUSED — AGENTS.md §2.2: 8pt Grid
.padding(14) violates 8pt grid. Use: Theme.Spacing.standard(12pt) or .card(16pt)

REFUSED — AGENTS.md §2.2: GeometryReader
GeometryReader in ScrollView/HStack forbidden. Use: UIScreen.main.bounds.width * proportion

REFUSED — AGENTS.md §2.1: Raw hex colors
Color(hex:"#FF5733") forbidden. Use: Theme.bearRed or add adaptive token to Theme.swift

REFUSED — AGENTS.md §2.3: Missing haptic
Add: .buttonStyle(EKPressStyle()) + HapticManager.selection() in action closure

REFUSED — AGENTS.md §2.6: Component nesting
ViewModel passed 4+ levels deep. Pass only required @Binding properties or closures.

REFUSED — AGENTS.md §2.8 Cmd I: Data Density
<3 actionable data points. Add P&L%, sector weight, or comparison metrics.
```

---

## 3. Pillar II: Backend Architecture (FastAPI & Decoupling)

### 3.1 Controller-Service-Repository
| Layer | Location | Responsibility |
|-------|----------|---------------|
| Controller | `routers/` (9 files) | HTTP validation, rate limiting, spawn `multiprocessing.Process` |
| Service | `services/` (20 files) | All business logic, LLM orchestration, computations |
| Repository | `database.py` + `models/db_models.py` + `repositories/` | `get_session()` context manager. ORM models centralized in one file. Alembic migrations in `migrations/versions/`. |

Business logic in routers FORBIDDEN. DB queries in services FORBIDDEN.

### 3.2 Database Sessions
Every DB interaction MUST use `get_session()` context manager. NEVER pass sessions across process boundaries. NEVER use global `session` variable.

### 3.3 Multiprocessing Integrity
Heavy AI analysis MUST use `multiprocessing.Process` with `multiprocessing.Queue` (pattern: `routers/analysis.py:488-577`). Worker MUST re-import deps + `load_dotenv(override=True)` inside subprocess. NEVER share unpicklable objects across processes. On disconnect: `p.terminate()` to save credits.

### 3.4 Global State
Any module-level mutable variable MUST have a dedicated `threading.Lock`. Use with-lock access pattern + explicit release/deletion path. Current locked state: `_running_analyses: set[int]`, per-user semaphores.

### 3.5 Database Migrations (Alembic) — MANDATORY

**Every schema change to ORM models MUST go through Alembic. Never use `Base.metadata.create_all()` for schema changes — it only creates NEW tables, never modifies existing ones.**

When you add, remove, or modify a column in `models/db_models.py`:
```bash
cd backend
../venv/bin/alembic revision --autogenerate -m "describe the change"
../venv/bin/alembic upgrade head
```

Key rules:
- **Generate BEFORE deploying** — the migration file must be committed alongside the model change.
- **`alembic check` before commit** — verifies no schema drift between models and DB.
- **Never manually ALTER TABLE** — all schema changes go through migration files in `migrations/versions/`.
- **SQLite `render_as_batch=True`** — already configured in `migrations/env.py`; batch mode handles SQLite's lack of ALTER support.
- **JSON columns use `default="{}"`** (string, not Python dict) — SQLite requires constant defaults.
- **`datetime.utcnow` forbidden in models** — use `default=lambda: datetime.now(timezone.utc)` (evaluated at row-insert time, not import time).
- **All ORM models live in `models/db_models.py` ONLY** — never define a second `class Foo(Base)` in a service file. Centralizing prevents `Table already defined` errors.

Schema change checklist:
1. Edit `models/db_models.py`
2. `alembic revision --autogenerate -m "description"`
3. Review the generated migration file
4. `alembic upgrade head` (local) or `alembic stamp head` (server if DB already matches)
5. Commit both the model change AND the migration file

---

## 4. Pillar III: AI Pipeline & Cost Engineering (LangGraph)

### 4.1 Smart Cache Gate
NEVER bypass `services/staleness.py:compute_staleness()`. 
| Score | Urgency | Action |
|-------|---------|--------|
| 0-19 | FRESH | Return cached. No AI run. |
| 20-44 | AGING | Optional: DeepSeek Flash only. |
| 45-69 | STALE | Full refresh: DeepSeek agents. |
| 70-100 | URGENT | Full multi-agent: DeepSeek + Claude Haiku/Sonnet. |

**Tiers:** Tier 1 = `deepseek-chat` ($0.00014/1K input) for 8 bulk agents. Tier 2 = `claude-haiku-4-5-20251001` for synthesis (Research/Portfolio Manager). Claude Sonnet = ONLY final reformatting.

### 4.2 Dialectical Asymmetry
Bear researcher prompt MUST be longer than Bull's. Bear has more data signals (management quality, promoter pledging, FII/DII, governance). `max_debate_rounds`=1, `max_risk_discuss_rounds`=1. Portfolio Manager weights Bear findings 1.5x Bull.

### 4.3 Prompt Integrity
`INDIAN_MARKET_SYSTEM_PROMPT` in `backend/prompts.py` is NON-NEGOTIABLE. NEVER shorten, truncate, or remove any of the 8 analysis priorities or 20+ JSON output fields. NEVER change the tone directive.

### 4.4 LLM Config
```python
HAIKU_MODEL = "claude-haiku-4-5-20251001"   # Tier 2 synthesis
SONNET_MODEL = "claude-3-5-sonnet-latest"    # Final reformatter
DEEPSEEK_MODEL = "deepseek-chat"             # Tier 1 bulk agents
```
Use `build_ta_config()` to override — NEVER modify `DEFAULT_CONFIG` directly.

---

## 5. Pillar IV: Data Formats & Financial Formatting

### 5.1 Indian Numbering — Absolute Mandate
All user-facing numbers MUST use Lakhs/Crores. "Million"/"Billion"/"Trillion" FORBIDDEN.

**iOS:** `IndianFormatter.price()` / `.percent()` / `.priceCompact()` / `.formatLakhsCrores()` / `.delta()` / `.elapsed()`
**Backend:** `format_indian_currency()`, `_ban_western_scale()` (raises ValueError on Western scales).

Thresholds: <1,00,000 = Indian commas | >=1,00,000 = X.XX Lakhs | >=1,00,00,000 = X.XX Crores

### 5.2 Response Normalization
Every LLM output MUST pass through `_extract_json_from_text()` → `json.loads()` → `_normalize_response()` → `_ban_western_scale()`. After normalization, all 20+ fields are guaranteed with correct types (signal=string enum, confidence_pct=int 0-100, target_prices/upside_downside_pct=dict, bull/bear_case/key_risks=non-empty arrays, etc.)

### 5.3 Emoji Stripping
All AI-generated text MUST pass through `stripEmoji()`. Applies to: Morning Brief, news headlines, portfolio insights, analysis descriptions, any AI text field.

---

## 6. Enforcement & Review

### 6.1 Pre-Commit Verification
1. Run `gitnexus_detect_changes()`.
2. Scan diff for raw hex colors, hardcoded spacing, `.system(size:...)` fonts, missing `Theme.*` tokens.
3. If router files modified: verify no business logic (no yfinance, no LLM client, no `session.query()`).
4. Scan diff for "Million"/"Billion"/"Trillion".
5. If `backend/prompts.py` modified: verify prompt not shortened/tone altered.
6. If `models/db_models.py` modified: verify `alembic revision --autogenerate` was run, migration file is committed, and `alembic check` passes.

### 6.2 Xcode Build Prohibition
**NEVER run `xcodebuild` or attempt to compile the iOS app.** The Swift/Xcode project in `ios/StockApp/` is reference-only. Compiling will crash the agent session. Skip any workflow step that would trigger `xcodebuild`.

### 6.3 Refusal Protocol
```
I cannot proceed because it violates [SPECIFIC RULE in AGENTS.md].
Violation: [description]
Non-compliant: [snippet]
Compliant alternative: [snippet]
Architectural impact: [what breaks]
```

```
REFUSED — AGENTS.md §3.5: Database Migrations
Direct ALTER TABLE or manual column addition forbidden.
Use: alembic revision --autogenerate -m "description" → alembic upgrade head
```

```
REFUSED — AGENTS.md §3.5: ORM Model Duplication
Defining class Foo(Base) in a service file forbidden.
All ORM models MUST live in models/db_models.py only.
```

### 6.4 Commit Workflow
Commit after EVERY small task or phase. Incremental, reviewable checkpoints.

**When:** After each discrete task (e.g. "added search bar" → commit, "added results list" → commit), each phase (frontend done, backend done, integration done), and after the final task.

**Format:** Conventional commits — `type(scope): description` (e.g. `feat(ios): add voice search to SearchScreen`, `fix(backend): screener rate limiting`)

**Types:** `feat` (new feature), `fix` (bug fix), `chore` (refactor/deps/config), `docs` (documentation/help/guides), `style` (UI polish/theming), `perf` (performance)

**Scopes:** `ios`, `backend`, `copilot`, `earnings`, `correlation`, `stress-test`, `nl-screener`, `anomalies`, `sector-rotation`, `settings`, `home`, `portfolio`, `markets`, `analysis`

**Pre-commit:** Run `gitnexus_detect_changes()`, review `git status` + `git diff --stat`, NO secrets/.env/binary assets, NO xcodebuild artifacts.

**Merging:** NEVER run `git merge` or merge any branch into `main` unless the user explicitly gives you permission. Also make sure that if you are in a branch `x` that is not `main`, anything committed should be committed to that branch only and should not be merged to `main`.

### 6.5 Deployment & Remote Verification
After committing and pushing your code, you MUST deploy and verify on the remote server by executing commands non-interactively. NEVER open an interactive SSH session.
**Anything to be tested in the backend should be done on the server using (`saumyapatel@192.168.1.122`). No backend Python files and tests will be ran in the local computer. All testing, checking for bugs by running the files will be done on the server (`saumyapatel@192.168.1.122`).**

**After EVERY backend change and git pull, you MUST:**
1. Kill all stale server processes to prevent zombie workers from consuming server CPU:
   ```bash
   ssh saumyapatel@192.168.1.122 "pkill -f 'uvicorn' || true; pkill -f 'python.*main' || true; sleep 2"
   ```
2. Pull latest code remotely: `ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && git pull"`
3. Restart the backend server (in background):
   ```bash
   ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && nohup ../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 &"
   ```
4. Run tests remotely: `ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && pytest"` (or relevant verification command)

**NEVER skip the kill step.** Stale uvicorn/Python processes run indefinitely in the background and waste server CPU. Always kill before restart.

---

## 6.6 SwiftUI Stack Overflow Prevention (CRITICAL)

When a SwiftUI view calls multiple inline `@ViewBuilder` functions (e.g., `func someSection() -> some View`), SwiftUI inlines the entire nested view tree into one massive type signature on the call stack. This causes `chkstk_darwin` / `EXC_BAD_ACCESS` crashes with the same address across every VStack/HStack/ZStack in the view.

### Rules (NON-NEGOTIABLE)

1. **NEVER use inline `func -> some View` for sections larger than 5 lines.** Convert to separate `View` structs. Each struct creates a boundary with its own stack frame.

2. **Inside `ScrollView`, prefer `LazyVStack` over `VStack`** — LazyVStack only builds visible children, reducing initial stack depth.

3. **If the same `EXC_BAD_ACCESS` address appears across multiple stacks**, the `@Published` model object is being deallocated mid-render. Copy to `@State` and sync via `.onReceive(publisher) { ... }`.

4. **`DenominationBackground` + `BanknoteWatermark` inside ZStack can corrupt view tree.** If crashes occur, fall back to `Theme.canvas.ignoresSafeArea()`.

5. **Files with >1000 lines** — extract independent sections into `Views/FeatureName/` subfolder structs.

### Fix Template
```swift
// BEFORE (crashes)
private func extremeChartSections(_ a: A) -> some View {
    Group { ... 100+ lines ... }
}

// AFTER (safe)
struct ExtremeChartSections: View {
    let analysis: StockAnalysis
    var body: some View { Group { ... } }
}
```

### Refusal Template
```
REFUSED — AGENTS.md §6.6: Inline view function too large
Convert `func {name}() -> some View` to `struct {Name}: View`.
Inline functions >5 lines cause chkstk_darwin stack overflow.
```

---

## 7. Glossary

**Banknote Aesthetic:** UI mimicking physical currency — aged-paper backgrounds, security gold accents, double-border cards, serif typography (Georgia), haptic feedback, GuillocheDivider separators.

**Controller-Service-Repository:** Routers=HTTP validation+process spawn. Services=business logic+LLM. Repository=DB via `get_session()`.

**Dialectical Asymmetry:** Bear researcher 1.5x weight advantage. Bear's prompt longer with more data signals. Burden of proof on Bull.

**GuillocheDivider:** Sinusoidal wave pattern (Theme.swift:206-231). SOLE authorized section separator.

**Smart Cache Gate:** `services/staleness.py` computes staleness (0-100) before triggering multi-agent run.

**Response Normalization:** Pipeline: extract JSON → parse → `_normalize_response()` → `_ban_western_scale()`. Guarantees all required fields exist with correct types.

**EKPressStyle:** ButtonStyle (BanknoteDesignSystem.swift:5-18) — 0.97 scale + 0.88 opacity spring animation. All interactive elements MUST use it.

**chkstk_darwin Crash:** SwiftUI stack overflow from inline `-> some View` functions. Same `EXC_BAD_ACCESS` address appears in every VStack/HStack/ZStack. Fix: convert to separate View structs (§6.6).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
