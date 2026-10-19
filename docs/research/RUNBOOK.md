# Research Engine v1: operator runbook

How to deploy, backfill, validate, promote, roll out, monitor and roll back the Research Engine. Derived from the approved implementation spec (revision 2), sections 2.6-2.8, 3.9, 5 and 12.4.

Companion documents: [METHODOLOGY.md](METHODOLOGY.md) and [COMPLIANCE.md](COMPLIANCE.md).

## Conventions

- **Where commands run.** All `python -m research.*` commands run inside the ml-engine container on the home server, whose working directory is `/app` and whose data directory is `/data` (`~/nivesh-data/research` on the host):

  ```
  docker exec -it ml-engine python -m research.<module> ...
  ```

  Long jobs (`backfill`, `train`) should run under `nohup` or `tmux` on the host so an SSH drop does not kill them. Training runs with `nice -n 10` and 3 threads.
- **Never print secrets.** `ML_ENGINE_API_KEY` lives in `~/nivesh-data/ml-engine.env` (ml-engine) and `backend/.env` (backend). Check that a key is set with `grep -c '^ML_ENGINE_API_KEY=.' <file>`, never with `cat` or `echo`.
- **Admin views.** `GET /healthz` (`research` block), `GET /api/v1/research/admin/status`, `GET /api/v1/research/track-record` and `GET /api/v1/research/model-card?detail=full` (all four are admin-only).
- **Flags** live in `backend/.env` and are read by `services/research/config.py` at backend start. Restart the backend after any change and confirm the effective values in `/healthz` and `/admin/status`.

## Command reference

Every command below is defined in the implementation plan:

| Command | Purpose |
|---|---|
| `python -m research.marketdata.store backfill --start YYYY-MM-DD` | Download and curate bhavcopy history from a start date |
| `python -m research.marketdata.store load --source local_csv` | Dev only: load the local CSV and print symbol count and date range |
| `python -m research.marketdata.store events --kind ca_unverified --since YYYY-MM-DD` | List corporate-action events for OPS review |
| `python -m research.train --horizon {21,63} --source store [...]` | Walk-forward validation, null calibration, lockbox, production training |
| `python -m research.registry verify <model_id>` / `promote <model_id>` | Verify an artefact's manifest and hashes / make it active (non-zero exit on mismatch). Run with `--help` for the exact arguments |
| `python -m research.pipeline --as-of YYYY-MM-DD --source store --data-dir /data [--extra-symbols ...] [--fundamentals {fetch,skip}]` | Manual nightly run for diagnosis (the backend does not ingest it) |
| `python -m research.export_contract [--check]` | Regenerate or check the contract schema and fixtures |

---

## 1. Deploy ml-engine (Stage 0; before any mode change)

ml-engine must be deployed with the research API **before** `RESEARCH_ENGINE_MODE` is changed from off.

1. **Port check.** Confirm nothing else binds :8001 on the server (a comment in `AdvisoryModels.swift` mentions a harvester on 8001):

   ```
   ss -ltnp 'sport = :8001'
   docker ps --filter publish=8001
   ```

   Anything other than the old ml-engine container must be moved first; `scripts/deploy_ml_engine.sh` stops any container publishing 8001.
2. **Data directory, mode 700:**

   ```
   mkdir -p ~/nivesh-data/research && chmod 700 ~/nivesh-data/research
   ```
3. **Env file, mode 600.** Create it empty with the right mode, then add the two variables with an editor (never paste the key into shell history):

   ```
   install -m 600 /dev/null ~/nivesh-data/ml-engine.env
   ```

   It holds `ML_ENGINE_API_KEY` (the same value as in `backend/.env`) and `RESEARCH_HTTP_CONTACT` (a URL or address NSE can reach, used in the honest User-Agent; the downloader refuses to run without it). Check: `stat -c %a ~/nivesh-data/ml-engine.env` prints `600`.
