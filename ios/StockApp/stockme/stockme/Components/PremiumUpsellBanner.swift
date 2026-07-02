import SwiftUI

// MARK: - PremiumUpsellBanner
//
// Small reusable inline banner prompting upgrade — matches the icon + title
// + subtitle layout of Views/Analysis/RegimeWarningBanner.swift (rounded
// rect fill/stroke, no banknoteCard chrome since it's meant to sit inline
// inside another screen's content, not stand alone as a card). Tapping it
// presents PaywallView as a sheet. MOCK - simulated for demo purposes: no
// real entitlement check gates the feature it's attached to; this is UI-only.

struct PremiumUpsellBanner: View {
    /// Short feature-specific hook, e.g. "Unlock unlimited price alerts".
    let message: String
    var tier: SubscriptionTier = .pro

    @State private var showPaywall = false

    var body: some View {
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
    PremiumUpsellBanner(message: "Unlock unlimited AI Deep Scan analyses and real-time data")
        .padding()
        .background(Theme.canvasDeep)
}
