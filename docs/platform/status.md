---
title: Status & continuation plan
description: Current status of the Research Lab and the plan for continuing the work.
---

# Status & continuation plan

<p class="nv-lede">State of the <code>feat/research-platform</code> branch as of 2026-10-19. Each item says how it
was verified. Nothing has been pushed or merged yet, and the <code>research_lab</code> flag defaults to off.</p>

## Current status

| Area | State | How it was verified |
|---|---|---|
| Time Machine simulator (`ml-engine/lab/sim.py`) | <span class="nv-pill real">done</span> | Unit and journey tests; no-lookahead gate (`PITView`) under test |
| Effective-dated Indian charges (`costs.py`, `india_charges.json`) | <span class="nv-pill real">done</span> | Test resolves every day from 2010 to today against the real schedule. Some old rows are marked UNVERIFIED |
| Trade autopsy, counterfactuals, behaviour flags (`autopsy.py`) | <span class="nv-pill real">done</span> | Unit and journey tests |
| Statistics toolkit (`stats.py`) | <span class="nv-pill real">done</span> | Unit tests against known values and simulated nulls |
| Feature language (`featurelang.py`) | <span class="nv-pill real">done</span> | Tests include truncation parity (no feature value changes when future rows are removed) |
| Hypothesis Lab (`hypothesis.py`) and template run | <span class="nv-pill real">done</span> | Tests, plus a recorded run in [Experiments](experiments/index.md) |
| Event reconstruction (`events.py`) | <span class="nv-pill real">done</span> | Tests |
| Trader School (`school/`) | <span class="nv-pill real">done</span> | Tests (44 lessons, 49 concepts, BKT) |
| Probabilistic forecasts (`forecast.py`) | <span class="nv-pill real">done</span> | Tests and a recorded dev run in [Forecasts](experiments/forecasts.md) |
| ml-engine `/lab/v1` API | <span class="nv-pill real">done</span> | `tests/lab/test_api.py` |
| Backend `/api/v1/research-lab` (sessions, school, research ledger, mentor) | <span class="nv-pill planned">written, not run</span> | Static checks (`py_compile`, `ruff`), every import resolved to a real symbol, a single Alembic head, a clean merge into `audit/integration`, and a line-by-line desk-check that traced all 17 tests in `tests/test_research_lab.py` to a pass. Backend tests must not run locally (AGENTS.md §6.5), so CI still has to run them |
| iOS Lab screens | <span class="nv-pill real">verified</span> | Every screen driven in the simulator against a local dev gateway that mirrors the backend contract (see below) |
| Documentation (this site) | <span class="nv-pill real">done</span> | `mkdocs build --strict` |

**ml-engine Lab tests: 127 passing.** These are pure, deterministic tests on synthetic data (`tests/lab/synth.py`).

### Research results so far

These results come from the **dev dataset**, which is survivorship-biased and pre-adjusted. They show how the
Lab behaves, not findings about the market.

- Of the 7 published-anomaly templates, 6 are `not supported` and Amihud illiquidity is `fragile`.
  The skeptic panel marks survivorship as a critical data-quality failure, so nothing can reach `supported` on this data.
- Forecasts show a small distributional skill (better calibrated intervals than climatology) and **no directional skill**.
  An earlier claim in the repo of a 52.66% hit rate was **not reproduced**.
- The feature compiler is fast enough in Python. A Rust or C++ backend is not needed.

### iOS verification

The app was run in the iPhone 17 Pro simulator with the DEBUG-only `-LabDevURL` launch argument. That argument
points the Lab client at a throwaway gateway. The gateway is not committed: it serves the same
`/api/v1/research-lab` shapes in memory and calls the real ml-engine Lab in-process. This tests decoding and the
UI end to end. It does **not** test the real backend (auth, database, flags).

Driving every screen found these bugs, all now fixed:

| Bug | Cause | Fix |
|---|---|---|
| Lab tiles did nothing | The hub was pushed with a view-destination link, so its `LabRoute` destinations never registered | `LabRoute.hub` value route, `LabRoute` registered at the Markets stack root |
| Starting IL&FS (and 4 other scenarios) failed with 422 | Hinted stocks missing from the dataset (e.g. delisted DHFL) | `/scenarios` filters the universe, returns `missing_symbols`, needs two stocks to be playable |
| Watchlist 1d/20d and all "knowable at entry" stats were blank | `.convertFromSnakeCase` turns `chg_1d` into `chg1D`, not `chg1d` | Explicit `CodingKeys`. A script checked all 345 response keys against the Swift models; no other mismatch |
| The thesis "test" counted as a written reason | Check only tested for non-empty text | Thesis needs two or more words |
| Mentor listed failed checks by their pass condition ("The position was not held through its stop") | Rules answer printed the check text | Prefixed with "Not met:" |
| Mentor send button hidden under the app-wide AI button | The AI button floats over every screen | Composer insets its trailing edge |
| Keyboard could not be dismissed in Event Explorer | No focus handling | Lab screens dismiss on scroll; "Reconstruct" drops focus |
| Unplayable scenarios listed first; raw reason codes in Trader School | — | Playable first; reason codes mapped to plain copy |

## Ownership

| Owner | Scope |
|---|---|
| This branch (`feat/research-platform`) | `ml-engine/lab/**`, `ml-engine/tests/lab/**`, `backend/routers/research_lab.py`, `backend/services/research_lab/**`, the three `Lab*` models and migration `8f3c2a7d9e15`, `ios/.../Views/Lab/**`, `NetworkManager+Lab.swift`, `mkdocs.yml`, `docs/platform/**`, `docs/research/**` |
| Parallel session (`audit-fixes` and feature packages) | Everything else, including the backend circular import it was told about. This branch does not touch those files |

## Blocked or needs a person

1. **Legal review.** NSE's data usage policy (§7.4) restricts simulation use, and the SEBI rule for educational
   use sets a 30-day lag on price data. The Lab enforces `LAB_MIN_DATA_AGE_DAYS` (default 30). The flag stays off
   until counsel signs off. See [Data: legal position](data.md#legal-position).
2. **Backend test run.** Push the branch and let CI run `backend/tests/test_research_lab.py` and the Alembic
   migration chain (`5c2e9b7d41af` → `8f3c2a7d9e15`).
3. **Curated bhavcopy panel.** Older scenarios (2008–2016) and any `supported` verdict need the survivorship-free
   panel in the market data store. 9 of the 14 scenarios are playable on the dev data.

## Continuation plan

In order:

1. Push `feat/research-platform` and open a PR against the integration branch. Fix whatever the backend CI finds.
2. Get the legal review. Record the outcome on [Data](data.md#legal-position), then turn on `research_lab` for internal users only.
3. Ingest NSE bhavcopy and corporate actions into the store, then re-run `python -m lab.run_templates --source store`
   and the forecast run. Replace the dev-data results on the experiments pages.
4. Add delivery volume, sector labels and earnings data to the panel. The Hypothesis Lab translator already
   reports these as missing.
5. Calibrate spreads and the impact coefficient from real trade data, replacing the liquidity-bucket assumptions.
6. Run a TestFlight pass of the Lab screens against the staging backend, not the dev gateway.

## Limitations

See [Limitations](limitations.md). Update that page in the same change that fixes any item on it.