4. **Run `scripts/deploy_ml_engine.sh`.** It builds the image and starts the container with `--user "$(id -u):$(id -g)"`, `-p 127.0.0.1:8001:8001` (loopback only), `-v ~/nivesh-data/research:/data`, `--env-file ~/nivesh-data/ml-engine.env`, `-e RESEARCH_DATA_DIR=/data -e HOME=/data`, `--cpus=3 --memory=4g` and `--restart unless-stopped`.
   - Caution: the script's process cleanup runs `pkill -f 'uvicorn'`, which also stops a backend uvicorn on the same host. Check the backend afterwards and restart it if needed.
5. **Verify:**
   - `docker port ml-engine` shows `127.0.0.1:8001`, not `0.0.0.0`.
   - `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/research/v1/ready` without the key returns 401 (503 means the key is unset in the container).
   - `/healthz` on the backend shows a `research` block with `mode: off` and the ml-engine `/ready` reasons (expected before backfill: no data, no active artefacts).
6. Confirm backups of `~/nivesh-data/research` and Postgres exist before Stage 1.

## 2. Backfill and data checks

### 2.1 Backfill

Run in a weekend window (about 4,700 sessions at 2.5 s, roughly 3.3 h; linking and adjustment run as it goes):

```
docker exec ml-engine python -m research.marketdata.store backfill --start 2008-01-01
```

If the NSE archive is shallower than 2008, shift every production date in `config.DATES` by the same offset while keeping at least 96 OOS months; that is a config change made before any OOS result is seen.

If NSE blocks the downloader, do not change the User-Agent or use proxies. Stop and move to a licensed vendor (COMPLIANCE.md section 9).

### 2.2 Entity-continuity and adjustment checks

Each of these must hold before validation starts (ISINs to be verified on the first backfill):

| Check | Expected |
|---|---|
| HDFCBANK face-value split 2019 (INE040A01026 → INE040A01034) | One continuous entity, continuous `px_idx` |
| TATASTEEL face-value split 2022 (INE081A01012 → INE081A01020) | One continuous entity |
| BAJFINANCE split plus bonus ex 2025-06-16 (INE296A01024 → INE296A01032) | One continuous entity |
| RELIANCE 1:1 bonus ex 2024-10-28 | f ≈ 0.5 ± 0.001 |
| HDFCBANK bonus, August 2025 | Reproduced as a PREVCLOSE event |
| yfinance-recorded splits and bonuses for listed names | At least 98% matched by a PREVCLOSE event within 2% |
| Same-day ISIN and symbol changes | Listed and reviewed (they start a new entity) |

The entity episodes are in `curated/entities.parquet`; inspect them with `load_entities()` and `resolve_entity()` from `research.marketdata.store`, for example:

```
docker exec ml-engine python -c "from research.marketdata.store import load_entities as L; e=L(); print(e[e.symbol.isin(['HDFCBANK','TATASTEEL','BAJFINANCE'])])"
```

### 2.3 Corporate-action review

```
docker exec ml-engine python -m research.marketdata.store events --kind ca_unverified --since 2008-01-01
```

Review every `ca_unverified` event (demergers, rights issues, large dividends, unmatched splits). The factor is always applied; classification is only a note. If a factor is genuinely wrong, add a row to `ml-engine/research/ref/adjustment_overrides.csv` (`isin, ex_date, factor, note`) through a reviewed commit and redeploy. After the first backfill, re-run the review weekly from the last review date; `/admin/status` shows the `ca_unverified` count per run.

### 2.4 Gap-fill limits

- Each nightly run fills missing sessions automatically, up to **15 calendar days** back (including weekends; a 404 means no session).
- A gap longer than 15 days (extended downtime) is not filled automatically. Run a backfill from the first missing date:

  ```
  docker exec ml-engine python -m research.marketdata.store backfill --start <first missing date>
  ```
- A run marked degraded with `gap_fill_incomplete` means an older date failed with a non-404 error; it is retried on the next run. If it persists, check the NSE archive URL for that date by hand.

