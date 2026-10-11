import SwiftUI
import Combine
import UIKit

/// Drives FixedDepositListView — fetches mock FD schemes and exposes a
/// comparison-friendly sorted/filterable list, mirroring LoanViewModel's
/// fetch/error/loading shape. MOCK DATA - simulated for demo purposes, not a
/// real integration; no real NBFC FD issuer data.
@MainActor
class FixedDepositViewModel: ObservableObject {
    enum SortOrder: String, CaseIterable, Identifiable {
        case rateDescending = "Highest Rate"
        case tenureAscending = "Shortest Tenure"
        case tenureDescending = "Longest Tenure"

        var id: String { rawValue }
    }

    @Published var allSchemes: [FDSchemeDTO] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var sortOrder: SortOrder = .rateDescending
    @Published var minTenureMonths: Double = 0
    @Published var maxTenureMonths: Double = 120 // 10 years ceiling for the tenure filter

    var filteredSchemes: [FDSchemeDTO] {
        var result = allSchemes.filter { $0.isActive }
        if minTenureMonths > 0 {
            result = result.filter { Double($0.maxTenureMonths) >= minTenureMonths }
        }
        if maxTenureMonths < 120 {
            result = result.filter { Double($0.minTenureMonths) <= maxTenureMonths }
        }
        switch sortOrder {
        case .rateDescending: return result.sorted { $0.interestRatePct > $1.interestRatePct }
        case .tenureAscending: return result.sorted { $0.minTenureMonths < $1.minTenureMonths }
        case .tenureDescending: return result.sorted { $0.maxTenureMonths > $1.maxTenureMonths }
        }
    }

    func fetchSchemes() async {
        isLoading = true
        errorMessage = nil
        do {
            let minTenure = minTenureMonths > 0 ? Int(minTenureMonths) : nil
            let maxTenure = maxTenureMonths < 120 ? Int(maxTenureMonths) : nil
            allSchemes = try await NetworkManager.shared.fetchFDSchemes(minTenure: minTenure, maxTenure: maxTenure)
            if allSchemes.isEmpty {
                errorMessage = "Couldn't load FD schemes. Pull to retry."
            }
        } catch {
            errorMessage = "Couldn't load FD schemes. Pull to retry."
        }
        isLoading = false
    }

    func clearFilters() {
        minTenureMonths = 0
        maxTenureMonths = 120
        sortOrder = .rateDescending
    }
}

/// Drives FixedDepositCalculatorView (standalone) and the live preview inside
/// FixedDepositBookingView. Tries the backend calculator first and falls
/// back to an identical local compound-interest formula so the preview
/// always works even if the network call is slow/unavailable. MOCK DATA -
/// simulated for demo purposes, not a real integration.
@MainActor
class FixedDepositCalculatorViewModel: ObservableObject {
    @Published var principal: Double
    @Published var tenureMonths: Int
    @Published var interestRatePct: Double

    @Published var result: FDCalculatorResponse? = nil
    @Published var isCalculating: Bool = false

    init(principal: Double = 1_00_000, tenureMonths: Int = 12, interestRatePct: Double = 7.0) {
        self.principal = principal
        self.tenureMonths = tenureMonths
        self.interestRatePct = interestRatePct
    }

    func recalculate() async {
        isCalculating = true
        if let backendResult = try? await NetworkManager.shared.calculateFDMaturity(
            principal: principal, tenure: tenureMonths, rate: interestRatePct
        ) {
            result = backendResult
        } else {
            result = Self.computeLocally(principal: principal, tenureMonths: tenureMonths, ratePct: interestRatePct)
        }
        isCalculating = false
    }

    /// Quarterly-compounded FD maturity projection — mirrors the shape the
    /// backend's own calculator is expected to return, used purely as an
    /// offline fallback so the preview never goes blank.
    static func computeLocally(principal: Double, tenureMonths: Int, ratePct: Double) -> FDCalculatorResponse {
        let years = Double(tenureMonths) / 12.0
        let n = 4.0 // quarterly compounding
        let r = ratePct / 100.0
        let maturity = principal * pow(1 + r / n, n * years)
        let interest = maturity - principal
        return FDCalculatorResponse(maturityAmount: maturity, interestEarned: interest)
    }
}

