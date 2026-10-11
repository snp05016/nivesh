import SwiftUI

// MARK: - NotificationPreferencesView
//
// Push master switch. It is stored locally (@AppStorage nivesh_pushMasterEnabled,
// read by NotificationManager to mute local notifications and the Morning Brief) and
// synced to the backend's UserPreference.alerts_enabled via PUT /api/v1/preferences,
// which the price-alert poller and APNs delivery honour. The sync and the one-time
// migration of a pre-sync local OFF live in NotificationManager.
// Price alerts are the only push type today, so there are no per-category toggles.

struct NotificationPreferencesView: View {
    @AppStorage("nivesh_pushMasterEnabled") private var masterEnabled = true
    @State private var syncError: String? = nil

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                    masterSection
                    if let syncError {
                        Text(syncError)
                            .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed)
                            .padding(.horizontal, Theme.Spacing.small)
                    }
                    Text("Server pushes are price alerts only today; more categories coming soon.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
                        .padding(.horizontal, Theme.Spacing.small)
                }
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.vertical, Theme.Spacing.large)
            }
        }
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.large)
        .task { await NotificationManager.shared.syncPushMaster() }
        .onChange(of: masterEnabled) { _, newValue in
            Task {
                guard let saved = await NotificationManager.shared.pushMasterChanged(to: newValue) else { return }
                syncError = saved ? nil : "Couldn't save this setting. Check your connection and try again."
            }
        }
    }

    private var masterSection: some View {
        NotifToggleRow(
            icon: "bell.badge.fill", color: Theme.securityGold,
            title: "Push Notifications", subtitle: "Price alerts, Morning Brief and analysis alerts",
            isOn: $masterEnabled
        )
        .banknoteCard()
    }
}

// MARK: - NotifToggleRow (private to this file)

private struct NotifToggleRow: View {
    let icon: String
    let color: Color
    let title: String
    let subtitle: String
    @Binding var isOn: Bool

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
                .onChange(of: isOn) { _, _ in HapticManager.selection() }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}