## 3. Nightly operations

### 3.1 Schedule (when the effective mode is not off)

| Job | IST |
|---|---|
| `research_nightly_kick` | Mon-Fri 19:45 and 21:00; Tue-Sat 07:15 (previous weekday) |
| `research_poll_ingest` | Every 5 min, Mon-Sat, in the 06:30-09:25 and 19:30-00:25 IST windows (cron hours 1-3 and 14-18 UTC) |
| `research_score_outcomes` | Mon-Fri 22:30 |
| `research_live_metrics` | Sun 10:00 |
| `research_cleanup` | Daily 02:30 |

LLM prose is generated only between 19:30 and 00:25 IST, at most 800 calls a day.

### 3.2 Stale-run handling

- **Automatic.** Every kick first marks failed (`stale_run`) any nightly row that has been `running` for more than 3 h, or whose `run_uid` returns 404 or `failed` from ml-engine. A failed row does not block the date, so the next kick (21:00, then 07:15) starts a new run. ml-engine marks any `running` `run.json` failed at startup (`engine_restarted`).
- **409 `engine_busy`.** If a kick gets 409 for a different market date, its row is marked failed. Wait for the active run to finish; the next kick retries.
- **Holidays.** At 07:15, no bhavcopy and no `^NSEI` bar records `skipped_holiday`. Until then the holiday counts as one stale session.
- **When all three kicks fail:** check `/admin/status` and the daily error digest (`RESEARCH_ENGINE` subsystem), fix the cause, then let the next evening's kick run; gap-fill catches the prices up. Reports age honestly in the meantime (stale at 1-2 sessions, expired at 3).
- **Diagnosis only:** `research.pipeline --as-of D --source store --data-dir /data --fundamentals skip` reproduces a run in its own `runs/` folder. The backend does not ingest it; it is for reading logs and counts.
- **Never** edit `research_runs` or `research_predictions` rows by hand.

## 4. Validation (once per procedure version)

### 4.1 Null calibration

```
docker exec ml-engine nice -n 10 python -m research.train --horizon 21 --source store --null-calibration 20
```

Writes to `TRIALS_DEV.jsonl` only. **Pass:** at most 2 of 20 permutations reach `weak_evidence` and none reaches `validated_edge`. If it fails, the pipeline leaks; stop and investigate before any real walk-forward.

### 4.2 Walk-forward

```
docker exec ml-engine nice -n 10 python -m research.train --horizon 21 --source store
docker exec ml-engine nice -n 10 python -m research.train --horizon 63 --source store
```

2-4 h per horizon. Each run appends one trial to `models/TRIALS.jsonl` (deduplicated) and writes `validation.json`, `validation.md` and `gate_result.json`. Read `validation.md`: PASSED appears only for gates that passed. Expected outcome: `no_reliable_edge` at 63 and `weak_evidence` or `no_reliable_edge` at 21. A poor result is a valid result; do not tune and re-run (every re-run with a changed config is a new trial and raises the DSR bar).

### 4.3 Freeze and lockbox (second reviewer)

1. **Freeze.** Record `config_sha256` and `git_sha` from `validation.json`. No config change after this point without a new procedure version.
2. **Second reviewer.** A second person (sign-off is by the owner plus a second reviewer) independently confirms that `config_sha256` in `validation.json` matches the code at the frozen `git_sha`, and that `LOCKBOX_LOG.jsonl` has no entry for this procedure and horizon.
3. **Open the lockbox once per horizon,** with the reviewer present:

   ```
   docker exec ml-engine nice -n 10 python -m research.train --horizon 21 --source store --open-lockbox --confirm-config-sha <config_sha256>
   docker exec ml-engine nice -n 10 python -m research.train --horizon 63 --source store --open-lockbox --confirm-config-sha <config_sha256>
   ```

   `train` refuses without the confirmation and refuses a second opening. Each opening appends to `LOCKBOX_LOG.jsonl`. The lockbox is recorded as spent (`lockbox_spent: true`); G6 is informative and G7 (live) is binding.

