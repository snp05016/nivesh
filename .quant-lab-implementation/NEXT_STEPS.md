# Quant Lab -- Next Steps

## Immediate (Pre-Merge)

1. **Deploy backend and verify ML signal endpoint with live ML engine.** Push the branch to the remote server, restart the backend, and confirm the `/api/v1/stocks/{symbol}/ml-signal` endpoint returns valid data when the ML engine is running with a loaded model.

## Short-Term (Post-Merge)

2. **Add SHAP-based feature importance to ML engine for feature_drivers.** The current ML engine may not expose per-prediction feature importance. Integrate SHAP (SHapley Additive exPlanations) into the LightGBM prediction path to provide the `feature_drivers` array with meaningful importance scores.

3. **Accumulate enough predictions for meaningful calibration data.** Run the prediction pipeline across the stock universe for several weeks to build a sufficient sample for calibration curves, alpha validation, and regime breakdown to produce statistically significant results.

4. **Implement alpha validation service with historical prediction replay.** Build a service that replays historical predictions against realized price movements to compute alpha, hit rate, and Sharpe ratio metrics for the alpha validation section.

## Medium-Term

5. **Add strategy sweep parameter storage for user presets.** Allow users to save their preferred strategy sweep configurations (lookback periods, thresholds, cost assumptions) so they can quickly re-run analyses with their preferred settings.

6. **Consider adding Quant Lab entry point from Settings or Developer menu.** Currently accessible only through the ML Signal Card on a stock profile. A standalone entry point would allow exploration of system-wide model metrics without needing a specific stock context.

7. **Add SwiftUI previews for all Quant Lab components.** Create preview providers with mock data for StockMLSignalCard, QuantLabView, and each section component to enable rapid UI iteration in Xcode Canvas without requiring live API data.
