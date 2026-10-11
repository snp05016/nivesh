import Foundation

// MARK: - Fixed Deposit Marketplace Domain Models
//
// MOCK DATA - simulated for demo purposes, not a real integration. Every
// "issuer" (NBFC FD issuer) below is fictional/demo-labeled, no real
// underwriting, KYC document collection, or payment processing happens.
// Mirrors the (mock) backend surface at prefix /api/fixed-deposits — a
// separate feature backend built concurrently by another agent. Booking
// submission just writes a row to a mock table on the demo backend, gated
// server-side by the same KYC consent / device-binding checks that gate the
// Loan Marketplace (see decisionReason on FDBookingResponse). Mirrors the
// CONTRACT below exactly — see NetworkManager+FixedDeposits.swift for the
// exact endpoints these decode from.
//
// CONTRACT (do not deviate):
// GET  /api/fixed-deposits/schemes?min_tenure_months=&max_tenure_months=
//      -> array of FDSchemeDTO
// GET  /api/fixed-deposits/schemes/{id} -> single FDSchemeDTO
// POST /api/fixed-deposits/calculator  body: FDCalculatorRequest
//      -> FDCalculatorResponse
// POST /api/fixed-deposits/bookings  body: FDBookingRequest
//      -> FDBookingResponse
// GET  /api/fixed-deposits/bookings -> array of FDBookingResponse

/// A single FD scheme card in the discovery/comparison list. MOCK DATA — the
/// "issuer" is a demo NBFC persona, not a real financial institution.
/// Mirrors GET /api/fixed-deposits/schemes (array) and
/// GET /api/fixed-deposits/schemes/{id} (single object) response shape.
struct FDSchemeDTO: Codable, Identifiable, Equatable {
    let id: Int
    let issuerName: String
    let minTenureMonths: Int
    let maxTenureMonths: Int
    let minAmount: Double
    let maxAmount: Double
    let interestRatePct: Double
    let seniorCitizenBonusPct: Double
    /// NOTE: the CONTRACT specifies `is_active: bool` on this shape, but as
    /// observed against the live backend (backend/routers/fixed_deposits.py
    /// FDSchemeResponse), the field is NOT actually serialized — the backend
    /// filters to active-only schemes server-side instead (see
    /// fixed_deposit_service.list_fd_schemes). Decoded as optional,
    /// defaulting to `true`, so a missing key never breaks the whole
    /// /schemes list decode; flagged for the Reviewer to reconcile with the
    /// real backend contract.
    let isActive: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case issuerName = "issuer_name"
        case minTenureMonths = "min_tenure_months"
        case maxTenureMonths = "max_tenure_months"
        case minAmount = "min_amount"
        case maxAmount = "max_amount"
        case interestRatePct = "interest_rate_pct"
        case seniorCitizenBonusPct = "senior_citizen_bonus_pct"
        case isActive = "is_active"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        issuerName = try container.decode(String.self, forKey: .issuerName)
        minTenureMonths = try container.decode(Int.self, forKey: .minTenureMonths)
        maxTenureMonths = try container.decode(Int.self, forKey: .maxTenureMonths)
        minAmount = try container.decode(Double.self, forKey: .minAmount)
        maxAmount = try container.decode(Double.self, forKey: .maxAmount)
        interestRatePct = try container.decode(Double.self, forKey: .interestRatePct)
        seniorCitizenBonusPct = try container.decode(Double.self, forKey: .seniorCitizenBonusPct)
        isActive = try container.decodeIfPresent(Bool.self, forKey: .isActive) ?? true
    }

    init(
        id: Int, issuerName: String, minTenureMonths: Int, maxTenureMonths: Int,
        minAmount: Double, maxAmount: Double, interestRatePct: Double,
        seniorCitizenBonusPct: Double, isActive: Bool = true
    ) {
        self.id = id
        self.issuerName = issuerName
        self.minTenureMonths = minTenureMonths
        self.maxTenureMonths = maxTenureMonths
        self.minAmount = minAmount
        self.maxAmount = maxAmount
        self.interestRatePct = interestRatePct
        self.seniorCitizenBonusPct = seniorCitizenBonusPct
        self.isActive = isActive
    }

    var interestRateDisplay: String {
        String(format: "%.2f%% p.a.", interestRatePct)
    }

    var seniorCitizenRateDisplay: String {
        String(format: "%.2f%% p.a.", interestRatePct + seniorCitizenBonusPct)
    }

    var amountRangeDisplay: String {
        "\(IndianFormatter.formatLakhsCrores(minAmount)) – \(IndianFormatter.formatLakhsCrores(maxAmount))"
    }

    var tenureRangeDisplay: String {
        "\(minTenureMonths)–\(maxTenureMonths) mo"
    }
}

