# Quant Lab API Contracts

All endpoints used by the Quant Lab feature.

---

## 1. GET /api/v1/stocks/{symbol}/ml-signal

**Status:** NEW

Proxies to the ML engine to retrieve the current ML prediction for a stock.

**Path Parameters:**
- `symbol` (string, required) -- Stock ticker symbol (e.g., RELIANCE, TCS)

**Response (200):**
```json
{
  "symbol": "RELIANCE",
  "direction": "bullish",
  "confidence": 0.73,
  "model_version": "lgbm_v2.1",
  "feature_drivers": [
    {"name": "RSI_14", "importance": 0.18},
    {"name": "MACD_signal", "importance": 0.15},
    {"name": "volume_ratio", "importance": 0.12}
  ],
  "generated_at": "2026-06-24T10:30:00Z"
}
```

**Error Responses:**
- 404: Symbol not found or ML engine unavailable
- 504: ML engine timeout

---

## 2. GET /api/v1/predictions/calibration

**Status:** EXISTING

Returns calibration curve data showing predicted vs. actual outcome frequencies.

**Query Parameters:**
- `model_version` (string, optional) -- Filter by model version
- `lookback_days` (int, optional, default 90) -- Historical window

**Response (200):**
```json
{
  "bins": [
    {"predicted_prob": 0.1, "actual_freq": 0.08, "count": 42},
    {"predicted_prob": 0.2, "actual_freq": 0.19, "count": 67}
  ],
  "brier_score": 0.12,
  "model_version": "lgbm_v2.1"
}
```

---

## 3. GET /api/v1/predictions/pillar-attribution

**Status:** EXISTING

Returns contribution breakdown by analysis pillar (technical, fundamental, sentiment, etc.).

**Query Parameters:**
- `symbol` (string, optional) -- Filter by symbol
- `model_version` (string, optional) -- Filter by model version

**Response (200):**
```json
{
  "attributions": [
    {"pillar": "technical", "weight": 0.35, "signal": "bullish"},
    {"pillar": "fundamental", "weight": 0.28, "signal": "neutral"},
    {"pillar": "sentiment", "weight": 0.22, "signal": "bearish"},
    {"pillar": "macro", "weight": 0.15, "signal": "neutral"}
  ]
}
```

---

## 4. GET /api/v1/predictions/model-versions

**Status:** EXISTING

Returns the registry of active and historical model versions.

**Response (200):**
```json
{
  "versions": [
    {
      "version": "lgbm_v2.1",
      "trained_at": "2026-06-20T08:00:00Z",
      "features_count": 158,
      "training_samples": 45000,
      "validation_sharpe": 1.42,
      "status": "active"
    }
  ]
}
```

---

## 5. POST /api/v1/backtests/alpha-validation

**Status:** EXISTING

Runs alpha validation on accumulated predictions against realized outcomes.

**Request Body:**
```json
{
  "model_version": "lgbm_v2.1",
  "benchmark": "NIFTY50",
  "lookback_days": 180
}
```

**Response (200):**
```json
{
  "alpha_bps": 42,
  "sharpe_ratio": 1.15,
  "hit_rate": 0.58,
  "sample_size": 312,
  "p_value": 0.03
}
```

---

## 6. GET /api/v1/backtests/strategy-sweep

**Status:** EXISTING

Returns parameter sweep results across strategy configurations.

**Query Parameters:**
- `strategy` (string, optional) -- Strategy type
- `param_grid` (string, optional) -- JSON-encoded parameter ranges

**Response (200):**
```json
{
  "sweep_results": [
    {
      "params": {"lookback": 20, "threshold": 0.6},
      "sharpe": 1.3,
      "max_drawdown": -0.08,
      "total_return": 0.18
    }
  ]
}
```

---

## 7. POST /api/v1/backtests/regime-breakdown

**Status:** EXISTING

Segments backtest performance by market regime (bull, bear, sideways, volatile).

**Request Body:**
```json
{
  "model_version": "lgbm_v2.1",
  "regime_method": "hmm"
}
```

**Response (200):**
```json
{
  "regimes": [
    {"regime": "bull", "sharpe": 1.8, "hit_rate": 0.65, "sample_size": 120},
    {"regime": "bear", "sharpe": 0.4, "hit_rate": 0.52, "sample_size": 80},
    {"regime": "sideways", "sharpe": 1.1, "hit_rate": 0.57, "sample_size": 95}
  ]
}
```

---

## 8. GET /api/v1/backtests/cost-sensitivity

**Status:** EXISTING (typed response added)

Returns the impact of varying transaction cost assumptions on strategy performance.

**Query Parameters:**
- `strategy` (string, optional) -- Strategy identifier
- `cost_bps_range` (string, optional) -- Comma-separated cost levels in basis points

**Response (200):**
```json
{
  "cost_levels": [
    {"cost_bps": 5, "net_sharpe": 1.35, "net_return": 0.17, "turnover": 2.1},
    {"cost_bps": 10, "net_sharpe": 1.20, "net_return": 0.14, "turnover": 2.1},
    {"cost_bps": 20, "net_sharpe": 0.95, "net_return": 0.09, "turnover": 2.1}
  ]
}
```
