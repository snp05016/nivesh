import SwiftUI

// MARK: - PaywallView
//
// Tier comparison (Free vs PRO vs Super PRO), monthly/annual billing toggle
// with an annual-discount badge, and a feature matrix. MOCK - simulated for
// demo purposes: tapping "Upgrade" calls NetworkManager.mockUpgradeSubscription,
// which just flips a plan flag on the mock backend — no real StoreKit
// purchase sheet is shown, no receipt is generated, no payment processor is
// wired.

struct PaywallView: View {
    @StateObject private var vm = SubscriptionViewModel()
    @Environment(\.dismiss) private var dismiss
    @State private var pendingUpgradePlan: SubscriptionPlanDTO? = nil
    @State private var showConfirmation = false

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()
                if vm.isLoading && vm.plans.isEmpty {
                    ProgressView().tint(Theme.securityGold)
                } else {
                    content
                }
            }
            .navigationTitle("Go Premium")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") { HapticManager.selection(); dismiss() }
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
            .task { await vm.loadPaywall() }
            .refreshable { await vm.loadPaywall() }
            .banknoteDialog(
                "Confirm Upgrade",
                isPresented: $showConfirmation,
                message: confirmationMessage,
                buttons: [
                    .init("Upgrade (Mock)") {
                        guard let plan = pendingUpgradePlan else { return }
                        Task { await vm.upgrade(to: plan) }
                    },
                    .cancel()
                ]
            )
        }
    }

    private var confirmationMessage: String {
        guard let plan = pendingUpgradePlan else { return "" }
        return "MOCK - simulated for demo purposes. This simulates upgrading to \(plan.parsedTier.displayName) at \(plan.priceDisplay). No real payment is processed."
    }

    private var content: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.sectionGap) {
                headerSection
                billingToggle
                tierCards
                serverEntitlementsSection
                if let confirmation = vm.lastActionConfirmation {
                    confirmationBanner(confirmation)
                }
                if let error = vm.errorMessage ?? vm.actionErrorMessage {
                    errorBanner(error)
                }
                GuillocheDivider()
                featureMatrix
            }
            .padding(.horizontal, Theme.Spacing.screen)
            .padding(.vertical, Theme.Spacing.large)
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("अपग्रेड करें").font(Theme.hindiFont(size: 11)).foregroundStyle(Theme.inkSecondary)
            Text("Unlock the Full Research Desk")
                .font(Theme.engravedSerif(size: 22, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)
            Text("Deeper AI analysis, unlimited alerts, and institutional-grade tools.")
                .font(Theme.engravedSerif(size: 13, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Billing Toggle

    private var billingToggle: some View {
        HStack(spacing: Theme.Spacing.medium) {
            ForEach(BillingCycle.allCases) { cycle in
                billingToggleButton(cycle)
            }
        }
    }

    private func billingToggleButton(_ cycle: BillingCycle) -> some View {
        let isSelected = vm.billingCycle == cycle
        return Button {
            HapticManager.selection()
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { vm.billingCycle = cycle }
        } label: {
            HStack(spacing: Theme.Spacing.small) {
                Text(cycle.displayName.uppercased())
                    .font(Theme.officialStampFont(size: 11))
                    .tracking(1.2)
                if cycle == .annual, let label = vm.annualDiscountLabel {
                    BanknoteSignalBadge(text: label, color: Theme.bullGreen, rotation: 0)
                        .scaleEffect(0.85)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.standard)
            .foregroundStyle(isSelected ? Theme.canvas : Theme.inkSecondary)
            .background(isSelected ? Theme.securityGold : Theme.canvasDeep)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(isSelected ? Color.clear : Theme.borderFine, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: - Tier Cards

    private var tierCards: some View {
        VStack(spacing: Theme.Spacing.card) {
            ForEach(vm.visiblePlans) { plan in
                PaywallTierCard(
                    plan: plan,
                    isCurrent: plan.parsedTier == vm.currentTier,
                    isProcessing: vm.isProcessingAction,
                    onUpgrade: {
                        HapticManager.selection()
                        pendingUpgradePlan = plan
                        showConfirmation = true
                    }
                )
            }
        }
    }

    // MARK: - Server-Verified Entitlements
    //
    // Real gate check, not a static client-side assumption: sourced from
    // GET /api/v1/subscription/entitlements (services/entitlement_service.py
    // FEATURE_MIN_TIER), which is the exact set of feature keys real
    // premium endpoints enforce server-side via core/entitlement_gate.py's
    // require_entitlement() dependency.

    @ViewBuilder
    private var serverEntitlementsSection: some View {
        if let entitlements = vm.entitlements {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                Text("SERVER-VERIFIED ENTITLEMENTS")
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkSecondary)
                VStack(spacing: Theme.Spacing.none) {
                    ForEach(EntitlementFeatureKeyDisplay.all, id: \.key.rawValue) { entry in
                        EntitlementFeatureRow(
                            title: entry.title,
                            isUnlocked: entitlements.isUnlocked(entry.key.rawValue)
                        )
                    }
                }
                .banknoteCard()
            }
        }
    }

    // MARK: - Feature Matrix

    private var featureMatrix: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("COMPARE FEATURES")
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.5)
                .foregroundStyle(Theme.inkSecondary)

            VStack(spacing: Theme.Spacing.none) {
                matrixHeaderRow
                ForEach(SubscriptionFeatureCatalog.rows) { row in
                    FeatureMatrixRow(row: row)
                }
            }
            .banknoteCard()
        }
    }

    @ViewBuilder
    private var matrixHeaderRow: some View {
        HStack(spacing: Theme.Spacing.small) {
            Text("FEATURE")
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkTertiary)
                .frame(maxWidth: .infinity, alignment: .leading)
            ForEach(SubscriptionTier.allCases) { tier in
                Text(tier.displayName.uppercased())
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(width: 64)
                    .multilineTextAlignment(.center)
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
        Rectangle().fill(Theme.inkPrimary.opacity(0.08)).frame(height: 0.5)
    }
}

// MARK: - Tier Card

private struct PaywallTierCard: View {
    let plan: SubscriptionPlanDTO
    let isCurrent: Bool
    let isProcessing: Bool
    let onUpgrade: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            header
            Text(plan.parsedTier.tagline)
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
            priceRow
            actionButton
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(plan.parsedTier == .superPro ? Theme.securityGold.opacity(0.5) : Color.clear, lineWidth: 1.5)
        )
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(plan.parsedTier.hindi).font(Theme.hindiFont(size: 9)).foregroundStyle(Theme.inkSecondary)
                Text(plan.parsedTier.displayName)
                    .font(Theme.engravedSerif(size: 18, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)
            }
            Spacer()
            if isCurrent {
                BanknoteSignalBadge(text: "Current", color: Theme.bullGreen, rotation: 0)
            } else if plan.parsedTier == .superPro {
                BanknoteSignalBadge(text: "Best Value", color: Theme.securityGold, rotation: 0)
            }
        }
    }

    private var priceRow: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
            Text(plan.priceDisplay)
                .font(Theme.serialNumberFont(size: 20).weight(.semibold))
                .foregroundStyle(Theme.inkPrimary)
            if let discount = plan.discountPct, discount > 0 {
                Text("· \(Int(discount))% off")
                    .font(Theme.roundedCaption(size: 11))
                    .foregroundStyle(Theme.bullGreen)
            }
        }
    }

    @ViewBuilder
    private var actionButton: some View {
        if isCurrent {
            Text("YOUR CURRENT PLAN")
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.standard)
        } else {
            Button(action: onUpgrade) {
                HStack {
                    if isProcessing { ProgressView().tint(Theme.canvas) }
                    Text(plan.parsedTier == .free ? "DOWNGRADE (MOCK)" : "UPGRADE (MOCK)")
                        .font(Theme.officialStampFont(size: 11))
                        .tracking(1.2)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.standard)
                .foregroundStyle(Theme.canvas)
                .background(Theme.securityGold)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            }
            .buttonStyle(EKPressStyle())
            .disabled(isProcessing)
        }
    }
}

