# Prediction Calibration System

Technical documentation for the Nivesh prediction calibration pipeline, covering statistical
methodology, API surface, iOS integration, and the path toward LightGBM model training.

---

## 1. What Calibration Means

A prediction system is **well-calibrated** when its stated confidence matches its empirical
accuracy. If the system issues 100 predictions at 70% confidence, roughly 70 of those
predictions should turn out correct.

**Overconfidence** occurs when stated confidence exceeds realized accuracy. A system that
claims 80% confidence but is correct only 55% of the time is overconfident by 25 percentage
points. Overconfidence is the more dangerous failure mode in a financial context because it
encourages users to size positions aggressively on unreliable signals.

**Underconfidence** occurs when realized accuracy exceeds stated confidence. A system that
claims 50% confidence but is correct 68% of the time is underconfident. While less dangerous,
underconfidence wastes signal quality -- users ignore predictions that deserved more weight.

Calibration is distinct from discrimination (the ability to separate winners from losers).
A perfectly calibrated model can still be useless if it assigns 50% confidence to everything.
The metrics in this system measure both properties.

---

## 2. Confidence Bucket Methodology

Predictions are grouped into six confidence buckets for calibration analysis:

| Bucket | Range | Purpose |
|--------|-------|---------|
| 0-50%  | Low confidence | Baseline: should these even be shown to users? |
| 50-60% | Marginal confidence | Weak signals, close to coin-flip |
| 60-70% | Moderate confidence | Actionable threshold for most investors |
| 70-80% | High confidence | Core prediction band |
| 80-90% | Very high confidence | Should be correct ~4 out of 5 times |
| 90-100% | Extreme confidence | Rare; demands near-perfect accuracy |

### Why These Buckets

The bucket widths are intentionally non-uniform. The 0-50% range collapses into a single
bucket because predictions below 50% confidence carry minimal actionable value and are
relatively rare in production. From 50% upward, each 10-percentage-point band gets its own
bucket, providing finer granularity where it matters most -- at higher confidence levels
where users are most likely to act on the signal and where overconfidence causes the most
financial harm.

### Implementation

Bucket assignment is defined in `services/prediction_calibration_service.py`:

```python
CONFIDENCE_BUCKETS = [
    (0, 50, "0-50%"),
    (50, 60, "50-60%"),
    (60, 70, "60-70%"),
    (70, 80, "70-80%"),
    (80, 90, "80-90%"),
    (90, 100, "90-100%"),
]
```

For each bucket, the service computes:
- **count**: total predictions in the bucket
- **accuracy**: fraction of matured 30d predictions where `hit_direction_30d = TRUE`
- **avg_brier_score**: mean Brier score for the bucket (see section 3)
- **avg_confidence**: mean stated confidence within the bucket
- **overconfidence**: `avg_confidence / 100 - accuracy` (positive = overconfident)

---

## 3. Brier Score

The Brier score is the primary per-prediction scoring rule. It measures the squared
distance between a probabilistic forecast and the binary outcome.

### Formula

```
brier_score = (confidence / 100 - outcome)^2
```

Where:
- `confidence` is the fused confidence percentage (0-100) stored in `confidence_pct`
- `outcome` is 1 if the prediction's directional call was correct (`hit_direction = TRUE`),
  0 if incorrect

### Range and Interpretation

| Brier Score | Meaning |
|-------------|---------|
| 0.00 | Perfect: 100% confident and correct, or 0% confident and wrong |
| 0.25 | Equivalent to constant 50% confidence (no skill) |
| 1.00 | Worst: 100% confident and wrong |

### Properties

The Brier score rewards two things simultaneously:

1. **Calibration** -- predictions that match their stated confidence score well.
   A 70% confident prediction that hits scores `(0.70 - 1.0)^2 = 0.09`, while
   a 70% confident prediction that misses scores `(0.70 - 0.0)^2 = 0.49`.

2. **Discrimination** -- the ability to assign high confidence to correct predictions
   and low confidence to incorrect ones. A system that says 90% on winners and 20% on
   losers will have a much lower average Brier score than one that says 60% on everything.

### Computation in the Outcome Tracker

Brier scores are computed per-horizon in `services/outcome_tracker.py` during the nightly
outcome backfill:

```python
outcome = 1.0 if p.hit_direction_30d else 0.0
conf_normalized = p.confidence_pct / 100.0
p.brier_score_30d = (conf_normalized - outcome) ** 2
```

Scores are stored at three horizons: `brier_score_7d`, `brier_score_30d`, `brier_score_90d`.

---

## 4. Expected Calibration Error (ECE)

