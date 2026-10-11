import Foundation

// MARK: - Compliance Disclosure + Key Fact Statement (KFS) Domain Models
//
// DEMO-GRADE / ILLUSTRATIVE CONTENT ONLY. Mirrors the REAL
// GET /api/v1/compliance/disclosures/{key} and
// GET /api/v1/compliance/key-fact-statement endpoints in
// backend/routers/compliance.py + backend/services/disclosure_service.py.
// Every disclosure body is clearly-labelled placeholder/demo copy for a
// portfolio project — NOT real legal advice, NOT a real regulatory filing,
// and does NOT reference any real SEBI/RBI registration or license number.

/// A disclosure's `sections` array is heterogeneous on the real backend:
/// most disclosures use `{heading, text}` dict entries
/// (services/disclosure_service.py's `_section()` helper), but
/// "digital_lending_compliance" uses a plain list of strings instead. This
/// decodes either shape into one type so DisclosureDetailView can render
/// both uniformly.
enum DisclosureSection: Codable, Identifiable, Equatable {
    case heading(String, String)
    case plain(String)

    var id: String {
        switch self {
        case .heading(let heading, let text): return heading + text
        case .plain(let text): return text
        }
    }

    var heading: String? {
        if case .heading(let heading, _) = self { return heading }
        return nil
    }

    var text: String {
        switch self {
        case .heading(_, let text): return text
        case .plain(let text): return text
        }
    }

    init(from decoder: Decoder) throws {
        if let container = try? decoder.singleValueContainer(), let plainText = try? container.decode(String.self) {
            self = .plain(plainText)
            return
        }
        let keyed = try decoder.container(keyedBy: CodingKeys.self)
        let heading = try keyed.decode(String.self, forKey: .heading)
        let text = try keyed.decode(String.self, forKey: .text)
        self = .heading(heading, text)
    }

    func encode(to encoder: Encoder) throws {
        switch self {
        case .plain(let text):
            var container = encoder.singleValueContainer()
            try container.encode(text)
        case .heading(let heading, let text):
            var keyed = encoder.container(keyedBy: CodingKeys.self)
            try keyed.encode(heading, forKey: .heading)
            try keyed.encode(text, forKey: .text)
        }
    }

    enum CodingKeys: String, CodingKey {
        case heading, text
    }
}

/// GET /api/v1/compliance/disclosures/{key}. Valid keys (mirrors
/// backend/routers/compliance.py `_VALID_DISCLOSURE_KEYS`): privacy_policy,
/// terms_of_use, grievance_officer, data_sharing_governance, digital_lending_compliance,
/// lending_service_provider, apr_disclosure, sim_binding_fraud_prevention.
struct DisclosureDTO: Codable, Equatable {
    let key: String?
    let title: String
    let body: String
    let sections: [DisclosureSection]?
}

/// Well-known disclosure keys, matching
/// backend/routers/compliance.py `_VALID_DISCLOSURE_KEYS` exactly.
enum DisclosureKey: String, CaseIterable, Identifiable {
    case privacyPolicy = "privacy_policy"
    case termsOfUse = "terms_of_use"
    case grievanceOfficer = "grievance_officer"
    case dataSharingGovernance = "data_sharing_governance"
    case digitalLendingCompliance = "digital_lending_compliance"
    case lendingServiceProvider = "lending_service_provider"
    case aprDisclosure = "apr_disclosure"
    case simBindingFraudPrevention = "sim_binding_fraud_prevention"

    var id: String { rawValue }

    var displayTitle: String {
        switch self {
        case .privacyPolicy: return "Privacy Policy"
        case .termsOfUse: return "Terms of Use"
        case .grievanceOfficer: return "Contact & Grievance Officer"
        case .dataSharingGovernance: return "Data Sharing Governance"
        case .digitalLendingCompliance: return "Digital Lending Compliance"
        case .lendingServiceProvider: return "Lending Service Provider"
        case .aprDisclosure: return "APR Disclosure"
        case .simBindingFraudPrevention: return "SIM-Binding Fraud Prevention"
        }
    }