### 4.4 Commit the validation files

Copy from `~/nivesh-data/research/models/` on the host into the repository and commit through a reviewed PR:

```
docs/research/validation/TRIALS.jsonl
docs/research/validation/LOCKBOX_LOG.jsonl
docs/research/validation/rg-lgbm-v1/h21/validation.json   validation.md
docs/research/validation/rg-lgbm-v1/h63/validation.json   validation.md
```

The PR description names the second reviewer. These files are admin evidence; nothing from them is shown to users.

## 5. Production train and promote

```
docker exec ml-engine nice -n 10 python -m research.train --horizon 21 --source store --train-production
docker exec ml-engine nice -n 10 python -m research.train --horizon 63 --source store --train-production
docker exec ml-engine python -m research.registry verify <model_id>
docker exec ml-engine python -m research.registry promote <model_id>
```

- `--train-production` writes the boosters (5 seeds), `calibrator.json` and `manifest.json` under `models/<model_id>/`.
- `verify` checks file sha256s, features, objective, params and `config_sha256`; it exits non-zero on any mismatch. Never promote an artefact that fails verify.
- `promote` updates `models/registry.json`. Fast artefacts (from `--fast`) are refused unless `--allow-fast`, which is for dev only and must never be used on the server.
- After promoting, `GET /research/v1/ready` (with the key) returns 200 with both active models, and `/healthz` shows no `manifest_invalid` reason.
- Check the contract on the deployed commit: `docker exec ml-engine python -m research.export_contract --check` exits 0.

## 6. Rollout

| Stage | Flags | Exit criteria |
|---|---|---|
| 0 Prerequisites | — | Wave-1 auth and quota fixes merged; backups; ml-engine deployed (section 1); backfill checked (section 2); artefacts promoted (section 5) |
| 1 Shadow | `RESEARCH_ENGINE_MODE=shadow` | **10 consecutive ok nights**; validator first-pass rate ≥ 90%; GET p95 < 200 ms; **50 prose samples with 0 violations** (manual review against COMPLIANCE.md) |
| 2 iOS release | Mode still shadow | New build live with `ResearchReportView`, legacy containment and paywall copy; 0 decode errors in TestFlight. Non-admins see "Stock report not available yet", so keep this window short |
| 3 On | `RESEARCH_ENGINE_MODE=on` **and** `RESEARCH_LEGACY_RETIRED=true` | 5xx < 0.5%; weekly prose sample clean |
| 4 Cleanup | — | See section 9 |

**Order is fixed:** iOS release first, then legal's confirmation of the NSE end-of-day data licence (or a licensed vendor), then mode on together with `RESEARCH_LEGACY_RETIRED=true`. Do not set mode on without the licence confirmation in writing. `RESEARCH_LEGACY_RETIRED` is **never unset** once set, so the old LLM pipeline never comes back.

In shadow the API is admin-only and the old pipeline is unchanged. Use shadow to read reports for a sample of symbols on device and to sample prose weekly.

## 7. Rollback and kill-switch

### 7.1 Rollback

- **Hide outlooks or stop serving:** set `RESEARCH_ENGINE_MODE=shadow` (admin-only) or keep `RESEARCH_OUTLOOK_DISPLAY=tier_only`, then restart the backend.
- **Never unset `RESEARCH_LEGACY_RETIRED`.** Legacy routes keep returning 410; there is nothing to roll back to.
- **Stop LLM prose only:** `RESEARCH_LLM_PROSE=false`; reports render template prose.
- **Bad artefact:** `research.registry verify` the previous `model_id`, then `research.registry promote` it. Ledger rows keep their original `model_id`.
- **Bad ml-engine release:** redeploy the previous commit with `scripts/deploy_ml_engine.sh`; `/data` is on the volume and survives.
- Invalid research config fails closed by itself (effective mode off, reasons in `/healthz`); the rest of the backend is unaffected.

