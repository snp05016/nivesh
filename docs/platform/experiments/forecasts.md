# Distributional forecasts: do they beat the stock's own history?

The app used to say "direction = UP, confidence = 0.67". `lab/forecast.py` replaces that with a forecast of the whole distribution: seven quantiles, P(return > 0) and 80%/90% intervals recalibrated by conformal prediction. Every forecast also carries an out-of-sample check against the simplest honest baseline, which is the stock's own past returns. If the model cannot beat that baseline, the forecast says so.

The raw output is in [`forecast-dev-2026-10-19.json`](forecast-dev-2026-10-19.json). It was produced at code revision `d09a495aa1` plus the uncommitted `lab/forecast.py`, and the full run takes about 160 s.

!!! warning "Development dataset"
    Source `local_csv`: 102,545 rows from 2018-01-01 to 2026-06-23. The universe is the 49 **current** Nifty 50 members, and prices are pre-adjusted for corporate actions. That gives **survivorship bias**: every stock here survived into today's index. The positive drift, the up-day base rate and anything that looks like a "winner" signal are inflated. Treat these numbers as a check of the method, not as findings about Indian equities. Rerun with `--source store` once the bhavcopy panel is populated.

## Setup

| Item | Choice |
|---|---|
| Target | Forward **log** return from the **next** close: `log px[t+1+h] − log px[t+1]`. Two variants: `raw`, and `rel` (minus the same-date cross-sectional mean). |
| Horizons | h = 5 and h = 20 sessions |
| Test period | 2021-01-01 to 2026-05-31: 1,334 dates (h=5) and 1,330 dates (h=20), about 65,000 stock-date rows each |
| Models | `climatology`: the stock's own expanding quantiles of past h-returns. `ewma_vol`: zero mean, RiskMetrics EWMA vol (λ = 0.94) × √h, with quantiles from pooled standardised residuals (filtered historical simulation). `lgbm_quantile`: one LightGBM model per quantile (100 trees, 8 leaves, seed 0) on 12 FDL features (returns over 5/20/60 sessions, vol over 20/60, volume z-score, distance from the 52-week high, cross-sectional ranks). |
| Walk-forward | Expanding window, refit every 63 sessions. Training ends h + 1 + 5 sessions before the first prediction (purge plus embargo). Predicted quantiles are sorted so they never cross. |
| Point-in-time | A forecast made at the close of t uses only labels realised by t, i.e. label dates ≤ t − h − 1. A test checks that forecasts at T are bit-identical whether or not data after T exists. |
| Conformal | Each central interval is **widened** (never narrowed) by the split-conformal quantile of the CQR scores from the last 63 sessions whose labels are already realised. |
| Skill test | Per-date difference in pinball loss (climatology minus model). "Significant" requires the block-bootstrap 95% CI to exclude 0 **and** HAC t > 1.96. |

## Headline: quantile (pinball) loss vs climatology

Skill is `1 − loss/loss_climatology`. Positive means better than the stock's own history.

| h | Target | ewma_vol skill | HAC t | lgbm_quantile skill | HAC t | Significant? |
|---|---|---|---|---|---|---|
| 5 | raw | +0.55% | 1.82 | **+0.77%** | 2.76 | LGBM yes, EWMA no |
| 5 | rel | +0.41% | 1.47 | **+1.19%** | 5.97 | LGBM yes, EWMA no |
| 20 | raw | +0.47% | 0.64 | −0.06% | −0.07 | neither |
| 20 | rel | +0.58% | 0.91 | **+1.18%** | 2.33 | LGBM yes, EWMA no |

!!! note "How big is about 1% skill?"
    It is small. LightGBM's distribution is about 1% better than climatology, measured by quantile loss. There are eight tests here (4 configurations × 2 models) and they are not independent. After a Holm adjustment over those eight, the h = 5 results survive (p ≈ 0 and 0.006 × 7 ≈ 0.04), but **h = 20 rel does not** (p ≈ 0.02 × 6 ≈ 0.12). The skill also sits mostly in **low-volatility regimes**: about +2.2% there and −0.4% to +0.5% when market vol is high (see below).

## Where the skill comes from: spread, not direction

| h | Target | Model | Median rank IC | IC 95% CI | P(up) BSS vs ex-ante base rate | ECE |
|---|---|---|---|---|---|---|
| 5 | raw | climatology | −0.013 | [−0.036, 0.010] | −0.0037 | 0.029 |
| 5 | raw | ewma_vol | 0.012 | [−0.011, 0.034] | 0.0001 | 0.035 |
| 5 | raw | lgbm_quantile | −0.001 | [−0.018, 0.017] | −0.0053 | 0.030 |
| 5 | rel | lgbm_quantile | 0.004 | [−0.011, 0.018] | −0.0009 | 0.014 |
| 20 | raw | ewma_vol | 0.034 | [−0.011, 0.074] | 0.0001 | 0.059 |
| 20 | raw | lgbm_quantile | −0.014 | [−0.046, 0.018] | −0.0160 | 0.056 |
| 20 | rel | lgbm_quantile | 0.005 | [−0.021, 0.031] | −0.0041 | 0.023 |

!!! danger "No model has directional skill"
    No forecast median ranks stocks better than chance: every IC confidence interval includes 0. No P(up) beats the ex-ante base rate: every Brier skill score is ≤ 0.0001. LightGBM's pinball gain therefore comes from the **shape and width** of its distribution, i.e. it forecasts volatility better than the stock's long-run history does. It does not come from knowing which way prices will move. `forecast_for` reports this explicitly. When the median's rank IC is not significant, the note says *"do not read the median or p_up as a call"*.

