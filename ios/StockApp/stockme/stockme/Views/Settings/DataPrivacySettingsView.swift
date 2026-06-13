import SwiftUI

struct DataPrivacySettingsView: View {
    @EnvironmentObject var reportManager: LocalReportManager
    
    @AppStorage("nivesh_hidePortfolioValues") private var hidePortfolioValues = false
    @AppStorage("nivesh_biometricTradeLock") private var biometricTradeLock = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)
            
            List {
                Section {
                    NavigationLink(destination: ReportManagerView(reportManager: reportManager)) {
                        HStack {
                            SettingIcon(icon: "doc.text", color: Theme.securityGold)
                            Text("SAVED REPORTS")
                                .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                            Spacer()
                            Text("\(reportManager.savedReports.count)")
                                .font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.inkTertiary)
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                    Button {
                        HapticManager.selection()
                        URLCache.shared.removeAllCachedResponses()
                    } label: {
                        HStack {
                            SettingIcon(icon: "photo.on.rectangle.angled", color: Theme.inkSecondary)
                            Text("CLEAR IMAGE CACHE")
                                .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                            Spacer()
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                    Button {
                        HapticManager.selection()
                        reportManager.savedReports.removeAll()
                    } label: {
                        HStack {
                            SettingIcon(icon: "brain.head.profile", color: Theme.bearRed)
                            Text("CLEAR ANALYSIS CACHE")
                                .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                            Spacer()
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                    ToggleNoteRow(icon: "eye.slash", color: Theme.inkSecondary, title: "Hide Portfolio Values", isOn: $hidePortfolioValues)
                    ToggleNoteRow(icon: "touchid", color: Theme.securityGold, title: "Biometric for Trades", isOn: $biometricTradeLock)
                } header: {
                    Text("DATA & PRIVACY").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Data & Privacy")
        .navigationBarTitleDisplayMode(.inline)
    }
}
