import Foundation

// MARK: - Mock Loan Disbursement Domain Models
//
// MOCK DATA - simulated for demo purposes, not a real integration. No real
// funds are ever moved and no real NBFC is contacted. Best-effort contract
// against the concurrent mock-loan-disbursement backend work landing in
// this same worktree — field names/shape here are provisional and MUST be
// re-verified against the real
// POST /api/finance/loan-applications/{id}/disburse and
// GET /api/finance/loan-applications/{id}/disbursement endpoints once that
// backend agent's code lands (see NetworkManager+Finance.swift for the
// calls that decode these types).

/// Lifecycle states for a (mock) disbursement record.
enum LoanDisbursementStatus: String, Codable {
    case pending = "pending"
    case completed = "completed"
    case failed = "failed"

    var displayName: String {
        switch self {
        case .pending: return "Pending (Demo)"
        case .completed: return "Completed (Demo)"
        case .failed: return "Failed (Demo)"
        }
    }
}

/// Response for both POST /api/finance/loan-applications/{id}/disburse and
/// GET /api/finance/loan-applications/{id}/disbursement. MOCK DATA —
/// simulated for demo purposes, not a real integration; no real fund
/// movement happens and no real NBFC is contacted. Decodes leniently since
/// the exact field set is a best-effort guess pending the real backend
/// model — unknown/missing optional fields simply decode to nil rather than
/// crashing this screen.
struct DisbursementDTO: Codable, Identifiable, Equatable {
    let id: Int
    let loanApplicationId: Int
    let status: String
    let disbursedAmount: Double?
    let nbfcName: String?
    let disbursedAt: String?
    let failureReason: String?

    enum CodingKeys: String, CodingKey {
        case id
        case loanApplicationId = "loan_application_id"
        case status
        case disbursedAmount = "disbursed_amount"
        case nbfcName = "nbfc_name"
        case disbursedAt = "disbursed_at"
        case failureReason = "failure_reason"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        loanApplicationId = try container.decode(Int.self, forKey: .loanApplicationId)
        status = try container.decode(String.self, forKey: .status)
        disbursedAmount = try container.decodeIfPresent(Double.self, forKey: .disbursedAmount)
        nbfcName = try container.decodeIfPresent(String.self, forKey: .nbfcName)
        disbursedAt = try container.decodeIfPresent(String.self, forKey: .disbursedAt)
        failureReason = try container.decodeIfPresent(String.self, forKey: .failureReason)
    }

    var parsedStatus: LoanDisbursementStatus { LoanDisbursementStatus(rawValue: status) ?? .pending }

    var disbursedAmountDisplay: String? {
        guard let disbursedAmount else { return nil }
        return IndianFormatter.formatLakhsCrores(disbursedAmount)
    }
}
