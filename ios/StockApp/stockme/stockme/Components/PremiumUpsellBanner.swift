import SwiftUI

// MARK: - PremiumUpsellBanner
//
// Small reusable inline banner prompting upgrade — matches the icon + title
// + subtitle layout of Views/Analysis/RegimeWarningBanner.swift (rounded
// rect fill/stroke, no banknoteCard chrome since it's meant to sit inline
// inside another screen's content, not stand alone as a card). Tapping it
// presents PaywallView as a sheet.
//
// Gated on the REAL server-side entitlement check: GET
// /api/v1/subscription/entitlements (services/entitlement_service.py,
// enforced server-side on the actual endpoint via
// core/entitlement_gate.py's require_entitlement() dependency). When
// `featureKey` is supplied, this banner fetches entitlements on appear and
// hides itself once the server reports the feature is already unlocked —
// it no longer just always renders regardless of the caller's real plan.
// If `featureKey` is omitted, or the entitlements fetch fails, this fails
// open (still shows the upsell) rather than silently hiding a real gate.

struct PremiumUpsellBanner: View {
    /// Short feature-specific hook, e.g. "Unlock unlimited price alerts".
    let message: String
    var tier: SubscriptionTier = .pro
    /// Real backend feature key (see EntitlementFeatureKey /
    /// entitlement_service.py FEATURE_MIN_TIER) this banner gates on. Pass
    /// nil to always show (no server-side feature backs it yet).
    var featureKey: EntitlementFeatureKey? = nil

    @State private var showPaywall = false
    @State private var isUnlocked = false
    @State private var hasCheckedEntitlement = false

    var body: some View {
        // Release builds have no in-app purchase yet (ReleaseGate), so the
        // upsell and its mock paywall are Debug-only.
        if ReleaseGate.demoFeatures {
            Group {
                if !isUnlocked {
                    bannerButton
                }
            }
            .task { await checkEntitlement() }
        } else {
            EmptyView()
        }
    }

    private func checkEntitlement() async {
        guard let featureKey, !hasCheckedEntitlement else { return }
        hasCheckedEntitlement = true
        if let entitlements = try? await NetworkManager.shared.fetchEntitlements() {
            isUnlocked = entitlements.isUnlocked(featureKey.rawValue)
        }
    }

    private var bannerButton: some View {
        Button {
            HapticManager.selection()
            showPaywall = true
        } label: {
            HStack(spacing: Theme.Spacing.standard) {
                Image(systemName: "crown.fill")
                    .foregroundStyle(Theme.securityGold)
                    .imageScale(.large)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("\(tier.displayName.uppercased()) FEATURE")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)

                    Text(message)
                        .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .caption))
                        .foregroundStyle(Theme.inkPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(Theme.Spacing.card)
            .background(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .fill(Theme.securityGold.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.securityGold.opacity(0.3), lineWidth: 1)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showPaywall) {
            PaywallView()
        }
    }
}

#Preview {
    PremiumUpsellBanner(message: "Unlock more with Nivesh Pro")
        .padding()
        .background(Theme.canvasDeep)
}
