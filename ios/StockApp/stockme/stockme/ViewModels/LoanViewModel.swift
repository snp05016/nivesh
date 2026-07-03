import SwiftUI
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
        return result.sorted { $0.interestRatePct < $1.interestRatePct }
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

    @Published var amount: Double
    @Published var tenureMonths: Int
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
    /// services/loan_marketplace_service.py's KYC gate): we send this
    /// device's vendor identifier as `device_id` so the mock device-binding
    /// check in services/kyc_consent_service.py can verify it.
    func submit() async {
        guard kycConsent else {
            submissionError = "Please provide KYC consent to continue."
            return
        }
        isSubmitting = true
        submissionError = nil

        guard let deviceId = UIDevice.current.identifierForVendor?.uuidString else {
            submissionError = "Could not identify device for binding."
            isSubmitting = false
            return
        }

        // 1. Persist the KYC consent
        do {
            _ = try await NetworkManager.shared.grantConsent(type: "credit_check", granted: true)
        } catch {
            submissionError = "Failed to record KYC consent. Please try again."
            isSubmitting = false
            return
        }

        // 2. Verify or Bind the device
        do {
            let verifyResp = try await NetworkManager.shared.verifyDeviceBinding(deviceId: deviceId)
            if !verifyResp.verified {
                _ = try await NetworkManager.shared.bindDevice(deviceId: deviceId, isPrimary: true)

                // Verify again to ensure the bind was accepted by the backend gate
                let secondVerify = try await NetworkManager.shared.verifyDeviceBinding(deviceId: deviceId)
                if !secondVerify.verified {
                    submissionError = "Device binding rejected. Please use your primary registered device."
                    isSubmitting = false
                    return
                }
            }
        } catch {
            // Fallback for fraud checks/network failures
            submissionError = "Device binding failed. Please use your primary registered device."
            isSubmitting = false
            return
        }

        // 3. Submit the loan application after prerequisites are confirmed
        let requestBody = LoanApplicationRequest(
            loanOfferId: offer.id,
            requestedAmount: amount,
            requestedTenureMonths: tenureMonths,
            deviceId: deviceId
        )
        do {
            submittedApplication = try await NetworkManager.shared.submitLoanApplication(requestBody)
        } catch {
            submissionError = "Couldn't submit your application. Please try again."
        }
        isSubmitting = false
    }

    /// "Request Disbursement (Demo)" action — only meaningful once the mock
    /// application has reached "approved". MOCK DATA - simulated for demo
    /// purposes, not a real integration; no real funds are ever moved.
    func requestDisbursement() async {
        guard let applicationId = submittedApplication?.id else { return }
        isRequestingDisbursement = true
        disbursementError = nil
        do {
            disbursement = try await NetworkManager.shared.requestDisbursement(applicationId: applicationId)
        } catch {
            disbursementError = "Couldn't request disbursement. Please try again."
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
