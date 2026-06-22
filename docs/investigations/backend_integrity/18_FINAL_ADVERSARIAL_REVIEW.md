# Report 18 — Final Adversarial Review

**Date:** 2026-06-16

---

## Review Scope

Phase 2 changes: `routers/alerts.py` (B-003 fix), 6 verification scripts, 4 test suites, 5 reports.

## Challenges & Responses

**Q: Is `asyncio.to_thread()` safe when `_yf_price` uses a global requests session?**  
A: `yfinance` creates per-call sessions. `_yf_price` takes a ticker string and returns a tuple — no shared mutable state. Thread-safe.

**Q: Do the new tests create real DB files that could pollute CI?**  
A: Migration tests use `tmp_path` pytest fixture (auto-cleaned). Smoke/API tests use `sqlite:///:memory:`. No persistent files created.

**Q: Does the `api_client` fixture bypass auth and give false confidence?**  
A: `raise_server_exceptions=False` means 500s return as responses, not exceptions. Tests explicitly assert `!= 500`. Auth-protected routes are tested for absence of 500, not for auth bypass.

**Q: Could the `verify_raw_sql_columns.py` script produce false negatives?**  
A: Yes — it's heuristic (regex-based), not AST-based. It exits 0 always (informational only) and is documented as such. Not a correctness gate.

**Q: The `check_backend_health.sh` script uses `$VIRTUAL_ENV/bin/python` — what if venv isn't activated?**  
A: The script falls back to `python3` and prints a warning. It sources the venv if found at `./venv/bin/activate`.

## Verdict

No architectural violations introduced. No new security surface. Pre-existing failures are pre-existing and documented.