ECE is the **primary calibration metric** used by the system. It measures the weighted
average gap between stated confidence and realized accuracy across all buckets.

### Formula

```
ECE = sum over buckets of (n_bucket / N_total) * |accuracy_bucket - confidence_bucket / 100|
```

Where:
- `n_bucket` is the number of predictions in a given bucket
- `N_total` is the total number of predictions across all buckets
- `accuracy_bucket` is the fraction of correct predictions in the bucket (0 to 1)
- `confidence_bucket` is the mean stated confidence in the bucket (0 to 100, divided by 100)

### Interpretation

| ECE Value | Calibration Quality |
|-----------|-------------------|
| 0.00 - 0.05 | Excellent -- stated confidence closely matches accuracy |
| 0.05 - 0.10 | Good -- minor calibration drift, acceptable for production |
| 0.10 - 0.20 | Moderate -- systematic over- or underconfidence in some bands |
| 0.20+ | Poor -- confidence scores are misleading to users |

### Why ECE Is the Primary Metric

ECE directly answers the question "how much should a user trust the confidence score?"
Unlike the Brier score (which conflates calibration with discrimination), ECE isolates
calibration quality. A model with high discrimination but poor calibration will have a
low Brier score but high ECE, signaling that the confidence values need recalibration
even though the model separates winners from losers effectively.

The weighting by bucket size ensures that heavily populated buckets dominate the metric.
A large calibration error in a bucket with 2 predictions does not inflate ECE the way
a moderate error in a bucket with 200 predictions does.

### Implementation

Computed in `_compute_calibration_errors()` in `services/prediction_calibration_service.py`:

```python
for b in buckets:
    gap = abs(accuracy - avg_conf / 100.0)
    ece_sum += (count / total) * gap
```

---

## 5. Max Calibration Error (MCE)

MCE is the **worst-case calibration error** across any single bucket.

### Formula

```
MCE = max over all buckets of |accuracy_bucket - confidence_bucket / 100|
```

### Why MCE Matters

ECE can mask severe miscalibration in a single bucket if that bucket has few predictions.
MCE catches this. If ECE is 0.06 (good) but MCE is 0.35, it means one confidence band
is severely miscalibrated -- likely the 90-100% bucket where overconfidence is most
dangerous.

MCE is especially important for tail risk: a user acting on a 95% confidence prediction
that actually has 60% accuracy faces a materially different risk profile than expected.

In the implementation, MCE is computed alongside ECE in the same loop:

```python
mce_val = max(mce_val, gap)
```

---

## 6. Pillar Attribution

The fused confidence score is a weighted combination of five pillars. Pillar attribution
answers: which pillars actually predict outcomes, and which are noise?

### The Five Pillars

| Pillar | Column | Scale | What It Measures |
|--------|--------|-------|-----------------|
| `llm_confidence` | `llm_confidence` | 0-100 | Raw confidence from the LLM analysis agent after dialectical debate |
| `quant_confidence` | `quant_confidence` | 0-1 | Quantitative engine score from technical indicators and momentum |
| `venn_abers_confidence` | `venn_abers_confidence` | 0-1 | Venn-Abers calibrated probability, a distribution-free calibration method |
| `signal_agreement` | `signal_agreement` | 0-1 | Bull/bear vote ratio across research agents |
| `ml_confidence` | `ml_confidence` | 0-1 | ML engine output (LightGBM when trained, technical heuristic fallback) |

### Fusion Weights

Defined in `services/confidence_fusion.py`:

```
fused = 0.45 * llm + 0.25 * quant + 0.15 * venn_abers + 0.10 * signal_agreement + 0.05 * ml
```

Missing values default to 0.5 (neutral) for all pillars except `ml_confidence`, which
defaults to 0.0 when unavailable.

### Correlation Computation

For each pillar, the service computes **point-biserial correlation** between the pillar's
continuous values and the binary `hit_direction_30d` outcome.

Point-biserial correlation is the appropriate measure when one variable is continuous
(pillar score) and the other is dichotomous (hit/miss). The formula:

```
r = (M1 - M0) / S * sqrt(n1 * n0 / n^2)
```

Where:
- `M1` = mean pillar value for correct predictions (hit = TRUE)
- `M0` = mean pillar value for incorrect predictions (hit = FALSE)
- `S` = standard deviation of all pillar values
- `n1`, `n0` = counts of correct and incorrect predictions

A positive correlation means higher pillar values associate with correct predictions.
The correlation is clamped to [-1, 1] for floating-point safety.

### Predictive Lift

