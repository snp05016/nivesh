# Quant Lab -- iOS Files Changed

## New Files (5)

### 1. Models/QuantLabModels.swift
Data models for the Quant Lab feature. Includes `MLSignalResponse`, `FeatureDriver`, `CalibrationData`, `PillarAttribution`, `ModelVersion`, `AlphaValidation`, `StrategySweepResult`, `RegimeBreakdown`, and `CostSensitivity` structs. All conform to `Codable` and `Identifiable` where appropriate.

### 2. Services/QuantLabAPIClient.swift
Dedicated API client for all Quant Lab endpoints. Handles the 8 API calls (ML signal, calibration, pillar attribution, model versions, alpha validation, strategy sweep, regime breakdown, cost sensitivity). Uses the existing `NetworkManager` infrastructure with proper error handling and timeout configuration.

### 3. ViewModels/QuantLabViewModel.swift
`@Observable` view model managing state for the full Quant Lab view. Coordinates loading across all 9 sections with independent loading/error states per section. Provides computed properties for formatted display values using `IndianFormatter` and `Theme` tokens.

### 4. Views/StockProfile/StockMLSignalCard.swift
Compact ML signal card displayed in the StockProfileView Overview tab. Shows directional signal with color coding (Theme.bullGreen / Theme.bearRed / Theme.holdAmber), confidence bar, model version badge, and top 3 feature drivers. Uses `.banknoteCard()` modifier, `EKPressStyle`, and `HapticManager.selection()`. Tapping opens the full QuantLabView.

### 5. Views/QuantLab/QuantLabView.swift
Full-screen research view with 9 collapsible sections in a ScrollView + LazyVStack. Each section uses `.banknoteCard()` with `GuillocheDivider()` separators. Includes a raw JSON inspector section for developer debugging. All spacing uses Theme.Spacing tokens, all colors use Theme tokens, all typography uses Theme font methods.

---

## Modified Files (2)

### 1. Views/StockProfile/StockProfileView.swift
Added `StockMLSignalCard` to the Overview tab section, positioned after the price summary and before the analyst section. Card is conditionally shown when ML signal data is available. Navigation destination registered for QuantLabView.

### 2. ViewModels/StockProfileViewModel.swift
Added `mlSignal` published property and `fetchMLSignal(symbol:)` method. Called during the existing data loading flow. Errors are silently handled (card simply does not appear if ML signal is unavailable).
