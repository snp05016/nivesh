# Label Generation

### 1. Current Targets
- `forward_return_20d` (Continuous)
- `forward_return_60d` (Continuous)
- `direction_20d` (Boolean: `fr_20d > 0`)
- `direction_60d` (Boolean: `fr_60d > 0`)

### 2. Objective Function
LightGBM defaults to binary classification using `direction_20d` as the target (configured via `WalkForwardConfig.target_col = "direction_20d"`).

### 3. Refinement Requirements
The current label is strictly binary (`>0` is bull, `≤0` is bear). 
This creates noise around 0%. A return of +0.01% is labeled identically to +25%. 
It is recommended to implement multi-class labeling:
- Class 1: `> DIRECTION_THRESHOLD` (Bullish)
- Class -1: `< -DIRECTION_THRESHOLD` (Bearish)
- Class 0: Neutral

Currently, `walk_forward.py` treats `y_true` as integer 1/0 and evaluates AUC/Brier accordingly. We should either adapt LightGBM to regress continuous returns (and use thresholds post-inference) or use ternary classification.
