import SwiftUI

struct SettingsScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager

    @State private var showDevTools = false
    @State private var devToolsTapCount = 0

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: Theme.Spacing.large) {
                        
                        // Profile Section
                        if let user = authManager.currentUser {
                            HStack(spacing: Theme.Spacing.card) {
                                ZStack {
                                    Circle()
                                        .fill(Theme.securityGold)
                                        .frame(width: 56, height: 56)
                                        .shadow(color: Theme.securityGold.opacity(0.3), radius: 8, y: 4)
                                    Text(String(user.displayName.prefix(1)).uppercased())
                                        .font(Theme.serialNumberFont(size: 24, relativeTo: .body).weight(.semibold))
                                        .foregroundStyle(Theme.canvas)
                                }
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(user.displayName)
                                        .font(Theme.engravedSerif(size: 20, weight: .semibold))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text("Registry #\(String(user.userId))-AUTH")
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundStyle(Theme.inkTertiary)
                                }
                                Spacer()
                            }
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                            .onTapGesture {
                                devToolsTapCount += 1
                                if devToolsTapCount >= 3 {
                                    HapticManager.success()
                                    withAnimation { showDevTools = true }
                                    devToolsTapCount = 0
                                } else {
                                    HapticManager.selection()
                                }
                            }
                        }

                        // Navigation Links
                        VStack(spacing: 0) {
                            SettingsNavRow(icon: "chart.bar.fill", color: Theme.securityGold, title: "Trading Preferences", route: .tradingPreferences)
                            SettingsNavRow(icon: "bell.fill", color: Theme.bearRed, title: "Notifications & Alerts", route: .notifications)
                            SettingsNavRow(icon: "brain.head.profile", color: Theme.bullGreen, title: "AI & Analysis", route: .aiAnalysis)
                            SettingsNavRow(icon: "paintbrush.fill", color: Theme.inkSecondary, title: "Appearance & Display", route: .appearance)
                            SettingsNavRow(icon: "lock.shield.fill", color: Theme.securityGold, title: "Data & Privacy", route: .dataPrivacy)
                            SettingsNavRow(icon: "person.crop.circle.fill", color: Theme.inkPrimary, title: "Account & System", route: .account, isLast: !showDevTools)
                            
                            if showDevTools {
                                NavigationLink(destination: CrashLabView()) {
                                    HStack {
                                        SettingIcon(icon: "exclamationmark.shield.fill", color: Theme.bearRed)
                                        Text("CRASH LAB (\(CrashLog.shared.count()))")
                                            .font(Theme.officialStampFont(size: 9))
                                            .foregroundStyle(Theme.inkPrimary)
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.caption.weight(.bold))
                                            .foregroundStyle(Theme.inkTertiary.opacity(0.5))
                                    }
                                    .padding(.vertical, Theme.Spacing.standard)
                                    .padding(.horizontal, Theme.Spacing.card)
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)

                                GuillocheDivider()
                                    .padding(.leading, Theme.Spacing.card + 32 + Theme.Spacing.card)

                                SettingsNavRow(icon: "hammer.fill", color: Theme.bearRed, title: "Developer Tools", route: .devTools, isLast: true)
                            }
                        }
                        .banknoteCard()
                    }
                    .padding(.horizontal, Theme.Spacing.screen)
                    .padding(.vertical, Theme.Spacing.large)
                }
            }
            .crashGuard("SettingsScreen")
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .navigationDestination(for: SettingsRoute.self) { route in
                switch route {
                case .tradingPreferences:
                    TradingPreferencesSettingsView()
                case .notifications:
                    NotificationsSettingsView()
                case .aiAnalysis:
                    AIPrefSettingsView()
                case .appearance:
                    AppearanceSettingsView()
                case .dataPrivacy:
                    DataPrivacySettingsView()
                case .account:
                    AccountSettingsView()
                case .devTools:
                    DevToolsSettingsView()
                }
            }
        }
    }
}

private struct SettingsNavRow: View {
    let icon: String
    let color: Color
    let title: String
    let route: SettingsRoute
    var isLast: Bool = false

    var body: some View {
        NavigationLink(value: route) {
            VStack(spacing: 0) {
                HStack(spacing: Theme.Spacing.card) {
                    ZStack {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(color.opacity(0.12))
                            .frame(width: 36, height: 36)
                        Image(systemName: icon)
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(color)
                    }
                    Text(title.uppercased())
                        .font(Theme.officialStampFont(size: 12))
                        .foregroundStyle(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(Theme.inkTertiary.opacity(0.5))
                }
                .padding(.vertical, Theme.Spacing.standard)
                .padding(.horizontal, Theme.Spacing.card)
                .contentShape(Rectangle())

                if !isLast {
                    GuillocheDivider()
                        .padding(.leading, Theme.Spacing.card + 36 + Theme.Spacing.card)
                }
            }
        }
        .buttonStyle(.plain)
    }
}
