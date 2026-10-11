import SwiftUI

// MARK: - NotificationPreferencesView
//
// Per-category push notification toggles (price alerts, IPO updates, forum
// replies, market news). The backend only has a generic UserPreference
// row (theme + a single alerts_enabled bool — backend/models/db_models.py,
// routers/preferences.py) with no per-category columns, and
// SettingsScreen.swift already persists its notification toggles locally
// via @AppStorage (signalChangeAlerts, morningBriefTime, etc.) rather than
// syncing them server-side. This view follows that same established
// local-only pattern instead of inventing a new server model.

struct NotificationPreferencesView: View {
    @AppStorage("nivesh_pushPriceAlerts") private var priceAlerts = true
    @AppStorage("nivesh_pushIPOUpdates") private var ipoUpdates = true
    @AppStorage("nivesh_pushForumReplies") private var forumReplies = false
    @AppStorage("nivesh_pushMarketNews") private var marketNews = false
    @AppStorage("nivesh_pushMasterEnabled") private var masterEnabled = true

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(spacing: Theme.Spacing.large) {
                    masterSection
                    categoriesSection
                }
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.vertical, Theme.Spacing.large)
            }
        }
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.large)
    }

    private var masterSection: some View {
        VStack(spacing: Theme.Spacing.none) {
            NotifToggleRow(
                icon: "bell.badge.fill", color: Theme.securityGold,
                title: "Push Notifications", subtitle: "Master switch for all categories below",
                isOn: $masterEnabled
            )
        }
        .banknoteCard()
    }

    private var categoriesSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
                Text("श्रेणियाँ").font(Theme.hindiFont(size: 9)).foregroundStyle(Theme.inkSecondary)
                Text("CATEGORIES").font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
            }
            .padding(.horizontal, Theme.Spacing.small)

            VStack(spacing: Theme.Spacing.none) {
                NotifToggleRow(
                    icon: "chart.line.uptrend.xyaxis", color: Theme.bullGreen,
                    title: "Price Alerts", subtitle: "Signal changes & target price hits",
                    isOn: $priceAlerts, disabled: !masterEnabled
                )
                GuillocheDivider()
                NotifToggleRow(
                    icon: "newspaper.fill", color: Theme.securityGold,
                    title: "IPO Updates", subtitle: "New listings, allotment & subscription status",
                    isOn: $ipoUpdates, disabled: !masterEnabled
                )
                GuillocheDivider()
                NotifToggleRow(
                    icon: "bubble.left.and.bubble.right.fill", color: Theme.inkSecondary,
                    title: "Forum Replies", subtitle: "Replies & mentions on your threads",
                    isOn: $forumReplies, disabled: !masterEnabled
                )
                GuillocheDivider()
                NotifToggleRow(
                    icon: "globe.asia.australia.fill", color: Theme.holdAmber,
                    title: "Market News", subtitle: "Macro headlines & sector rotation digests",
                    isOn: $marketNews, disabled: !masterEnabled
                )
            }
            .banknoteCard()
        }
    }
}

// MARK: - NotifToggleRow (private to this file)

private struct NotifToggleRow: View {
    let icon: String
    let color: Color
    let title: String
    let subtitle: String
    @Binding var isOn: Bool
    var disabled: Bool = false

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(color.opacity(0.08)).frame(width: 32, height: 32)
                Image(systemName: icon)
                    .font(.subheadline.weight(.medium)).foregroundStyle(color.opacity(0.7))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                Text(subtitle)
                    .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
            Toggle(title, isOn: $isOn)
                .labelsHidden()
                .tint(Theme.securityGold)
                .disabled(disabled)
                .onChange(of: isOn) { _, _ in HapticManager.selection() }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        .opacity(disabled ? 0.4 : 1.0)
    }
}