    /// REG-12: the privacy policy, terms and grievance contact are the real
    /// notices; the lending/marketplace disclosures are still demo copy.
    var isDemoContent: Bool {
        switch self {
        case .privacyPolicy, .termsOfUse, .grievanceOfficer: return false
        default: return true
        }
    }
}

/// GET /api/v1/compliance/key-fact-statement?loan_offer_id= or ?scheme_id=.
/// Mirrors backend `disclosure_service.compute_key_fact_statement()` — the
/// loan-offer and FD-scheme variants share `loan_amount`/`interest_rate`/
/// `all_fees`/`apr`/`tenure_months`/`disclaimer` but differ in which of
/// (loan_offer_id + nbfc_name + loan_type) vs (scheme_id + issuer_name) is
/// populated, distinguished by `source`.
struct KeyFactStatementDTO: Codable, Equatable {
    let source: String
    let loanOfferId: Int?
    let nbfcName: String?
    let loanType: String?
    let schemeId: Int?
    let issuerName: String?
    let loanAmount: Double
    let interestRate: Double
    let allFees: Double
    let apr: Double
    let tenureMonths: Int
    let disclaimer: String?

    enum CodingKeys: String, CodingKey {
        case source
        case loanOfferId = "loan_offer_id"
        case nbfcName = "nbfc_name"
        case loanType = "loan_type"
        case schemeId = "scheme_id"
        case issuerName = "issuer_name"
        case loanAmount = "loan_amount"
        case interestRate = "interest_rate"
        case allFees = "all_fees"
        case apr
        case tenureMonths = "tenure_months"
        case disclaimer
    }

    var isFixedDeposit: Bool { source == "fixed_deposit_scheme" }

    var issuerDisplayName: String { issuerName ?? nbfcName ?? "—" }

    var amountDisplay: String { IndianFormatter.formatLakhsCrores(loanAmount) }
    var feesDisplay: String { IndianFormatter.formatLakhsCrores(allFees) }
    var interestRateDisplay: String { String(format: "%.2f%% p.a.", interestRate) }
    var aprDisplay: String { String(format: "%.2f%% APR", apr) }
    var tenureDisplay: String { "\(tenureMonths) months" }
}

// MARK: - Entitlements

/// GET /api/v1/subscription/entitlements (backend/routers/subscription.py
/// EntitlementsResponse, backed by services/entitlement_service.py). `tier`
/// is the caller's *effective* tier — derived from UserSubscription's
/// is_active/renews_at rather than trusting the possibly-stale `tier`
/// column directly (see entitlement_service.get_effective_tier). `features`
/// maps every server-enforced feature key (entitlement_service.FEATURE_MIN_TIER)
/// to whether the caller's effective tier currently unlocks them. `catalog`
/// lists the same keys with paywall titles and minimum tiers; it is nil from
/// servers that predate it.
struct EntitlementsDTO: Codable, Equatable {
    let tier: String
    let features: [String: Bool]
    var catalog: [FeatureCatalogEntryDTO]? = nil

    var parsedTier: SubscriptionTier { SubscriptionTier(rawValue: tier) ?? .free }

    /// Fails closed: a key the server did not return is treated as locked.
    func isUnlocked(_ featureKey: String) -> Bool {
        features[featureKey] ?? false
    }
}

/// One gated feature from entitlement_service.get_feature_catalog().
struct FeatureCatalogEntryDTO: Codable, Equatable, Identifiable {
    let key: String
    let title: String
    let minTier: String

    var id: String { key }

    enum CodingKeys: String, CodingKey {
        case key, title
        case minTier = "min_tier"
    }
}

/// Feature keys gated server-side — mirrors
/// backend/services/entitlement_service.py FEATURE_MIN_TIER exactly (the
/// six keys routers enforce via require_entitlement()).
enum EntitlementFeatureKey: String {
    case advancedAnalysis = "advanced_analysis"
    case sectorRotation = "sector_rotation"
    case comprehensiveStockInsights = "comprehensive_stock_insights"
    case swotAnalysis = "swot_analysis"
    case technicalPicks = "technical_picks"
    case ideasForProfit = "ideas_for_profit"
}
