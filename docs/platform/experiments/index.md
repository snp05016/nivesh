# Experiment log

Every row below was produced by `python -m lab.run_templates` at code revision `9ca23f6b61`. The raw output, with every spec and skeptic finding, is in [`dev-templates-2026-10-19.json`](dev-templates-2026-10-19.json).

!!! warning "Development dataset"
    Source `local_csv`: 102,545 rows from 2018-01-01 to 2026-06-23. This is today's Nifty 50 list with pre-adjusted prices, so it carries **survivorship bias**. These numbers show how the lab behaves. They are not findings about Indian markets. Rerun with `--source store` once the bhavcopy panel is populated.

## Published anomalies, one at a time

The research window runs from 2019-06-01 to 12 months before 2026-06-01; the last 12 months are held out and were not used. Rebalancing is non-overlapping at the stated horizon, within a universe of up to 49 names. The label is the forward return measured from the **next** close. Costs are the dated statutory charges plus 10 bps of slippage per side. `trials` increased by one with each run (1 to 7), so the deflated Sharpe bar rises down the table.

| Template | Reference | h | Mean IC | IC 95% CI | Perm. p | Net excess / period | Turnover | DSR | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| momentum_12_1 | Jegadeesh & Titman (1993) | 20 | 0.0012 | [-0.0611, 0.0651] | 0.505 | -0.00224 | 0.222 | 0.2516 | **not_supported** |
| short_reversal | Jegadeesh (1990); Lehmann (1990) | 5 | 0.0137 | [-0.01, 0.0362] | 0.0399 | -0.00346 | 0.808 | 0.0 | **not_supported** |
| low_volatility | Ang, Hodrick, Xing & Zhang (2006) | 20 | -0.03 | [-0.0841, 0.0256] | 0.9501 | -0.00116 | 0.328 | 0.1058 | **not_supported** |
| near_52w_high | George & Hwang (2004) | 20 | -0.0415 | [-0.0976, 0.016] | 0.992 | -0.00453 | 0.56 | 0.0054 | **not_supported** |
| amihud_illiquidity | Amihud (2002) | 20 | 0.0602 | [0.0183, 0.1029] | 0.004 | 0.00884 | 0.301 | 0.9498 | **fragile** |
| abnormal_volume | Gervais, Kaniel & Mingelgrin (2001) | 20 | -0.0047 | [-0.0428, 0.0358] | 0.6367 | -0.0016 | 0.782 | 0.0329 | **not_supported** |
| max_effect | Bali, Cakici & Whitelaw (2011) | 20 | -0.0271 | [-0.0604, 0.0046] | 0.9361 | -0.00968 | 0.725 | 0.0 | **not_supported** |

## Comparison across all candidates (h = 20)

illiq_20 looked best in-sample but is not supported: its own checks failed (Data Quality Investigator). Probability of backtest overfitting across the candidates: 2%.

| Candidate | Verdict | Mean IC | Perm. p | Holm p | Romano–Wolf p |
|---|---|---|---|---|---|
| mom_12_1 | not_supported | 0.0012 | 0.505 | 1.0 | 0.9975 |
| rev_5 | not_supported | 0.023 | 0.0898 | 0.5388 | 1.0 |
| lowvol_60 | not_supported | -0.03 | 0.9501 | 1.0 | 0.9975 |
| near_high | not_supported | -0.0415 | 0.992 | 1.0 | 1.0 |
| illiq_20 | fragile | 0.0602 | 0.004 | 0.028 | 0.001 |
| abn_vol | not_supported | -0.0047 | 0.6367 | 1.0 | 1.0 |
| neg_max | not_supported | -0.0271 | 0.9361 | 1.0 | 1.0 |

## What this shows

- **Six of the seven published anomalies show no reliable evidence** on this panel and window. Their bootstrap CIs include zero, or the effect does not survive costs.
- **Amihud illiquidity looks strong.** IC is 0.06, the CI excludes zero, Holm p < 0.05 and Romano–Wolf p ≈ 0.001. The lab still labels it **fragile**. The universe is today's index members, so the stocks that were illiquid in 2019 and are in the index now are, by construction, ones that grew. The Data Quality Investigator treats this as a critical failure. This is the *Alpha Autopsy* idea in action: an attractive result is taken apart by the data's own construction.
- The low PBO across candidates (2%) means picking the in-sample best was not itself an overfitting artefact. The problem is the dataset, not the selection.

## Reproduce

```bash
cd ml-engine
RESEARCH_LOCAL_CSV=/path/to/nifty50_data.csv python -m lab.run_templates --source local_csv --out ../docs/platform/experiments/run.json
```