Predictive lift measures how much additional predictive power a pillar provides compared
to the final fused confidence score:

```
lift = pillar_correlation - baseline_confidence_correlation
```

A positive lift means the pillar is individually more correlated with outcomes than the
fused score. A negative lift means the pillar adds noise relative to the fused output.
This metric helps identify pillars whose fusion weights should be increased or decreased.

### Bucketed Accuracy

Each pillar's value range is divided into 5 equal-width buckets (from its observed min
to max). Within each bucket, the service computes the hit rate. This reveals whether the
pillar has monotonic predictive power -- accuracy should increase as pillar value increases.
Non-monotonic patterns suggest the pillar's signal is unreliable or nonlinear.

### Missing Data Handling

Each pillar reports a `missing_rate`: the fraction of total predictions where that pillar's
value is NULL. High missing rates reduce the reliability of correlation estimates and
indicate that the pillar was not computed for a significant portion of predictions (e.g.,
`ml_confidence` is NULL when the LightGBM model is not yet trained).

### Usefulness Ranking

Pillars are ranked by the absolute value of their point-biserial correlation. Rank 1 is the
most predictive pillar. Pillars with no computable correlation (all NULL or zero variance)
receive a NULL rank.

---

## 7. API Endpoints and iOS Chart Integration

### GET /api/v1/predictions/calibration

**Response schema**: `CalibrationResponse`

Returns bucket-level calibration data, global error metrics, horizon hit rates, and
group-level breakdowns.

**iOS usage**: The reliability diagram. The chart plots each bucket's realized accuracy
(y-axis) against the bucket's average stated confidence (x-axis). The ideal calibration
line is the 45-degree diagonal where accuracy equals confidence. Points above the diagonal
indicate underconfidence; points below indicate overconfidence. Bucket size can be encoded
as point radius.

Key response fields for the chart:
- `confidence_bucket_accuracy[].accuracy` -- y-axis value
- `confidence_bucket_accuracy[].avg_confidence` -- x-axis value
- `confidence_bucket_accuracy[].count` -- point size
- `expected_calibration_error` -- annotation label
- `overconfidence_by_bucket[].overconfidence` -- bar chart of per-bucket overconfidence

### GET /api/v1/predictions/pillar-attribution

**Response schema**: `PillarAttributionResponse`

Returns per-pillar correlation, bucketed accuracy, Brier scores, predictive lift,
missing rates, and usefulness ranking.

**iOS usage**: Pillar contribution waterfall chart. Each pillar is a bar whose height
represents its `correlation_with_outcome`. Bars are colored by sign (positive = bullGreen,
negative = bearRed). The `predictive_lift` value can be overlaid as a secondary marker
to show delta versus the fused baseline. The `usefulness_rank` determines left-to-right
ordering (rank 1 on the left).

Key response fields for the chart:
- `pillars[].correlation_with_outcome` -- bar height
- `pillars[].predictive_lift` -- delta marker
- `pillars[].missing_rate` -- opacity or annotation
- `pillars[].usefulness_rank` -- sort order

### GET /api/v1/predictions/model-versions

**Response schema**: `ModelVersionsResponse`

Returns per-model-version performance: hit rates across horizons, average returns,
Brier scores, calibration error, and the confidence-accuracy gap.

**iOS usage**: Version comparison table. Each row is a model version. Columns include
hit rates (7d, 30d, 90d), Brier score, calibration error, and the confidence gap.
The `confidence_realized_accuracy_gap` column is the most actionable -- positive values
mean the model was overconfident for that version, negative means underconfident.

Key response fields for the table:
- `versions[].model_version` -- row identifier
- `versions[].hit_rate_7d`, `hit_rate_30d`, `hit_rate_90d` -- hit rate columns
- `versions[].brier_score_30d` -- quality score
- `versions[].calibration_error_30d` -- calibration column
- `versions[].confidence_realized_accuracy_gap` -- overconfidence indicator

---

## 8. Known Limitations

### Small Sample Sizes in Early Buckets

The 0-50% and 90-100% buckets will have few predictions in early operation. Calibration
statistics in buckets with fewer than ~30 predictions are unreliable. The API returns
these values regardless, but iOS should annotate small-sample buckets or suppress them
from the reliability diagram until a minimum count threshold is met.

### SQLite Aggregation Precision

The backend uses SQLite in development. SQLite stores floats as IEEE 754 doubles and
performs aggregation without extended precision. For calibration metrics computed from
hundreds of predictions, this is adequate. At scale (tens of thousands of predictions),
the accumulated rounding in `AVG()` and `SUM()` operations may introduce drift on the
order of 1e-6 to 1e-4. This is well below the precision threshold for financial
calibration decisions.

