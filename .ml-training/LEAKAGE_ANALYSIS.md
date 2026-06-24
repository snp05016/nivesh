# Leakage Analysis

### 1. Feature Point-in-Time (PiT) Integrity
**Status: Safe**
`feature_builder.py` constructs features via an explicit loop:
```python
ohlcv_slice = sym_df.iloc[: i + 1]
...
alpha_row = fc.compute_all(pl.from_pandas(fc_input))
```
This guarantees that features at index `i` only see data `≤ i`. There is no leakage via rolling window bleed.

### 2. Temporal Scaling Leakage
**Status: Safe**
No global scalers (e.g., `StandardScaler.fit(full_dataset)`) are applied before the split. `fc = FeatureComputer(..., scaler_params=None)` ensures that Alpha158 returns raw metrics.

### 3. Target Construction Leakage
**Status: Unsafe (Corporate Actions)**
```python
fr_20d = _safe_pct(closes_all[i + 20], closes_all[i])
```
This formula assumes `close` is continuous. If a 1:10 stock split occurs at `i+5`, `closes_all[i+20]` will be ~10% of `closes_all[i]`, registering as a -90% crash. Since Bhavcopy provides raw unadjusted prices, the targets will contain massive false negatives, poisoning the ML model.

### 4. Survivorship Bias Leakage
**Status: Unsafe**
If we pull the current NIFTY 50 and download their 2018-2025 history, we are implicitly selecting stocks that succeeded. The model will learn an optimistic baseline.
