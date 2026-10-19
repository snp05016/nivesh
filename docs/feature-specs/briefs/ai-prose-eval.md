# Feature package ai-prose-eval: Offline prose eval harness for the research formatter

Cluster: ai (AI cost architecture and research surfaces); area: backend
Features covered: 50. I13 Offline eval harness

## Files (create or modify)
- backend/scripts/research_prose_eval.py
- backend/tests/test_research_prose_eval.py
- docs/research/RUNBOOK.md

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:be-prose, ENG:be-db-ledger, ENG:docs-research, FIX:LLM-25, FIX:LLM-02, FIX:TEST-13. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
New backend/scripts/research_prose_eval.py. Use the stdlib plus existing backend modules, and add the backend directory to sys.path as scripts/populate_stock_universe.py does.

freeze(session, n: int) -> list[dict]
- D = max(ResearchReportRow.as_of_date) where origin == 'nightly'; with none, return [].
- Take the nightly rows for D, sorted by hashlib.sha1(symbol.encode()).hexdigest(), and keep the first n (1 <= n <= 50).
- Each item is {'symbol', 'report': row.report_json, 'known_symbols': sorted list, 'company_names': list}, using research_repo.known_symbols_and_names(session, exclude_symbol=row.symbol).
- Report JSON only: nightly rows carry no user ids.

run_eval(payloads, *, max_calls: int, generate) -> tuple[dict, list[dict]]
- remaining = max_calls. For each payload while remaining > 0: narrative, attempts, failures = generate(p['report'], known_symbols=set(p['known_symbols']), company_names=p['company_names'], allow_llm=True, calls_remaining=remaining); then remaining -= max(attempts, 0).
- Summary keys:
  - label (set by the caller);
  - n_evaluated, llm_validated, template;
  - first_pass_rate: share with attempts == 1 and status 'llm_validated';
  - validated_rate, template_rate, mean_attempts;
  - failure_codes: collections.Counter of f['code'] over all failures;
  - calls_used;
  - model: services.llm_utils.DEEPSEEK_MODEL;
  - prompt_version and validator_version from the narrative dict, defaulting to 'rf-1' and 'gv-1'.
- Each sample is {'symbol', 'status', 'attempts', 'failure_codes', 'narrative'}. It holds validated or template text only; rejected raw text is never available or written.

main(argv) -> int (argparse subcommands)
- No arguments: print usage and return 2.
- freeze --n 20 --out PATH: opens get_session() and writes JSONL.
- run --in PATH --max-calls 40 --label NAME [--out PATH] --yes.
  - Returns 2 unless --yes is given, DEEPSEEK_API_KEY is set, 1 <= max-calls <= 200, and the input has at least one payload.
  - Before calling, prints 'This makes up to {max_calls} paid DeepSeek calls (about ${max_calls*0.0009:.2f} at the spec 7.8 estimate; verify current pricing).'
  - If services.llm_budget.bind exists (FIX:LLM-02), call bind(None, 'prose_eval') first so the ledger attributes the calls.
  - generate = services.research.formatter.generate_narrative. Its calls go through llm_utils, so FIX:LLM-02's breaker and ledger apply.
  - Prints the summary as indented JSON, and writes samples to --out when given.
- Writes no research_* rows; provider calls are recorded in llm_usage by FIX:LLM-02. No scheduling, no LLM-as-judge, never run in CI.

docs/research/RUNBOOK.md: add section '10. Offline prose eval (before any prompt or model change)'.
- Freeze 20 payloads once per quarter to ~/nivesh-data/prose_eval/payloads-YYYYQn.jsonl.
- Run a baseline with the current env.
- Run the candidate with NIVESH_DEEPSEEK_MODEL=<candidate> (FIX:LLM-25), or on the branch that changes rf-1.
- Adopt only if all hold: the candidate validated_rate is at least 0.90 and at least baseline minus 0.02; template_rate rises by no more than 2 points; 20 rendered samples pass human review.
- Paste both summaries into the PR.

Tests, backend/tests/test_research_prose_eval.py
Import the script with importlib.util.spec_from_file_location. Use a stub generate that returns scripted (narrative, attempts, failures).
(a) Three payloads: (llm_validated, 1, []), (llm_validated, 2, [literal_number]), (template, 2, [ADVICE, literal_number]). Expect first_pass_rate 1/3, validated_rate 2/3, failure_codes {'literal_number': 2, 'ADVICE': 1}, calls_used 5.
(b) max_calls 2 stops after the second payload.
(c) main(['run', ...]) without --yes returns 2, and the stub is never called.
(d) --max-calls 201 returns 2.
(e) a missing DEEPSEEK_API_KEY returns 2.
(f) freeze over SQLite, with two nightly rows on the latest date and one older row, returns 2 items in deterministic order whose keys are exactly symbol, report, known_symbols, company_names.
(g) main([]) returns a non-zero code and prints 'usage' (capsys).

## Acceptance checks
1. PYPARSE and PYRIGHT are clean.
2. The tests pass in CI without network access (TEST-13 guard) and without calling a real LLM.
3. RUNBOOK section 10 exists with the adoption thresholds.
4. Test (g) covers the no-arguments usage exit.

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