## Calibration of intervals

Coverage is the share of realised returns that fall inside the interval. The nominal values are 80% and 90%.

| h | Target | Model | 80% raw → conformal | 90% raw → conformal | Interval score 80% (raw) |
|---|---|---|---|---|---|
| 5 | raw | climatology | 84.6% → 85.2% | 93.1% → 93.5% | 0.1356 |
| 5 | raw | ewma_vol | 79.2% → 80.6% | 89.8% → 90.5% | 0.1347 |
| 5 | raw | lgbm_quantile | 80.6% → 82.0% | 90.4% → 91.3% | **0.1339** |
| 20 | raw | climatology | 85.2% → 86.3% | 93.6% → 94.1% | 0.2682 |
| 20 | raw | ewma_vol | 80.7% → 82.2% | 90.9% → 91.6% | 0.2685 |
| 20 | raw | lgbm_quantile | 81.8% → 83.7% | 91.3% → 92.3% | 0.2680 |
| 20 | rel | lgbm_quantile | 83.1% → 84.1% | 91.8% → 92.4% | **0.2275** |

- **Climatology over-covers on average** (about 85% for a nominal 80%) and is miscalibrated by regime. Its 80% interval covers 81% of outcomes in high-vol periods and 88–89% in calm ones. It is too wide when markets are quiet.
- **EWMA vol and LightGBM are close to nominal on average.** EWMA's coverage is the most even across regimes: 80% in high-vol and 78% in low-vol periods at h = 5 raw.
- **Conformal widening** only ever widens, so it fixes under-coverage. In the stormy regime it lifts coverage toward or past nominal, e.g. LightGBM at h = 20 raw goes from 79.9% to 83.2%. On models that already over-cover it adds a little width, and the interval score worsens slightly. That is the price of the "never narrower" rule. A signed (two-sided) CQR adjustment would let it shrink as well, and is a possible follow-up.

## Regimes (trailing 20-session market vol, split at the test-period median)

Pinball skill vs climatology within each regime:

| h | Target | Model | High vol | Low vol |
|---|---|---|---|---|
| 5 | raw | ewma_vol | −0.64% | +1.95% |
| 5 | raw | lgbm_quantile | −0.45% | +2.21% |
| 5 | rel | lgbm_quantile | +0.31% | +2.19% |
| 20 | raw | lgbm_quantile | −0.82% | +0.84% |
| 20 | rel | lgbm_quantile | +0.55% | +1.90% |

Both conditional models win when markets are calm and climatology's intervals are too wide. They lose or tie when vol is high.

## Reproducing the historical claim: "LightGBM hit rate ≈ 52.66% vs momentum ≈ 52%"

Hit rate here is the share of rows where the sign of the forecast median equals the sign of the realised return. "Always up" is the base rate.

| h | Target | Always majority | Climatology | EWMA vol | LightGBM (median) | Momentum (sign of past h-return) |
|---|---|---|---|---|---|---|
| 5 | raw | **53.9%** (always up) | 52.8% | 54.0% | 51.9% [50.1, 54.1] | 49.5% |
| 5 | rel | 51.8% (always down) | 50.5% | 51.8% | 51.6% [50.8, 52.2] | 49.5% |
| 20 | raw | **57.1%** (always up) | 55.7% | 57.1% | 54.1% [50.2, 58.0] | 49.4% |
| 20 | rel | 51.0% (always down) | 49.8% | 51.0% | 50.9% [49.7, 52.0] | 49.0% |

!!! failure "Not reproduced as evidence of skill"
    LightGBM's hit rate on the most comparable setup (h = 5, raw) is **51.9%**, close to the claimed 52.66%. But it is **below** the 53.9% you get by always saying "up" on this survivorship-biased panel, and EWMA vol's ≈ 54% is just "always up", since its median is about zero plus drift. Momentum's hit rate is 49.0–49.5% here, not 52%. A hit rate around 52% is therefore not evidence of skill on this data. It is below the base rate.

    Caveats: the original setup (features, horizon, universe, period, whether neutral calls were excluded) is not recorded in the repo. Directional hit rate on a panel with ~54% up-days is a weak metric in any case. Use rank IC or Brier skill instead.

## What a forecast looks like now

`forecast_for(panel, "RELIANCE", "2026-06-23", h=5)` gives:

| Field | Value |
|---|---|
| quantiles (5% … 95%) | −5.2%, −3.8%, −1.7%, +0.2%, +2.6%, +4.5%, +6.1% (log) |
| p_up | 0.53 |
| interval_80 / interval_90 | [−3.8%, +4.5%] / [−5.2%, +6.1%] |
| calibration | 80% coverage over the last 63 realised sessions: 80.2% (n = 3,087); conformal widening 0 |
| evidence_sufficient | `true`: universe-wide pinball skill +1.9%, HAC t 2.6 over the last 244 sessions |
| note | "… The edge is in the spread of outcomes, not the direction: the median's cross-sectional rank IC is not significant, so do not read the median or p_up as a call." |

`evidence_sufficient` is `false` whenever the model's out-of-sample skill vs climatology is not significantly positive. In that case the note says the forecast is no better than the stock's own history. The tests check this on pure-noise data.

## Reproduce

```bash
cd ml-engine
RESEARCH_LOCAL_CSV=/path/to/nifty50_data.csv python -m lab.forecast --source local_csv \
  --out ../docs/platform/experiments/forecast-dev-2026-10-19.json
python -m pytest -q --import-mode=importlib tests/lab/test_forecast.py   # synthetic checks, ~14 s
```