### 7.2 Kill-switch (A1)

- Automatic: the weekly live-metrics job sets a horizon `under_review` when the rolling 12-month mean IC is below 0 at 6 consecutive month-ends (evaluated only once 12 independent periods exist). That horizon is then served as `no_reliable_edge` (`live_under_review`).
- `calibrator_drift` and `psi_warning` are admin warnings only; review them in `/track-record` but they change nothing.
- **Reinstatement** only through a new procedure version validated from section 4 and promoted by hand. Never clear `under_review` manually.

## 8. Retention, refits and housekeeping

### 8.1 Retention

- `research_cleanup` (daily 02:30 IST) runs `prune_reports(today)`: deletes on-demand and off-universe reports older than 30 days and universe reports older than 400 days. Predictions survive with `report_id` NULL.
- ml-engine deletes `runs/*` folders older than 7 days at the start of each run.
- Raw bhavcopy zips, `MANIFEST.jsonl`, `TRIALS*.jsonl`, `LOCKBOX_LOG.jsonl` and model artefacts are kept indefinitely; include `~/nivesh-data/research` in backups.
- Legacy `analysis_history` and `analysis_predictions` tables are archived as they are.

### 8.2 Quarterly refit

Once a quarter, retrain the production artefacts with the **frozen** recipe (section 5: `--train-production`, then `verify`). Promotion is always manual, never automatic; compare the new `validation.json` with the committed one before promoting. Any change to `research/config.py` is a new procedure version and restarts section 4.

### 8.3 Weekly checks

- 50-sample prose audit against COMPLIANCE.md (validator blind spot: mis-attribution within a section).
- `ca_unverified` review (section 2.3).
- `/admin/status`: template rate (alert above 20% over 7 days), LLM calls, live states, warnings.

## 9. Stage 4 trigger (cleanup)

Stage 4 deletes `tradingagents-core`, the TradingAgents path, `quant_engine.py`, `confidence_fusion.py` and the dead `/analyze` code (ARCH-23). Start it at the earlier of:

- 90 days after Stage 3, or
- when, in the backend access logs, 410 responses on legacy paths (`/analyze*`, `POST /batch`, `/daily-action/*`) fall below **5% of research GETs** (`GET /api/v1/research/stocks/*`) for 30 consecutive days.

Compute the ratio per day from the access logs; the `X-Nivesh-Client` header sent by new builds separates new-build traffic from old builds. Record the 30-day series in the Stage 4 PR.

## 10. Offline prose eval (before any prompt or model change)

Run this before switching the DeepSeek model (`NIVESH_DEEPSEEK_MODEL`) or editing the `rf-1` prompt. It replays frozen report payloads through the formatter and prints deterministic metrics; there is no LLM judge and no `research_*` rows are written. Paid runs are owner-only and never run in CI.

1. Freeze 20 payloads once per quarter: `cd backend && python scripts/research_prose_eval.py freeze --n 20 --out ~/nivesh-data/prose_eval/payloads-YYYYQn.jsonl`.
2. Run a baseline with the current environment: `python scripts/research_prose_eval.py run --in <payloads> --max-calls 40 --label baseline --out baseline-samples.jsonl --yes`.
3. Run the candidate with `NIVESH_DEEPSEEK_MODEL=<candidate>`, or on the branch that changes `rf-1`, using the same payloads and a different `--label`.
4. Adopt the candidate only if all of these hold:
   - candidate `validated_rate` is at least 0.90 and at least the baseline minus 0.02;
   - `template_rate` rises by no more than 2 points;
   - 20 rendered samples pass human review.
5. Paste both summaries into the PR.

Each run makes up to `--max-calls` paid DeepSeek calls (about $0.0009 each at the engine spec 7.8 estimate; verify current pricing); they are recorded in `llm_usage` under the `prose_eval` feature. The script exits with code 2 without `--yes`, without `DEEPSEEK_API_KEY`, above 200 calls, or on empty input.
