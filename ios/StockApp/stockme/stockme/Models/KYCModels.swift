import Foundation

// MARK: - KYC Consent + Device-Binding ("SIM-binding") Domain Models
//
// MOCK DATA - simulated for demo purposes, not a real integration. Mirrors
// the REAL, already-merged /api/kyc/... surface in
// backend/routers/kyc.py + backend/services/kyc_consent_service.py — there
// is no real telecom SIM-swap-detection API and no real credit-bureau /
// government ID verification anywhere behind these endpoints. See
// NetworkManager+KYC.swift for the exact endpoints these decode from.

/// A single KYC consent record. Mirrors GET/POST /api/kyc/consents
/// (backend/services/kyc_consent_service.py `_consent_to_dict`). Each grant
/// inserts a new row (audit trail) rather than updating an existing one, so
/// the full grant/revoke history is reconstructable — callers should treat
/// the array from GET /api/kyc/consents as "currently active" consents only
/// (already filtered server-side to granted && not revoked).
struct ConsentDTO: Codable, Identifiable, Equatable {
    let id: Int
    let userId: Int
    let consentType: String
    let granted: Bool
    let grantedAt: String?
    let ipAddress: String?
    let revokedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case consentType = "consent_type"
        case granted
        case grantedAt = "granted_at"
        case ipAddress = "ip_address"
        case revokedAt = "revoked_at"
    }
}

/// Well-known consent_type values used across the loan/FD marketplace KYC
/// gate (services/kyc_consent_service.py's CREDIT_CHECK_CONSENT constant +
/// the "sim_binding"/"data_sharing" types referenced by
/// services/compliance_service.py's withdraw_consent()).
enum KYCConsentType: String, CaseIterable, Identifiable {
    case creditCheck = "credit_check"
    case simBinding = "sim_binding"
    case dataSharing = "data_sharing"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .creditCheck: return "Credit Check"
        case .simBinding: return "SIM / Device Binding"
        case .dataSharing: return "Data Sharing"
        }
    }

    var explanation: String {
        switch self {
        case .creditCheck:
            return "Required before a (mock) loan application can be approved — see services/loan_marketplace_service.py's KYC gate."
        case .simBinding:
            return "Consent to the mock device-binding fraud-prevention check used to gate loan/FD confirmations."
        case .dataSharing:
            return "Consent to (mock) downstream data sharing with the demo loan/FD marketplace partners."
        }
    }
}

/// Request body for POST /api/kyc/consents (backend RecordConsentRequest).
struct RecordConsentRequest: Codable {
    let consentType: String
    let granted: Bool

    enum CodingKeys: String, CodingKey {
        case consentType = "consent_type"
        case granted
    }
}

/// A single device-binding ("SIM-binding") record. Mirrors
/// POST /api/kyc/device-binding (backend `bind_device()` return shape).
/// `fraudSignal` is an OPTIONAL field the concurrent fraud-signals backend
/// work may add to this response when a bind is rejected (e.g. cross-user
/// device reuse) — decodes leniently to nil when the backend doesn't send
/// it (older/unchanged server, or a successful bind) so this never crashes
/// decoding of the existing response shape. MOCK DATA - simulated for demo
/// purposes, not a real fraud engine.
struct DeviceBindingDTO: Codable, Identifiable, Equatable {
    let id: Int
    let userId: Int
    let deviceId: String
    let boundAt: String?
    let isPrimary: Bool
    let fraudSignal: String?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case deviceId = "device_id"
        case boundAt = "bound_at"
        case isPrimary = "is_primary"
        case fraudSignal = "fraud_signal"
    }

    init(id: Int, userId: Int, deviceId: String, boundAt: String?, isPrimary: Bool, fraudSignal: String? = nil) {
        self.id = id
        self.userId = userId
        self.deviceId = deviceId
        self.boundAt = boundAt
        self.isPrimary = isPrimary
        self.fraudSignal = fraudSignal
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        userId = try container.decode(Int.self, forKey: .userId)
        deviceId = try container.decode(String.self, forKey: .deviceId)
        boundAt = try container.decodeIfPresent(String.self, forKey: .boundAt)
        isPrimary = try container.decode(Bool.self, forKey: .isPrimary)
        // Lenient: missing key (older backend / successful bind) decodes to nil.
        fraudSignal = try container.decodeIfPresent(String.self, forKey: .fraudSignal)
    }

    /// Masked display form, e.g. "AB12••••••••7F3C", so the raw
    /// identifierForVendor UUID isn't shown in full on screen.
    var maskedDeviceId: String {
        let cleaned = deviceId.replacingOccurrences(of: "-", with: "")
        guard cleaned.count > 8 else { return deviceId }
        let prefix = cleaned.prefix(4)
        let suffix = cleaned.suffix(4)
        return "\(prefix)••••••••\(suffix)"
    }
}

/// Request body for POST /api/kyc/device-binding (backend BindDeviceRequest).
struct BindDeviceRequest: Codable {
    let deviceId: String
    let isPrimary: Bool

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case isPrimary = "is_primary"
    }
}

/// Response for GET /api/kyc/device-binding/verify?device_id=
/// (backend `verify_device_binding()` return shape — a MOCK check).
/// `fraudSignal` is OPTIONAL — the concurrent fraud-signals backend work may
/// add this when a verify fails (e.g. cross-user device reuse); decodes
/// leniently to nil when absent. MOCK DATA - simulated for demo purposes.
struct DeviceBindingVerifyDTO: Codable, Equatable {
    let verified: Bool
    let reason: String
    let fraudSignal: String?

    enum CodingKeys: String, CodingKey {
        case verified, reason
        case fraudSignal = "fraud_signal"
    }

    init(verified: Bool, reason: String, fraudSignal: String? = nil) {
        self.verified = verified
        self.reason = reason
        self.fraudSignal = fraudSignal
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        verified = try container.decode(Bool.self, forKey: .verified)
        reason = try container.decode(String.self, forKey: .reason)
        fraudSignal = try container.decodeIfPresent(String.self, forKey: .fraudSignal)
    }
}

// MARK: - Fraud Signals

/// GET /api/kyc/fraud-signals. MOCK DATA - simulated for demo purposes, not
/// a real fraud-detection engine — this is a simple aggregate over this
/// app's own DeviceBinding rows (bind attempts / cross-user rejections /
/// rate-limit hits), not a telecom or bureau signal. Best-effort contract
/// pending final backend shape from the concurrent fraud-signals work;
/// decodes leniently (unknown/missing fields default to safe values) so a
/// still-landing backend doesn't crash this screen.
struct FraudSignalsDTO: Codable, Equatable {
    let totalBindAttempts24h: Int
    let crossUserRejectionsTotal: Int
    let rateLimitHits24h: Int
    let isFlagged: Bool

    enum CodingKeys: String, CodingKey {
        case totalBindAttempts24h = "total_bind_attempts_24h"
        case crossUserRejectionsTotal = "cross_user_rejections_total"
        case rateLimitHits24h = "rate_limit_hits_24h"
        case isFlagged = "is_flagged"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        totalBindAttempts24h = try container.decodeIfPresent(Int.self, forKey: .totalBindAttempts24h) ?? 0
        crossUserRejectionsTotal = try container.decodeIfPresent(Int.self, forKey: .crossUserRejectionsTotal) ?? 0
        rateLimitHits24h = try container.decodeIfPresent(Int.self, forKey: .rateLimitHits24h) ?? 0
        isFlagged = try container.decodeIfPresent(Bool.self, forKey: .isFlagged) ?? false
    }
}
