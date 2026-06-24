# Risk Report

### 1. Survivorship Bias in Training
The current training pipeline accepts OHLCV data for the NIFTY 50 or broad indices. If the training dataset only contains the *current* NIFTY 50 constituents, the model trains on companies that survived and thrived, implicitly leaking future knowledge.

### 2. Feature NaN Propagation
`Alpha158` contains extensive trailing metrics (e.g., 60-day moving averages). If a stock has < 60 days of history (recent IPO), the feature vector contains NaNs. LightGBM handles NaNs natively, but the `_fallback_score` heuristic in `inference.py` accesses `features_df[col][0]` assuming floating-point validity. This may cause type-cast errors or silent math failure.

### 3. Static Volatility Thresholding
The `DIRECTION_THRESHOLD` is fixed at 0.005 (0.5%). This threshold might represent a massive move for a low-beta utility stock, but noise for a high-beta small cap. Treating all assets with the same flat return threshold degrades classification accuracy.

### 4. Zero-Variance Target Leakage
If forward returns are calculated using `shift(-N)`, any unadjusted stock splits within that window will result in massive artificial returns (e.g., -50% overnight on a 2:1 split), confusing the model.

### 5. Overconfidence Feedback Loop
If the LLM pillar produces uncalibrated 95% confidences, and the fusion weight is strictly 0.45, the fused score will remain wildly overconfident. If users act on this, the risk is severe financial misallocation.
