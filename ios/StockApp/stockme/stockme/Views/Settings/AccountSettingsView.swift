import SwiftUI

struct AccountSettingsView: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager

    @AppStorage("currencyDisplay") private var currencyDisplay = "Lakhs/Crores"
    @AppStorage("homeAutoRefreshSeconds") private var homeAutoRefreshSeconds = "0"
    @AppStorage("ipoAlerts") private var ipoAlerts = false

    @State private var showClearHistoryAlert = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)

            List {
                Section {
                    if let user = authManager.currentUser {
                        HStack(spacing: Theme.Spacing.card) {
                            ZStack {
                                Circle().fill(Theme.securityGold).frame(width: 44, height: 44)
                                Text(String(user.displayName.prefix(1)).uppercased())
                                    .font(Theme.serialNumberFont(size: 18, relativeTo: .body).weight(.semibold))
                                    .foregroundStyle(Theme.canvas)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text(user.displayName)
                                    .font(Theme.engravedSerif(size: 15, weight: .semibold))
                                    .foregroundStyle(Theme.inkPrimary)
                                Text("Registry #\(String(user.userId))-AUTH")
                                    .font(Theme.serialNumberFont(size: 9))
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }

                    PickerNoteRow(icon: "indianrupeesign", color: Theme.securityGold, title: "Currency Format", selection: $currencyDisplay, options: ["Lakhs/Crores", "Absolute"])
                    PickerNoteRow(icon: "arrow.triangle.2.circlepath", color: Theme.inkSecondary, title: "Home Auto-refresh", selection: $homeAutoRefreshSeconds, options: ["0", "30", "60", "120"])
                    ToggleNoteRow(icon: "newspaper", color: Theme.securityGold, title: "IPO Alerts", isOn: $ipoAlerts)
                    
                    Button(role: .destructive) { showClearHistoryAlert = true } label: {
                        HStack {
                            SettingIcon(icon: "trash", color: Theme.bearRed)
                            Text("VOID ALL RECORDS").font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.bearRed)
                            Spacer()
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                    
                    Button(role: .destructive) { authManager.logout() } label: {
                        HStack {
                            SettingIcon(icon: "door.right.hand.open", color: Theme.bearRed)
                            Text("VOID SESSION").font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.bearRed)
                            Spacer()
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                } header: {
                    Text("ACCOUNT").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Account")
        .navigationBarTitleDisplayMode(.inline)
        .alert("Void All Records?", isPresented: $showClearHistoryAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Void", role: .destructive) { reportManager.savedReports.removeAll() }
        }
    }
}
