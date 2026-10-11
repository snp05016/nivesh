import SwiftUI
import Combine
import UIKit

/// Drives LoanMarketplaceView — fetches mock loan offers and applies
/// type/amount/tenure filters client-side, mirroring MutualFundViewModel's
/// fetch/error/loading shape. MOCK DATA - simulated for demo purposes,
/// not a real integration; no real NBFC/credit-bureau data.
@MainActor
class LoanViewModel: ObservableObject {
    @Published var selectedLoanType: LoanType? = nil
    @Published var minAmount: Double = 0
    @Published var maxAmount: Double = 1_00_00_000 // 1 Cr ceiling for the amount slider
    @Published var maxTenureMonths: Double = 360   // 30 years ceiling for the tenure slider

    @Published var allOffers: [LoanOfferDTO] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    var filteredOffers: [LoanOfferDTO] {
        var result = allOffers
        if let type = selectedLoanType {
            result = result.filter { $0.parsedLoanType == type }
        }
        if minAmount > 0 {
            result = result.filter { $0.maxAmount >= minAmount }
        }
        if maxAmount < 1_00_00_000 {
            result = result.filter { $0.minAmount <= maxAmount }
        }
        if maxTenureMonths < 360 {
            result = result.filter { Double($0.minTenureMonths) <= maxTenureMonths }
        }
        // REG-05: rank by all-in cost (max APR), not the headline rate.
        return result.sorted { ($0.maxAprPct ?? $0.interestRatePct) < ($1.maxAprPct ?? $1.interestRatePct) }
    }

    func fetchOffers() async {
        isLoading = true
        errorMessage = nil
        do {
            allOffers = try await NetworkManager.shared.fetchLoanOffers()
            if allOffers.isEmpty {
                errorMessage = "Couldn't load loan offers. Pull to retry."
            }
        } catch {
            errorMessage = "Couldn't load loan offers. Pull to retry."
        }
        isLoading = false
    }

    func clearFilters() {
        selectedLoanType = nil
        minAmount = 0
        maxAmount = 1_00_00_000
        maxTenureMonths = 360
    }
}

/// Drives LoanApplicationView's multi-step form (amount → tenure → purpose
/// → KYC consent) and submits the (mock) application. MOCK DATA - simulated
/// for demo purposes, not a real integration; the KYC consent checkbox does
/// not trigger any real e-KYC/document-upload flow.
@MainActor
class LoanApplicationViewModel: ObservableObject {
    let offer: LoanOfferDTO

    // Changing what's sent starts a new intent, so it gets a fresh idempotency key.
    @Published var amount: Double { didSet { submitKey = nil } }
    @Published var tenureMonths: Int { didSet { submitKey = nil } }
    @Published var purpose: String = ""
    @Published var kycConsent: Bool = false

    @Published var currentStep: Int = 0
    let totalSteps = 4 // amount, tenure, purpose, KYC consent + review

    @Published var isSubmitting: Bool = false
    @Published var submissionError: String? = nil
    @Published var submittedApplication: LoanApplicationResponse? = nil

    // MARK: - Mock Disbursement
    //
    // MOCK DATA - simulated for demo purposes, not a real integration. No
    // real funds are ever moved and no real NBFC is contacted. Only
    // meaningful once submittedApplication.parsedStatus == .approved.
    @Published var disbursement: DisbursementDTO? = nil
    @Published var isRequestingDisbursement: Bool = false
    @Published var disbursementError: String? = nil

    /// IOSCORE-17: one Idempotency-Key per user intent, reused on retry after a
    /// failure (the first attempt may have committed), cleared on success.
    private var submitKey: String?
    private var disburseKey: String?

    init(offer: LoanOfferDTO) {
        self.offer = offer
        self.amount = offer.minAmount
        self.tenureMonths = offer.minTenureMonths
    }

    var canAdvance: Bool {
        switch currentStep {
        case 0: return amount >= offer.minAmount && amount <= offer.maxAmount
        case 1: return tenureMonths >= offer.minTenureMonths && tenureMonths <= offer.maxTenureMonths
        case 2: return !purpose.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case 3: return kycConsent
        default: return false
        }
    }

