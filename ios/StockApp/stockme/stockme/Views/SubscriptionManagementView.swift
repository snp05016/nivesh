import SwiftUI

// MARK: - SubscriptionManagementView
//
// Current plan, renewal date, and cancel/upgrade/downgrade actions. MOCK -
// simulated for demo purposes: cancel just marks the mock backend row
// `cancelled` and upgrade just flips the plan flag — no real StoreKit
// transaction, no receipt, no refund flow. Reached from
// Settings → Account → "Subscription".

struct SubscriptionManagementView: View {
    @StateObject private var vm = SubscriptionViewModel()
    @State private var showPaywall = false
    @State private var showCancelConfirm = false

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            if vm.isLoading && vm.currentSubscription == nil {
                ProgressView().tint(Theme.securityGold)
            } else {
                content
            }
        }
        .navigationTitle("Subscription")
        .navigationBarTitleDisplayMode(.large)
        .task { await vm.loadCurrentSubscription() }
        .refreshable { await vm.loadCurrentSubscription() }
        .sheet(isPresented: $showPaywall) {
            PaywallView()
        }
        .banknoteDialog(
            "Cancel Plan?",
            isPresented: $showCancelConfirm,
            message: "MOCK - simulated for demo purposes. Your \(vm.currentTier.displayName) access continues until the renewal date, then moves to Free. No real refund is processed.",
            buttons: [
                .init("Cancel Plan (Mock)", role: .destructive) {
                    Task { await vm.cancel() }
                },
                .cancel()
            ]
        )
    }

    private var content: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.large) {
                currentPlanCard
                if let confirmation = vm.lastActionConfirmation {
                    inlineBanner(confirmation, icon: "checkmark.seal.fill", color: Theme.bullGreen)
                }
                if let error = vm.actionErrorMessage ?? vm.errorMessage {
                    inlineBanner(error, icon: "exclamationmark.triangle.fill", color: Theme.bearRed)
                }
                if ReleaseGate.demoFeatures {
                    actionsSection
                } else {
                    BetaPlanNotice()
                }
            }
            .padding(.horizontal, Theme.Spacing.screen)
            .padding(.vertical, Theme.Spacing.large)
        }
    }

    // MARK: - Current Plan Card

    private var currentPlanCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("CURRENT PLAN")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkSecondary)
                    Text(vm.currentTier.displayName)
                        .font(Theme.engravedSerif(size: 22, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                }
                Spacer()
                if let sub = vm.currentSubscription {
                    BanknoteSignalBadge(
                        text: sub.parsedStatus.displayName,
                        color: statusColor(sub.parsedStatus),
                        rotation: 0
                    )
                }
            }

            GuillocheDivider()

            if let sub = vm.currentSubscription {
                detailRow(label: "Billing cycle", value: sub.billingCycle?.capitalized ?? "—")
                detailRow(label: "Renewal date", value: formattedRenewalDate(sub.renewalDate))
                detailRow(label: "Auto-renew", value: sub.autoRenew ? "On" : "Off")
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func detailRow(label: String, value: String) -> some View {
        HStack {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkTertiary)
            Spacer()
            Text(value)
                .font(Theme.serialNumberFont(size: 12))
                .foregroundStyle(Theme.inkPrimary)
        }
    }

    private func statusColor(_ status: SubscriptionStatus) -> Color {
        switch status {
        case .active: return Theme.bullGreen
        case .cancelled: return Theme.holdAmber
        case .pastDue: return Theme.bearRed
        case .none: return Theme.inkSecondary
        }
    }

    private func formattedRenewalDate(_ raw: String?) -> String {
        guard let raw, !raw.isEmpty else { return "—" }
        let iso = ISO8601DateFormatter()
        if let date = iso.date(from: raw) {
            let fmt = DateFormatter()
            fmt.dateFormat = "d MMM yyyy"
            return fmt.string(from: date)
        }
        return raw
    }

    // MARK: - Actions

    private var actionsSection: some View {
        VStack(spacing: Theme.Spacing.none) {
            Button {
                HapticManager.selection()
                showPaywall = true
            } label: {
                actionRow(icon: "arrow.up.circle.fill", color: Theme.securityGold, title: "Upgrade / Downgrade Plan")
            }
            .buttonStyle(EKPressStyle())
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

            if vm.currentTier != .free && vm.currentSubscription?.parsedStatus != .cancelled {
                Button(role: .destructive) {
                    HapticManager.selection()
                    showCancelConfirm = true
                } label: {
                    actionRow(icon: "xmark.circle.fill", color: Theme.bearRed, title: "Cancel Plan", tint: Theme.bearRed)
                }
                .buttonStyle(EKPressStyle())
                .disabled(vm.isProcessingAction)
            }
        }
        .banknoteCard()
    }

    private func actionRow(icon: String, color: Color, title: String, tint: Color? = nil) -> some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: icon).foregroundStyle(color).imageScale(.large)
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.0)
                .foregroundStyle(tint ?? Theme.inkPrimary)
            Spacer()
            if vm.isProcessingAction {
                ProgressView().tint(Theme.inkSecondary)
            } else {
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        .contentShape(Rectangle())
    }

    private func inlineBanner(_ message: String, icon: String, color: Color) -> some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: icon).foregroundStyle(color)
            Text(message)
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
        }
        .padding(Theme.Spacing.card)
        .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(color.opacity(0.1)))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(color.opacity(0.3), lineWidth: 1))
    }
}

// MARK: - Beta Plan Notice
//
// Shown instead of the mock upgrade/cancel actions in Release builds
// (ReleaseGate): paid tiers must be sold through App Store in-app purchase.

struct BetaPlanNotice: View {
    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Image(systemName: "gift.fill")
                .foregroundStyle(Theme.securityGold)
                .imageScale(.large)
            Text("All features are free during the beta. Paid plans will be offered through App Store in-app purchase.")
                .font(Theme.engravedSerif(size: 13, relativeTo: .caption))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

#Preview {
    NavigationStack {
        SubscriptionManagementView()
    }
}