/// Drives FixedDepositBookingView's amount/tenure input, live calculator
/// preview, payment method picker, and (mock) booking submission. Surfaces
/// device_id (same UIDevice.identifierForVendor source LoanApplicationViewModel
/// uses) and holds the booking status/decisionReason for UI feedback. MOCK
/// DATA - simulated for demo purposes, not a real integration; neither UPI
/// nor Net Banking collects any real payment.
@MainActor
class FixedDepositBookingViewModel: ObservableObject {
    let scheme: FDSchemeDTO

    // Changing what's sent starts a new intent, so it gets a fresh idempotency key.
    @Published var principal: Double { didSet { bookingKey = nil } }
    @Published var tenureMonths: Int { didSet { bookingKey = nil } }
    @Published var paymentMethod: FDPaymentMethod = .upi { didSet { bookingKey = nil } }

    let calculator: FixedDepositCalculatorViewModel

    @Published var isSubmitting: Bool = false
    @Published var submissionError: String? = nil
    @Published var bookingResult: FDBookingResponse? = nil

    /// IOSCORE-17: one Idempotency-Key per booking intent, reused on retry after
    /// a failure (the first attempt may have committed), cleared on success.
    private var bookingKey: String?

    init(scheme: FDSchemeDTO) {
        self.scheme = scheme
        self.principal = scheme.minAmount
        self.tenureMonths = scheme.minTenureMonths
        self.calculator = FixedDepositCalculatorViewModel(
            principal: scheme.minAmount,
            tenureMonths: scheme.minTenureMonths,
            interestRatePct: scheme.interestRatePct
        )
    }

    var isAmountValid: Bool {
        principal >= scheme.minAmount && principal <= scheme.maxAmount
    }

    var isTenureValid: Bool {
        tenureMonths >= scheme.minTenureMonths && tenureMonths <= scheme.maxTenureMonths
    }

    var canSubmit: Bool { isAmountValid && isTenureValid && !isSubmitting }

    /// Whether the last booking attempt failed closed on a KYC/device-binding
    /// gate — used to steer the user toward Account Settings rather than a
    /// blind retry. This view never calls /api/kyc/... directly; it only
    /// surfaces the decision_reason text the backend already returned.
    var requiresAccountSettingsFollowUp: Bool {
        guard let bookingResult, bookingResult.parsedStatus == .failed else { return false }
        guard let reason = bookingResult.decisionReason?.lowercased() else { return false }
        return reason.contains("sim binding") || reason.contains("device") || reason.contains("kyc")
    }

    func syncCalculatorInputs() {
        calculator.principal = principal
        calculator.tenureMonths = tenureMonths
        calculator.interestRatePct = scheme.interestRatePct
    }

    func submit() async {
        guard canSubmit else { return }
        isSubmitting = true
        submissionError = nil
        bookingResult = nil

        guard let deviceId = UIDevice.current.identifierForVendor?.uuidString else {
            submissionError = "Couldn't identify this device. Please try again."
            isSubmitting = false
            return
        }

        let requestBody = FDBookingRequest(
            schemeId: scheme.id,
            principalAmount: principal,
            tenureMonths: tenureMonths,
            paymentMethod: paymentMethod.rawValue,
            deviceId: deviceId
        )
        let key = bookingKey ?? UUID().uuidString
        bookingKey = key
        do {
            bookingResult = try await NetworkManager.shared.bookFixedDeposit(requestBody, idempotencyKey: key)
            bookingKey = nil
        } catch {
            submissionError = error.moneyActionMessage(fallback: "Couldn't submit your booking. Please try again.")
        }
        isSubmitting = false
    }
}
