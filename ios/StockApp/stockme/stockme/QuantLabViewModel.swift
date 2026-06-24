import Foundation
import SwiftUI

@MainActor
class QuantLabViewModel: ObservableObject {
    let symbol: String

    // MARK: - ML Signal

    @Published var mlSignal: MLSignalResponse?
    @Published var mlSignalLoading = false
    @Published var mlSignalError: String?

    // MARK: - Calibration

    @Published var calibration: CalibrationResponse?
    @Published var calibrationLoading = false
    @Published var calibrationError: String?

    // MARK: - Pillar Attribution

    @Published var pillarAttribution: PillarAttributionResponse?
    @Published var pillarAttributionLoading = false
    @Published var pillarAttributionError: String?

    // MARK: - Model Versions

    @Published var modelVersions: ModelVersionsResponse?
    @Published var modelVersionsLoading = false
    @Published var modelVersionsError: String?

    // MARK: - Alpha Validation

    @Published var alphaValidation: BacktestResult?
    @Published var alphaValidationLoading = false
    @Published var alphaValidationError: String?

    // MARK: - Strategy Sweep

    @Published var strategySweep: StrategySweepResponse?
    @Published var strategySweepLoading = false
    @Published var strategySweepError: String?

    // MARK: - Regime Breakdown

    @Published var regimeBreakdown: RegimeBreakdownResponse?
    @Published var regimeBreakdownLoading = false
    @Published var regimeBreakdownError: String?

    // MARK: - Cost Sensitivity

    @Published var costSensitivity: CostSensitivityResponse?
    @Published var costSensitivityLoading = false
    @Published var costSensitivityError: String?

    init(symbol: String) {
        self.symbol = symbol
    }

    // MARK: - Load All

    func loadAll() async {
        // Load ML signal first (fast), then others in parallel
        await fetchMLSignal()

        async let cal: () = fetchCalibration()
        async let pil: () = fetchPillarAttribution()
        async let mod: () = fetchModelVersions()
        async let alp: () = fetchAlphaValidation()
        async let str: () = fetchStrategySweep()
        async let reg: () = fetchRegimeBreakdown()
        async let cos: () = fetchCostSensitivity()

        _ = await (cal, pil, mod, alp, str, reg, cos)
    }

    // MARK: - ML Signal

    func fetchMLSignal() async {
        mlSignalLoading = true
        mlSignalError = nil
        do {
            mlSignal = try await NetworkManager.shared.fetchMLSignal(symbol: symbol)
        } catch {
            mlSignalError = error.localizedDescription
        }
        mlSignalLoading = false
    }

    // MARK: - Calibration

    func fetchCalibration() async {
        calibrationLoading = true
        calibrationError = nil
        do {
            calibration = try await NetworkManager.shared.fetchCalibration()
        } catch {
            calibrationError = error.localizedDescription
        }
        calibrationLoading = false
    }

    // MARK: - Pillar Attribution

    func fetchPillarAttribution() async {
        pillarAttributionLoading = true
        pillarAttributionError = nil
        do {
            pillarAttribution = try await NetworkManager.shared.fetchPillarAttribution()
        } catch {
            pillarAttributionError = error.localizedDescription
        }
        pillarAttributionLoading = false
    }

    // MARK: - Model Versions

    func fetchModelVersions() async {
        modelVersionsLoading = true
        modelVersionsError = nil
        do {
            modelVersions = try await NetworkManager.shared.fetchModelVersions()
        } catch {
            modelVersionsError = error.localizedDescription
        }
        modelVersionsLoading = false
    }

    // MARK: - Alpha Validation

    func fetchAlphaValidation() async {
        alphaValidationLoading = true
        alphaValidationError = nil
        do {
            alphaValidation = try await NetworkManager.shared.fetchAlphaValidation()
        } catch {
            alphaValidationError = error.localizedDescription
        }
        alphaValidationLoading = false
    }

    // MARK: - Strategy Sweep

    func fetchStrategySweep() async {
        strategySweepLoading = true
        strategySweepError = nil
        do {
            strategySweep = try await NetworkManager.shared.fetchStrategySweep()
        } catch {
            strategySweepError = error.localizedDescription
        }
        strategySweepLoading = false
    }

    // MARK: - Regime Breakdown

    func fetchRegimeBreakdown() async {
        regimeBreakdownLoading = true
        regimeBreakdownError = nil
        do {
            regimeBreakdown = try await NetworkManager.shared.fetchRegimeBreakdown()
        } catch {
            regimeBreakdownError = error.localizedDescription
        }
        regimeBreakdownLoading = false
    }

    // MARK: - Cost Sensitivity

    func fetchCostSensitivity() async {
        costSensitivityLoading = true
        costSensitivityError = nil
        do {
            costSensitivity = try await NetworkManager.shared.fetchCostSensitivity()
        } catch {
            costSensitivityError = error.localizedDescription
        }
        costSensitivityLoading = false
    }
}