// MARK: - Feature Matrix Row

private struct FeatureMatrixRow: View {
    let row: SubscriptionFeatureRow

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            HStack(spacing: Theme.Spacing.small) {
                Text(row.title)
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                ForEach(SubscriptionTier.allCases) { tier in
                    cell(for: tier)
                        .frame(width: 64)
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
        }
    }

    @ViewBuilder
    private func cell(for tier: SubscriptionTier) -> some View {
        let value = row.values[tier] ?? nil
        if value == "yes" {
            Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.bullGreen)
        } else if let value = value {
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
        } else {
            Text("—").foregroundStyle(Theme.inkTertiary)
        }
    }
}

// MARK: - Server Entitlement Row

private struct EntitlementFeatureKeyDisplay {
    let key: EntitlementFeatureKey
    let title: String

    static let all: [EntitlementFeatureKeyDisplay] = [
        .init(key: .advancedAnalysis, title: "Advanced Analysis Dashboards"),
        .init(key: .forumPremiumBoard, title: "Forum Premium Boards"),
        .init(key: .sectorRotation, title: "Sector Rotation Analytics"),
        .init(key: .alphaGenerators, title: "Alpha Generators"),
        .init(key: .whatsappAlerts, title: "WhatsApp Alerts"),
    ]
}

private struct EntitlementFeatureRow: View {
    let title: String
    let isUnlocked: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: isUnlocked ? "checkmark.circle.fill" : "lock.fill")
                .foregroundStyle(isUnlocked ? Theme.bullGreen : Theme.inkTertiary)
            Text(title)
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

