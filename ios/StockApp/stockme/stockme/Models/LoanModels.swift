import Foundation

// MARK: - Loan Marketplace Domain Models
//
// MOCK DATA - simulated for demo purposes, not a real integration. Every
// "lender" and "NBFC" name below is fictional/demo-labeled, no real credit
// bureau (CIBIL/Experian) pull happens, no government ID (PAN/Aadhaar) is
// collected, and application submission just writes a row to a mock table
// on the demo backend. Mirrors the (mock) backend/routers/loans.py
// LoanOfferResponse / LoanApplicationResponse shapes — see
// NetworkManager+Finance.swift for the exact endpoints these decode from.

/// Loan product categories shown in the marketplace filter chips.
enum LoanType: String, Codable, CaseIterable, Identifiable {
    case personal = "personal"
    case home = "home"
    case car = "car"
    case gold = "gold"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .personal: return "Personal Loan"
        case .home: return "Home Loan"
        case .car: return "Car Loan"
        case .gold: return "Gold Loan"
        }
    }

    var icon: String {
        switch self {
        case .personal: return "person.crop.circle.fill"
        case .home: return "house.fill"
        case .car: return "car.fill"
        case .gold: return "circle.hexagongrid.fill"
        }
    }
}

/// A single loan offer card in the marketplace. MOCK DATA — the "lender"
/// is a demo NBFC persona, not a real financial institution.
/// Mirrors GET /api/finance/loan-offers (backend/routers/finance.py
/// LoanOfferResponse — a single flat interest_rate_pct, not a min/max range).
struct LoanOfferDTO: Codable, Identifiable, Equatable {
    let id: Int
    let nbfcName: String
    let loanType: String
    let minAmount: Double
    let maxAmount: Double
    let interestRatePct: Double
    let minTenureMonths: Int
    let maxTenureMonths: Int
    let minCreditScore: Int
    let processingFeePct: Double

    enum CodingKeys: String, CodingKey {
        case id
        case nbfcName = "nbfc_name"
        case loanType = "loan_type"
        case minAmount = "min_amount"
        case maxAmount = "max_amount"
        case interestRatePct = "interest_rate_pct"
        case minTenureMonths = "min_tenure_months"
        case maxTenureMonths = "max_tenure_months"
        case minCreditScore = "min_credit_score"
        case processingFeePct = "processing_fee_pct"
    }

    var parsedLoanType: LoanType { LoanType(rawValue: loanType) ?? .personal }

    var interestRateDisplay: String {
        String(format: "%.2f%% p.a.", interestRatePct)
    }

    var amountRangeDisplay: String {
        "\(IndianFormatter.formatLakhsCrores(minAmount)) – \(IndianFormatter.formatLakhsCrores(maxAmount))"
    }

    var tenureRangeDisplay: String {
        "\(minTenureMonths / 12)–\(maxTenureMonths / 12) yrs"
    }
}

/// Request body for POST /api/finance/loan-applications. Mirrors
/// backend/routers/finance.py SubmitLoanApplicationRequest exactly — the
/// backend has no `purpose` field (UI-only, kept client-side for the
/// multi-step form but never transmitted) and no `kyc_consent` boolean
/// (KYC gating happens server-side via kyc_consent_service, keyed off
/// device_id — see services/loan_marketplace_service.py's KYC gate).
/// MOCK DATA - simulated for demo purposes, not a real integration.
struct LoanApplicationRequest: Codable {
    let loanOfferId: Int
    let requestedAmount: Double
    let requestedTenureMonths: Int
    let deviceId: String?

    enum CodingKeys: String, CodingKey {
        case loanOfferId = "loan_offer_id"
        case requestedAmount = "requested_amount"
        case requestedTenureMonths = "requested_tenure_months"
        case deviceId = "device_id"
    }
}

/// Lifecycle states for a submitted (mock) loan application. Mirrors the
/// `status` values enforced by the ck_loan_application_status CHECK
/// constraint in backend/models/db_models.py.
enum LoanApplicationStatus: String, Codable {
    case submitted = "submitted"
    case underReview = "under_review"
    case approved = "approved"
    case rejected = "rejected"
    case disbursed = "disbursed"

    var displayName: String {
        switch self {
        case .submitted: return "Submitted"
        case .underReview: return "Under Review"
        case .approved: return "Approved"
        case .rejected: return "Rejected"
        case .disbursed: return "Disbursed"
        }
    }
}

/// Response for POST /api/finance/loan-applications and GET
/// /api/finance/loan-applications/{id}. Mirrors backend/routers/finance.py
/// LoanApplicationResponse. MOCK DATA — status transitions are simulated by
/// the demo backend, not a real underwriting decision.
struct LoanApplicationResponse: Codable, Identifiable, Equatable {
    let id: Int
    let userId: Int
    let loanOfferId: Int
    let requestedAmount: Double
    let requestedTenureMonths: Int
    let status: String
    let mockCreditScoreAtApplication: Int?
    let decisionReason: String?
    let submittedAt: String?
    let decidedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case loanOfferId = "loan_offer_id"
        case requestedAmount = "requested_amount"
        case requestedTenureMonths = "requested_tenure_months"
        case status
        case mockCreditScoreAtApplication = "mock_credit_score_at_application"
        case decisionReason = "decision_reason"
        case submittedAt = "submitted_at"
        case decidedAt = "decided_at"
    }

    var parsedStatus: LoanApplicationStatus { LoanApplicationStatus(rawValue: status) ?? .submitted }
    var amountDisplay: String { IndianFormatter.formatLakhsCrores(requestedAmount) }
}
