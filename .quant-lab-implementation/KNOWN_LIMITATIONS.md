# Quant Lab -- Known Limitations

## 1. Feature Drivers Dependency

Feature drivers (e.g., RSI_14, MACD_signal) depend on the ML engine providing them in the prediction response. Not all model versions expose feature importance values. When absent, the StockMLSignalCard and QuantLabView gracefully hide the feature drivers section rather than showing empty data.

## 2. Backtest Endpoints -- Insufficient Historical Data

The backtest endpoints (strategy sweep, regime breakdown, alpha validation) may return errors or empty results if insufficient historical prediction data exists. This is expected during the early rollout period before the system has accumulated enough predictions.

## 3. Alpha Validation -- Prediction Accumulation Required

Alpha validation requires a meaningful volume of accumulated predictions with realized outcomes to produce statistically significant metrics. The `sample_size` and `p_value` fields in the response indicate whether results are reliable. The iOS view displays a warning when sample size is below the significance threshold.

## 4. Cost Sensitivity -- Estimated Costs

The cost sensitivity presets (5, 10, 20 bps) are estimates based on typical Indian equity market execution costs. They do not reflect live execution costs from any specific broker. Actual slippage, impact costs, and STT/GST will vary by broker, order size, and market conditions.

## 5. iOS Compile Verification -- Xcode Prohibition

Per AGENTS.md section 6.2, the iOS app cannot be compile-verified without Xcode. All SwiftUI code follows established patterns, uses correct Theme tokens, and adheres to the Banknote Aesthetic, but syntax errors can only be caught when the project is opened in Xcode.

## 6. ML Engine Availability

The ML signal endpoint depends on the ML engine being reachable. If the ML engine is down or the model is not loaded, the endpoint returns a 504 or 404 error. The iOS layer handles this gracefully by not showing the ML Signal Card.

## 7. Calibration Data Freshness

Calibration curves reflect historical prediction accuracy and may lag behind model updates. After a new model version is deployed, the calibration data will initially reflect the previous model until enough new predictions accumulate.
