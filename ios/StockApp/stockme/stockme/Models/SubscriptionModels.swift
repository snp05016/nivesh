import Foundation

// MARK: - Subscription Domain Models
//
// MOCK DATA - simulated for demo purposes, not a real integration. No real
// StoreKit purchase flow, no App Store receipt validation, no real payment
// processor is wired anywhere in this stack. "Upgrade"/"Cancel" just flip a
// plan flag on the mock backend (backend/routers/subscription.py — mirrors
// the shape of backend/routers/finance.py's mock Loan Marketplace surface).
// See NetworkManager+Subscription.swift for the exact endpoints these
// decode from.

/// The three subscription tiers shown in the paywall's comparison matrix.
enum SubscriptionTier: String, Codable, CaseIterable, Identifiable {
    case free = "free"
    case pro = "pro"
    case superPro = "super_pro"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .free: return "Free"
        case .pro: return "PRO"
        case .superPro: return "Super PRO"
        }
    }

    var hindi: String {
        switch self {
        case .free: return "मुफ़्त"
        case .pro: return "प्रो"
        case .superPro: return "सुपर प्रो"
        }
    }

    var tagline: String {
        switch self {
        case .free: return "Get started with the basics"
        case .pro: return "For active traders & investors"
        case .superPro: return "Institutional-grade research desk"
        }
    }

    /// Rank used for upgrade/downgrade comparisons — higher is more premium.
    var rank: Int {
        switch self {
        case .free: return 0
        case .pro: return 1
        case .superPro: return 2
        }
    }
}

/// Billing cadence toggle shown above the tier cards.
enum BillingCycle: String, Codable, CaseIterable, Identifiable {
    case monthly = "monthly"
    case annual = "annual"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .monthly: return "Monthly"
        case .annual: return "Annual"
        }
    }
}

/// A single row in the tier comparison feature matrix.
struct SubscriptionFeatureRow: Identifiable {
    let title: String
    /// Value shown per tier — nil renders as a dash, otherwise a checkmark
    /// (for "true"/"yes") or the literal string (e.g. "5/day", "Unlimited").
    let values: [SubscriptionTier: String?]

    var id: String { title }

    /// Matrix rows generated from the server catalogue (GET
    /// /api/v1/subscription/entitlements `catalog`): a checkmark from the
    /// feature's minimum tier upward, a dash below it. An unknown tier
    /// renders as unavailable everywhere.
    static func rows(from catalog: [FeatureCatalogEntryDTO]) -> [SubscriptionFeatureRow] {
        catalog.map { entry in
            let minRank = SubscriptionTier(rawValue: entry.minTier)?.rank ?? Int.max
            var values: [SubscriptionTier: String?] = [:]
            for tier in SubscriptionTier.allCases {
                let value: String? = tier.rank >= minRank ? "yes" : nil
                values.updateValue(value, forKey: tier)
            }
            return SubscriptionFeatureRow(title: entry.title, values: values)
        }
    }
}

/// One pricing/plan entry shown in the paywall's tier comparison. The
/// backend has no plan/pricing-catalog table or endpoint (only
/// user_subscriptions, which stores the *current* plan — see
/// backend/models/db_models.py UserSubscription) so this catalog is defined
/// client-side rather than fetched. MOCK DATA — prices are demo figures, not
/// live App Store SKU prices.
struct SubscriptionPlanDTO: Identifiable, Equatable {
    let id: String
    let parsedTier: SubscriptionTier
    let parsedCycle: BillingCycle
    let priceInr: Double
    let discountPct: Double?

    var priceDisplay: String { priceInr == 0 ? "Free" : "\(IndianFormatter.price(priceInr))/\(parsedCycle == .monthly ? "mo" : "yr")" }
}

/// Client-side plan/pricing catalog (no backend catalog endpoint exists).
enum SubscriptionPlanCatalog {
    static let all: [SubscriptionPlanDTO] = [
        SubscriptionPlanDTO(id: "free_monthly", parsedTier: .free, parsedCycle: .monthly, priceInr: 0, discountPct: nil),
        SubscriptionPlanDTO(id: "free_annual", parsedTier: .free, parsedCycle: .annual, priceInr: 0, discountPct: nil),
        SubscriptionPlanDTO(id: "pro_monthly", parsedTier: .pro, parsedCycle: .monthly, priceInr: 499, discountPct: nil),
        SubscriptionPlanDTO(id: "pro_annual", parsedTier: .pro, parsedCycle: .annual, priceInr: 4990, discountPct: 17),
        SubscriptionPlanDTO(id: "super_pro_monthly", parsedTier: .superPro, parsedCycle: .monthly, priceInr: 999, discountPct: nil),
        SubscriptionPlanDTO(id: "super_pro_annual", parsedTier: .superPro, parsedCycle: .annual, priceInr: 9990, discountPct: 17),
    ]
}

/// The signed-in user's current plan. Mirrors GET /api/v1/subscription
/// (backend/routers/subscription.py SubscriptionResponse). MOCK DATA — no
/// real StoreKit transaction/receipt backs this record.
///
/// The backend has no `status`/`auto_renew`/`sku_id` columns — those are
/// derived client-side from `is_active` + `renews_at` (see `parsedStatus`
/// and `autoRenew` below), matching subscription_service.mock_cancel()'s
/// documented "no cron reverts this" semantics: `tier` stays as-is after
/// cancellation until `renews_at` passes, so the *true* entitlement must be
/// derived from `is_active` + `renews_at` rather than trusted from `tier`
/// alone.
struct CurrentSubscriptionDTO: Codable, Equatable {
    let userId: Int
    let tier: String
    let billingCycle: String?
    let startedAt: String?
    let renewsAt: String?
    let isActive: Bool
    let cancelledAt: String?

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case tier
        case billingCycle = "billing_cycle"
        case startedAt = "started_at"
        case renewsAt = "renews_at"
        case isActive = "is_active"
        case cancelledAt = "cancelled_at"
    }

    var parsedTier: SubscriptionTier { SubscriptionTier(rawValue: tier) ?? .free }
    var renewalDate: String? { renewsAt }
    /// No real auto-renew flag on the backend — treat "still active" as
    /// "will auto-renew" (mirrors mock_cancel()'s "cancel at period end").
    var autoRenew: Bool { isActive && cancelledAt == nil }

    var parsedStatus: SubscriptionStatus {
        if cancelledAt != nil { return .cancelled }
        if !isActive { return .none }
        return .active
    }
}

/// Lifecycle states for the current subscription, derived client-side from
/// is_active/cancelled_at (the backend has no status column/CHECK
/// constraint for this — see CurrentSubscriptionDTO.parsedStatus above).
enum SubscriptionStatus: String, Codable {
    case active = "active"
    case cancelled = "cancelled"
    case pastDue = "past_due"
    case none = "none"

    var displayName: String {
        switch self {
        case .active: return "Active"
        case .cancelled: return "Cancels at period end"
        case .pastDue: return "Payment issue"
        case .none: return "No active plan"
        }
    }
}

/// Request body for POST /api/v1/subscription/upgrade
/// (backend/routers/subscription.py UpgradeRequest). MOCK DATA — no real
/// StoreKit purchase completion happens; this simply asks the mock backend
/// to flip the user's plan row. See services/subscription_service.py.
struct SubscriptionUpgradeRequest: Codable {
    let tier: String
    let billingCycle: String

    enum CodingKeys: String, CodingKey {
        case tier
        case billingCycle = "billing_cycle"
    }
}
