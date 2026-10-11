import SwiftUI
import Combine
/// Drives PaywallView and SubscriptionManagementView — fetches the mock plan
/// catalog + current plan, and performs the mock upgrade/downgrade/cancel
/// actions. Mirrors LoanViewModel's fetch/error/loading shape. MOCK DATA -
/// simulated for demo purposes, not a real integration; no real StoreKit
/// purchase completion, no receipt validation, no real payment processor.
@MainActor
class SubscriptionViewModel: ObservableObject {
    @Published var billingCycle: BillingCycle = .monthly

    @Published var plans: [SubscriptionPlanDTO] = []
    @Published var currentSubscription: CurrentSubscriptionDTO? = nil

    /// Real server-side entitlements from GET /api/v1/subscription/entitlements
    /// (services/entitlement_service.py) — `tier` here is the caller's
    /// *effective* tier (derived from is_active/renews_at, not the possibly
    /// stale `tier` column), so it's preferred over
    /// `currentSubscription?.parsedTier` wherever both are available. See
    /// `currentTier` below.
    @Published var entitlements: EntitlementsDTO? = nil

    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    /// Set while an upgrade/cancel action is in flight, to disable buttons
    /// and show an inline spinner instead of a full-screen loader.
    @Published var isProcessingAction: Bool = false
    @Published var actionErrorMessage: String? = nil

    /// Success confirmation shown after a mock upgrade/cancel completes.
    @Published var lastActionConfirmation: String? = nil

    /// The real, effective tier — prefers `entitlements.tier` (server-derived,
    /// accounts for cancelled-but-not-yet-lapsed subscriptions) and falls
    /// back to `currentSubscription`'s raw tier column if entitlements
    /// haven't loaded yet.
    var currentTier: SubscriptionTier {
        entitlements?.parsedTier ?? currentSubscription?.parsedTier ?? .free
    }

    /// True if the caller's real, server-side entitlements unlock
    /// `featureKey` (see EntitlementFeatureKey / entitlement_service.py
    /// FEATURE_MIN_TIER). Fails closed (`false`) while entitlements haven't
    /// loaded or couldn't be fetched; the server stays authoritative either way.
    func isFeatureUnlocked(_ featureKey: EntitlementFeatureKey) -> Bool {
        entitlements?.isUnlocked(featureKey.rawValue) ?? false
    }

    /// Loads the caller's real entitlements; leaves them nil (locked) on failure.
    func refreshEntitlements() async {
        entitlements = try? await NetworkManager.shared.fetchEntitlements()
    }

    /// Plans for the currently-selected billing cycle, one per tier,
    /// ordered Free → PRO → Super PRO for the comparison matrix columns.
    var visiblePlans: [SubscriptionPlanDTO] {
        SubscriptionTier.allCases.compactMap { tier in
            plans.first { $0.parsedTier == tier && $0.parsedCycle == billingCycle }
        }
    }

    /// Annual discount badge text, derived from the PRO annual plan's
    /// discount_pct (falls back to Super PRO if PRO isn't loaded yet).
    var annualDiscountLabel: String? {
        let annualPlans = plans.filter { $0.parsedCycle == .annual && $0.discountPct != nil }
        guard let best = annualPlans.max(by: { ($0.discountPct ?? 0) < ($1.discountPct ?? 0) }),
              let pct = best.discountPct, pct > 0 else { return nil }
        return "Save \(Int(pct))%"
    }

    func loadPaywall() async {
        isLoading = true
        errorMessage = nil
        // Plan/pricing catalog is client-side only — the backend has no
        // plans-catalog endpoint (see SubscriptionPlanCatalog).
        plans = SubscriptionPlanCatalog.all
        do {
            currentSubscription = try await NetworkManager.shared.fetchCurrentSubscription()
        } catch {
            errorMessage = "Couldn't load your current plan. Pull to retry."
        }
        // Real server-side entitlement check — non-fatal if it fails, since
        // currentSubscription already gives a (slightly less authoritative)
        // fallback tier for the tier cards to render against.
        entitlements = try? await NetworkManager.shared.fetchEntitlements()
        isLoading = false
    }

    func loadCurrentSubscription() async {
        isLoading = true
        errorMessage = nil
        do {
            currentSubscription = try await NetworkManager.shared.fetchCurrentSubscription()
        } catch {
            errorMessage = "Couldn't load your plan. Pull to retry."
        }
        isLoading = false
    }

    /// MOCK - simulated for demo purposes: no real StoreKit purchase sheet.
    func upgrade(to plan: SubscriptionPlanDTO) async {
        isProcessingAction = true
        actionErrorMessage = nil
        #if DEBUG
        do {
            currentSubscription = try await NetworkManager.shared.mockUpgradeSubscription(
                tier: plan.parsedTier.rawValue, billingCycle: plan.parsedCycle.rawValue
            )
            lastActionConfirmation = "You're now on \(plan.parsedTier.displayName) (\(plan.parsedCycle.displayName))."
        } catch {
            actionErrorMessage = "Couldn't complete the upgrade. Please try again."
        }
        #else
        actionErrorMessage = "Purchases are not available in this build."
        #endif
        isProcessingAction = false
    }

    /// MOCK - simulated for demo purposes: no real StoreKit cancellation.
    /// `reason` is UI-only — the backend endpoint takes no request body, so
    /// it is not sent server-side (see NetworkManager+Subscription.swift).
    func cancel(reason: String? = nil) async {
        isProcessingAction = true
        actionErrorMessage = nil
        #if DEBUG
        do {
            currentSubscription = try await NetworkManager.shared.mockCancelSubscription()
            lastActionConfirmation = "Your plan will remain active until the renewal date, then move to Free."
        } catch {
            actionErrorMessage = "Couldn't cancel your plan. Please try again."
        }
        #else
        actionErrorMessage = "Purchases are not available in this build."
        #endif
        isProcessingAction = false
    }
}