/// Request body for POST /api/fixed-deposits/calculator. Mirrors the
/// CONTRACT exactly. MOCK DATA - simulated for demo purposes, not a real
/// integration; this is a plain compound-interest projection.
struct FDCalculatorRequest: Codable {
    let principalAmount: Double
    let tenureMonths: Int
    let interestRatePct: Double

    enum CodingKeys: String, CodingKey {
        case principalAmount = "principal_amount"
        case tenureMonths = "tenure_months"
        case interestRatePct = "interest_rate_pct"
    }
}

/// Response for POST /api/fixed-deposits/calculator. Mirrors the CONTRACT
/// exactly.
struct FDCalculatorResponse: Codable, Equatable {
    let maturityAmount: Double
    let interestEarned: Double

    enum CodingKeys: String, CodingKey {
        case maturityAmount = "maturity_amount"
        case interestEarned = "interest_earned"
    }

    var maturityAmountDisplay: String { IndianFormatter.formatLakhsCrores(maturityAmount) }
    var interestEarnedDisplay: String { IndianFormatter.formatLakhsCrores(interestEarned) }
}

/// Payment method chosen at booking time. Both are MOCK/DEMO rails — no real
/// payment collection happens against either.
enum FDPaymentMethod: String, Codable, CaseIterable, Identifiable {
    case upi = "upi"
    case netBanking = "net_banking"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .upi: return "UPI (Demo)"
        case .netBanking: return "Net Banking (Demo)"
        }
    }

    var icon: String {
        switch self {
        case .upi: return "qrcode"
        case .netBanking: return "building.columns.fill"
        }
    }
}

/// Request body for POST /api/fixed-deposits/bookings. Mirrors the CONTRACT
/// exactly — `deviceId` is this device's vendor identifier, the same source
/// LoanApplicationViewModel uses, so the mock KYC device-binding gate on the
/// backend can verify it. MOCK DATA - simulated for demo purposes, not a
/// real integration; no real payment processing happens for either UPI or
/// Net Banking.
struct FDBookingRequest: Codable {
    let schemeId: Int
    let principalAmount: Double
    let tenureMonths: Int
    let paymentMethod: String
    let deviceId: String
    /// Self-declared (mock); the backend adds the scheme's senior-citizen bonus.
    let isSeniorCitizen: Bool

    enum CodingKeys: String, CodingKey {
        case schemeId = "scheme_id"
        case principalAmount = "principal_amount"
        case tenureMonths = "tenure_months"
        case paymentMethod = "payment_method"
        case deviceId = "device_id"
        case isSeniorCitizen = "is_senior_citizen"
    }
}

/// Lifecycle states for a submitted (mock) FD booking. Mirrors the
/// CONTRACT's `status` field.
enum FDBookingStatus: String, Codable {
    case pending = "pending"
    case confirmed = "confirmed"
    case failed = "failed"

    var displayName: String {
        switch self {
        case .pending: return "Pending"
        case .confirmed: return "Confirmed"
        case .failed: return "Failed"
        }
    }
}

/// Response for POST /api/fixed-deposits/bookings and each element of
/// GET /api/fixed-deposits/bookings. Mirrors the CONTRACT exactly.
/// MOCK DATA — status transitions are simulated by the demo backend, not a
/// real payment/booking decision. `decisionReason`, when present on a
/// `failed` booking, surfaces WHY the booking failed closed (e.g. "SIM
/// binding required" / "KYC incomplete") — the UI should guide the user
/// toward Account Settings to complete device binding/consent rather than
/// retry blindly.
struct FDBookingResponse: Codable, Identifiable, Equatable {
    let id: Int
    let schemeId: Int
    let principalAmount: Double
    let tenureMonths: Int
    let interestRatePct: Double
    let maturityAmount: Double
    let paymentMethod: String
    let status: String
    let decisionReason: String?
    let bookedAt: String?
    let maturesAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case schemeId = "scheme_id"
        case principalAmount = "principal_amount"
        case tenureMonths = "tenure_months"
        case interestRatePct = "interest_rate_pct"
        case maturityAmount = "maturity_amount"
        case paymentMethod = "payment_method"
        case status
        case decisionReason = "decision_reason"
        case bookedAt = "booked_at"
        case maturesAt = "matures_at"
    }

    var parsedStatus: FDBookingStatus { FDBookingStatus(rawValue: status) ?? .pending }
    var parsedPaymentMethod: FDPaymentMethod { FDPaymentMethod(rawValue: paymentMethod) ?? .upi }
    var principalDisplay: String { IndianFormatter.formatLakhsCrores(principalAmount) }
    var maturityDisplay: String { IndianFormatter.formatLakhsCrores(maturityAmount) }
}
