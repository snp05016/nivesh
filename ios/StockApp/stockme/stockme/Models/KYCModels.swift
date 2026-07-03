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
struct DeviceBindingDTO: Codable, Identifiable, Equatable {
    let id: Int
    let userId: Int
    let deviceId: String
    let boundAt: String?
    let isPrimary: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case deviceId = "device_id"
        case boundAt = "bound_at"
        case isPrimary = "is_primary"
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
struct DeviceBindingVerifyDTO: Codable, Equatable {
    let verified: Bool
    let reason: String
}
