# Lab API contract

Two layers. The **ml-engine** (`/lab/v1`, internal, `X-ML-Engine-Key`) is stateless: callers send
`(config, actions)` and get computed results. The **backend** (`/api/v1/research-lab`, user auth) owns
users, persistence, permissions, LLM use and feature flags, and is the only thing iOS talks to.

All dates are ISO `YYYY-MM-DD` exchange dates (Asia/Kolkata trading days). Money is INR, floats rounded to paise.

## Shared shapes

### SimConfig
```json
{"start": "2020-02-03", "end": "2020-06-30", "universe": ["RELIANCE", "HDFCBANK"],
 "capital": 1000000, "max_participation": 0.1, "impact_coef": 0.7,
 "brokerage_flat": 20, "brokerage_pct": 0.0003, "hide_identity": false}
```
Rules: 1–30 symbols; capital 10,000–1e9; span ≤ 5 years; `end` ≤ today − `LAB_MIN_DATA_AGE_DAYS` (default 30).

### Action (append-only log; replay is deterministic)
```json
{"type": "order", "symbol": "RELIANCE", "side": "BUY", "qty": 10,
 "order_type": "MARKET|LIMIT|STOP", "limit": 1300.5, "stop": 1200, "tif": "DAY|GTC",
 "thesis": "why", "planned_stop": 1200, "planned_exit": 1500, "horizon_days": 20, "conviction": 0.6}
{"type": "cancel", "order_id": "o3"}
{"type": "advance", "days": 5}
{"type": "note", "text": "..."}
```
Order ids are `o1, o2, …` in placement order. An order placed at `clock` can fill on the next session at the earliest.

### SessionPayload (`POST /lab/v1/sim/state`)
```json
{"state": {"clock": "2020-03-02", "finished": false, "cash": 812345.5, "equity": 990000.1,
   "positions": [{"symbol","qty","avg_cost","last","value","unrealised"}],
   "orders": [{"id","symbol","side","qty","order_type","limit","stop","tif","placed","status","filled_qty","avg_price","reason","remaining","thesis","planned_stop","planned_exit","horizon_days","conviction"}],
   "fills": [{"order_id","symbol","side","qty","price","d","charges":{"brokerage","stt","exchange_txn","sebi_fee","stamp_duty","gst","total","sources"},"slippage_bps","ref_price"}],
   "trades": [{"symbol","qty","entry_date","exit_date","entry_cost","exit_net","entry_order_id","exit_order_id","pnl","ret"}],
   "equity_curve": [{"d","equity","cash","benchmark"}],
   "events": [{"d","event", "...": "..."}], "assumptions": ["..."], "days_total": 103, "day_index": 20},
 "performance": {"start_capital","final_equity","total_return","cagr","ann_vol","sharpe","sortino","max_drawdown",
   "benchmark_return","excess_return","turnover_x","costs_inr","cost_drag","trades","hit_rate","profit_factor","avg_hold_days","sessions","score"},
 "watchlist": [{"symbol","listed","date","close","volume","chg_1d","chg_20d","stale"}],
 "provenance": {"source": "store|local_csv", "warnings": ["..."], "benchmark", "rows", "window"},
 "benchmark": "^NSEI|null",
 "news": [{"date","symbol|null","title","source","url"}]}
```
`news` holds only items published on or before `clock` (curated, sourced scenario timelines), newest first.
Order `status`: `OPEN | PARTIAL | FILLED | CANCELLED | EXPIRED | PARTIAL_EXPIRED | REJECTED`.
Invalid action → **422** `{"detail": "action N: <reason safe to show>"}`.

## ml-engine `/lab/v1` (internal)

| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/sim/state` | `{config, actions}` | SessionPayload |
| POST | `/sim/history` | `{config, asof, symbol, bars}` | `{symbol, asof, bars:[{d,o,h,l,c,v}]}` (never after `asof`) |
| POST | `/sim/autopsy` | `{config, actions, order_id?}` | `{clock, trades:[Autopsy], counterfactuals, counterfactual_note, behaviour:[Flag], performance, provenance}` |
| GET | `/scenarios` | – | `{version, scenarios:[{id,title,category,start,end,difficulty,universe_hint,briefing,debrief,timeline,learning_goals,related_concepts,sources,verification,notes}]}` |
| GET | `/universe?start=&n=` | – | `{asof, symbols, provenance}` (liquidity-ranked with data up to `start`) |
| GET | `/hypothesis/templates` | – | `{templates:[{id,title,score,horizon,program,reference}], fields, unavailable_fields_note}` |
| POST | `/features/compile` | `{program}` | `{ok, fingerprint, nodes, outputs:[{name,lineage,warmup_bars,availability}]}` or `{ok:false,error,line,col}` |
| POST | `/hypothesis/run` | Spec | Experiment report (below) |
| POST | `/hypothesis/compare` | `{base: Spec, candidates:[{program,score}]}` | `{status, periods, candidates:[{name,verdict,mean_ic,net_per_period,permutation_p,holm_p,romano_wolf_p}], pbo, in_sample_best, best_survives_corrections, text, reports}` |
| POST | `/events/timeline` | `{symbol, start, end}` | `{symbol,start,end,bars:[{d,c,v}],items:[{date,kind: price_anomaly|volume_anomaly|corporate_action|sourced_event, evidence: prices|exchange|source, text, ...}], note, provenance}` |
| GET | `/school/curriculum` | – | `{tracks, concepts, lessons:[{id,track,title,minutes,prereqs,concepts,summary}]}` |
| GET | `/school/lessons/{id}` | – | lesson with `body` and quiz **without** answers/explanations |
| POST | `/school/grade` | `{lesson_id, answers:[int], state}` | `{score, per_question:[{id,correct,explain}], state}` |
| POST | `/school/next` | `{state, weaknesses:[flag ids], k}` | `{lessons:[lesson summary + reason]}` |

### Autopsy
```json
{"symbol","qty","entry_order_id","exit_order_id","thesis","planned_stop","planned_exit","conviction",
 "knowable": {"asof","bars_available","ret_5d","ret_20d","ret_60d","vol_20d_daily","vol_20d_ann","ret_5d_z",
              "dist_from_52w_high","volume_vs_20d_avg","benchmark_ret_20d","news_visible":[...],
              "position_weight","risk_per_trade","base_rate":{"horizon","windows","beat_benchmark_share"}},
 "process": {"score": 0-100, "checks": [{"id","passed","text"}]},
 "hindsight": {"entry_date","exit_date","sessions_held","return_net","pnl_net","benchmark_return","excess_return",
               "max_adverse_excursion","max_favourable_excursion","fees_inr","fees_share_of_gross","move_in_sigmas"},
 "verdict": {"quadrant": "earned|bad_break|lucky|predictable_loss", "text"}}
```
`knowable` uses only data dated ≤ the order's placement date. `hindsight` is labelled as such in every UI.

### Flag (behaviour)
`{"id": "overtrading|ignored_costs|concentration|disposition_effect|chasing_momentum|no_thesis|stop_discipline|poor_calibration", "severity": "low|medium|high", "evidence": {...}, "text"}`

### Spec (hypothesis)
```json
{"question","program","score","start","end","horizon":1|5|10|20|60,"direction":1|-1,"universe_n":50,"min_names":15,
 "n_quantiles":5,"filter":null,"holdout_months":12,"use_holdout":false,"trials_so_far":1,"permutations":300}
```
Report: `{status: ok|invalid|insufficient_data, fingerprint, lineage, warmup_bars, availability, research_window, holdout_window,
costs, result:{periods, mean_names, mean_ic, ic_hac_t, ic_ci95, ic_positive_share, top_excess_gross_per_period,
top_excess_net_per_period, top_minus_bottom_per_period, avg_turnover, net_sharpe_ann, net_sharpe_ci95},
series:[{date,ic,top_net}], permutation_p, baselines, incremental_ic, ic_by_year, regimes, deflated_sharpe,
skeptics:[{agent,status:pass|warn|fail,finding,evidence,critical}], verdict:{label: supported|fragile|not_supported|insufficient_data, text, failed_checks}, holdout?, provenance}`.

## Backend `/api/v1/research-lab` (iOS-facing, `Authorization: Bearer`)

Gated by feature flag `research_lab` (default **off** until legal review of NSE data terms; see verified facts).

| Method | Path | Notes |
|---|---|---|
| GET | `/scenarios` | proxy |
| GET | `/universe?start=&n=` | proxy |
| POST | `/sessions` | `{title?, scenario_id?, config}` → `{id, title, scenario_id, created_at, ...SessionPayload}` |
| GET | `/sessions` | `[{id,title,scenario_id,clock,equity,finished,updated_at}]` (own only) |
| GET | `/sessions/{id}` | `{id,title,...SessionPayload}` |
| POST | `/sessions/{id}/actions` | `{action, client_action_id?}` → appended only if the replay accepts it; idempotent on `client_action_id`; 422 with reason otherwise |
| POST | `/sessions/{id}/history` | `{symbol, bars}`; backend supplies `asof` = session clock |
| GET | `/sessions/{id}/autopsy?order_id=` | ml-engine autopsy |
| POST | `/sessions/{id}/mentor` | `{question, order_id?}` → `{answer, grounded_on:{...facts used}, mode:"llm"|"rules", disclaimer}` |
| DELETE | `/sessions/{id}` | |
| POST | `/events/timeline` | proxy (Market Event Reconstruction) |
| GET | `/school/curriculum` · `/school/lessons/{id}` | proxy |
| POST | `/school/lessons/{id}/grade` | `{answers}` → grade + saves progress |
| GET | `/school/progress` | `{state, mastered:[concepts], completed:[lessons]}` |
| GET | `/school/next` | uses the user's latest behaviour flags as weaknesses |
| GET | `/research/templates` | proxy |
| POST | `/research/compile` | proxy |
| POST | `/research/translate` | `{question}` → `{spec?, explanation, missing_data:[...], mode}` (LLM with compile-validation; rules fallback) |
| POST | `/research/experiments` | Spec without `trials_so_far` (server fills it from the user's ledger) → stored report |
| GET | `/research/experiments` · `/research/experiments/{id}` | own ledger |
| POST | `/research/compare` | proxy with ledger-aware trials |