    func advance() {
        guard canAdvance, currentStep < totalSteps - 1 else { return }
        currentStep += 1
    }

    func goBack() {
        guard currentStep > 0 else { return }
        currentStep -= 1
    }

    /// Submits the (mock) application. `purpose` is UI-only and not sent —
    /// backend/routers/finance.py's SubmitLoanApplicationRequest has no
    /// `purpose` field. KYC gating happens server-side (see
    /// services/loan_marketplace_service.py's KYC gate), which needs an
    /// active "credit_check" consent and a verified device binding. So the
    /// consent the user just ticked is recorded server-side and this device
    /// is bound before the application is sent with this device's vendor
    /// identifier as `device_id`.
    func submit() async {
        guard kycConsent else {
            submissionError = "Please provide KYC consent to continue."
            return
        }
        isSubmitting = true
        submissionError = nil
        defer { isSubmitting = false }

        guard let deviceId = UIDevice.current.identifierForVendor?.uuidString else {
            submissionError = "Could not identify this device for KYC binding."
            return
        }

        // 1. Record the consent the user just gave.
        do {
            _ = try await NetworkManager.shared.grantConsent(type: "credit_check", granted: true)
        } catch {
            submissionError = "Failed to record KYC consent. Please try again."
            return
        }

        // 2. Verify this device, binding it first if needed.
        do {
            let firstCheck = try await NetworkManager.shared.verifyDeviceBinding(deviceId: deviceId)
            if !firstCheck.verified {
                _ = try await NetworkManager.shared.bindDevice(deviceId: deviceId, isPrimary: true)
                let secondCheck = try await NetworkManager.shared.verifyDeviceBinding(deviceId: deviceId)
                guard secondCheck.verified else {
                    submissionError = "Device binding rejected. Please use your primary registered device."
                    return
                }
            }
        } catch NetworkError.serverError(409, let message?) {
            // A mock fraud heuristic rejected the bind.
            submissionError = message
            return
        } catch {
            submissionError = "Device binding failed. Please try again."
            return
        }

        // 3. Submit the application.
        let requestBody = LoanApplicationRequest(
            loanOfferId: offer.id,
            requestedAmount: amount,
            requestedTenureMonths: tenureMonths,
            deviceId: deviceId
        )
        let key = submitKey ?? UUID().uuidString
        submitKey = key
        do {
            submittedApplication = try await NetworkManager.shared.submitLoanApplication(requestBody, idempotencyKey: key)
            submitKey = nil
        } catch {
            submissionError = error.moneyActionMessage(fallback: "Couldn't submit your application. Please try again.")
        }
    }

    /// "Request Disbursement (Demo)" action — only meaningful once the mock
    /// application has reached "approved". MOCK DATA - simulated for demo
    /// purposes, not a real integration; no real funds are ever moved.
    func requestDisbursement() async {
        guard let applicationId = submittedApplication?.id else { return }
        isRequestingDisbursement = true
        disbursementError = nil
        let key = disburseKey ?? UUID().uuidString
        disburseKey = key
        do {
            disbursement = try await NetworkManager.shared.requestDisbursement(applicationId: applicationId, idempotencyKey: key)
            disburseKey = nil
        } catch NetworkError.serverError(409, let message?) {
            // Definitive business-rule rejection: the next attempt is a new request.
            disburseKey = nil
            disbursementError = message
        } catch {
            disbursementError = error.moneyActionMessage(fallback: "Couldn't request disbursement. Please try again.")
        }
        isRequestingDisbursement = false
    }

    /// Polls the mock disbursement status, e.g. on view appear/refresh for
    /// an already-approved application.
    func refreshDisbursementStatus() async {
        guard let applicationId = submittedApplication?.id else { return }
        do {
            disbursement = try await NetworkManager.shared.fetchDisbursementStatus(applicationId: applicationId)
        } catch {
            // Non-fatal — no disbursement requested yet is an expected 404.
        }
    }
}