### Outcome Data Availability Lag

Outcome data is populated by the nightly outcome tracker (`services/outcome_tracker.py`),
which uses yfinance to fetch historical prices. Three lag windows apply:

| Horizon | Data Available After | Implication |
|---------|---------------------|-------------|
| 7d | 7 calendar days + next nightly run | Short-term calibration updates within ~8 days |
| 30d | 30 calendar days + next nightly run | Primary calibration metric, ~31 day lag |
| 90d | 90 calendar days + next nightly run | Long-term calibration, significant wait |

Until a prediction matures, its `hit_direction_*` and `brier_score_*` columns remain NULL
and it is excluded from calibration calculations. New deployments will show no calibration
data until the first 7-day predictions mature.

### Market Regime Changes

Calibration metrics are computed across all market conditions. A model calibrated during a
bull market may appear miscalibrated during a correction, and vice versa. The API provides
`calibration_by_regime` groupings to help isolate regime-specific performance, but the
system does not yet adjust confidence scores based on detected regime shifts.

### HOLD Predictions Excluded from Hit Rate

Predictions with a `HOLD` recommendation have `pred_dir = 0` and are excluded from
directional hit rate and Brier score calculations. These predictions contribute to bucket
counts but not to accuracy or Brier metrics.

---

## 9. Next Steps Toward LightGBM Training

The calibration system is designed as the foundation for a supervised ML feedback loop.
The following steps outline the path from calibration analytics to trained model deployment.

### 9.1 Use Pillar Attribution to Identify Features

The `/pillar-attribution` endpoint reveals which confidence pillars actually predict
outcomes. Features with high positive correlation and low missing rates are candidates for
the LightGBM feature vector. Features with near-zero or negative correlation should be
investigated -- they may need transformation (log, rank, interaction terms) rather than
raw inclusion.

The `bucketed_accuracy` data for each pillar reveals whether the relationship is monotonic.
Non-monotonic pillars may benefit from binning or polynomial features in the model.

### 9.2 Build the Feature Vector

The initial LightGBM feature vector should include:

- The five pillar scores: `llm_confidence`, `quant_confidence`, `venn_abers_confidence`,
  `signal_agreement`, `ml_confidence`
- The fused `confidence_pct` (to let the model learn residual corrections)
- Market regime context (`regime_id`)
- Scan type (`scan_type`)
- Sector (via join with `StockUniverse`)
- Temporal features: day of week, month, days since last earnings

### 9.3 Use Brier Score as Training Loss

LightGBM supports custom objective functions. The Brier score decomposes cleanly into
a gradient-friendly form. Using Brier loss directly as the training objective ensures
the model optimizes for calibration, not just classification accuracy. This prevents
the common failure mode where a model achieves high AUC but poor calibration.

### 9.4 Retrain Trigger: N > 500 Per Model Version

The `model_version` column tracks which pipeline version produced each prediction.
Retraining should be triggered when:

1. A model version accumulates more than 500 matured predictions (with non-NULL
   `hit_direction_30d`)
2. The ECE for that version exceeds 0.10 (moderate miscalibration)
3. The `confidence_realized_accuracy_gap` is consistently positive (overconfident)

After retraining, the new model receives a new `model_version` string (e.g.,
`nivesh-v2.0-lgbm`), and the `/model-versions` endpoint enables direct A/B comparison
between the old heuristic and the new trained model.

### 9.5 Deployment Cycle

1. Accumulate 500+ matured predictions on the current `model_version`
2. Extract training data: pillar scores as features, `hit_direction_30d` as label
3. Train LightGBM with Brier loss, stratified k-fold cross-validation
4. Compare cross-validated ECE against the current heuristic's ECE
5. If the trained model improves ECE by more than 0.02, deploy with a new `model_version`
6. Set `ml_engine_mode` to `lgbm_trained` (via `get_ml_engine_mode()` in
   `confidence_fusion.py`)
7. Monitor the new version's calibration via `/model-versions` for regression

---

## File Reference

| File | Role |
|------|------|
| `services/prediction_calibration_service.py` | Calibration metrics, pillar attribution, model version analytics |
| `services/confidence_fusion.py` | Pillar fusion formula and weights |
| `services/outcome_tracker.py` | Nightly outcome backfill, Brier score computation |
| `schemas/prediction_calibration.py` | Pydantic response schemas |
| `routers/predictions.py` | API endpoint definitions |
| `models/db_models.py` (`AnalysisPrediction`) | ORM model with prediction inputs and outcome columns |