// MARK: - Confirmation / Error Banners

private extension PaywallView {
    func confirmationBanner(_ message: String) -> some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "checkmark.seal.fill").foregroundStyle(Theme.bullGreen)
            Text(message)
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
        }
        .padding(Theme.Spacing.card)
        .background(Theme.bullGreen.opacity(0.1))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.bullGreen.opacity(0.3), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }

    func errorBanner(_ message: String) -> some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.bearRed)
            Text(message)
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
        }
        .padding(Theme.Spacing.card)
        .background(Theme.bearRed.opacity(0.1))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.bearRed.opacity(0.3), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }
}

// MARK: - Feature Catalog (client-side matrix content, not fetched from backend)

enum SubscriptionFeatureCatalog {
    static let rows: [SubscriptionFeatureRow] = [
        SubscriptionFeatureRow(title: "Watchlist size", values: [.free: "10", .pro: "100", .superPro: "Unlimited"]),
        SubscriptionFeatureRow(title: "Price alerts", values: [.free: "5", .pro: "50", .superPro: "Unlimited"]),
        SubscriptionFeatureRow(title: "AI Deep Scan analysis", values: [.free: "1/day", .pro: "20/day", .superPro: "Unlimited"]),
        SubscriptionFeatureRow(title: "Real-time data (vs 15-min delay)", values: [.free: nil, .pro: "yes", .superPro: "yes"]),
        SubscriptionFeatureRow(title: "Options strategy builder", values: [.free: nil, .pro: "yes", .superPro: "yes"]),
        SubscriptionFeatureRow(title: "Portfolio stress test", values: [.free: nil, .pro: nil, .superPro: "yes"]),
        SubscriptionFeatureRow(title: "Expert network access", values: [.free: nil, .pro: nil, .superPro: "yes"]),
        SubscriptionFeatureRow(title: "Priority support", values: [.free: nil, .pro: "yes", .superPro: "yes"]),
        SubscriptionFeatureRow(title: "Ad-free experience", values: [.free: nil, .pro: "yes", .superPro: "yes"]),
    ]
}

#Preview {
    PaywallView()
}
