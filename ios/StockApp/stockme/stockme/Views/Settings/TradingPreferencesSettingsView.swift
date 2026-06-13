import SwiftUI

struct TradingPreferencesSettingsView: View {
    @AppStorage("nivesh_defaultScanType") private var defaultScanType = "ask"
    @AppStorage("nivesh_autoRunOnTap") private var autoRunOnTap = false
    @AppStorage("nivesh_riskTolerance") private var riskTolerance = "Moderate"
    @AppStorage("nivesh_defaultExchange") private var defaultExchange = "Auto"
    @AppStorage("nivesh_minMarketCap") private var minMarketCap = "Any"

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)
            
            List {
                Section {
                    PickerNoteRow(icon: "sparkles", color: Theme.securityGold, title: "Default Scan Type", selection: $defaultScanType, options: ["Ask Every Time", "Standard", "Deep", "Extreme"])
                    ToggleNoteRow(icon: "bolt.fill", color: Theme.bullGreen, title: "Auto-run on Stock Tap", isOn: $autoRunOnTap)
                    PickerNoteRow(icon: "shield.checkered", color: Theme.securityGold, title: "Risk Tolerance", selection: $riskTolerance, options: ["Conservative", "Moderate", "Aggressive"])
                    PickerNoteRow(icon: "building.2", color: Theme.inkSecondary, title: "Default Exchange", selection: $defaultExchange, options: ["Auto", "NSE", "BSE"])
                    NavigationLink(destination: SectorBlacklistView()) {
                        HStack {
                            SettingIcon(icon: "tag", color: Theme.inkSecondary)
                            Text("SECTOR BLACKLIST")
                                .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                            Spacer()
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                    PickerNoteRow(icon: "chart.bar", color: Theme.inkSecondary, title: "Min Market Cap", selection: $minMarketCap, options: ["Any", "Large (>20K Cr)", "Mid (5-20K Cr)", "Small (<5K Cr)"])
                } header: {
                    Text("TRADING PREFERENCES").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Trading Preferences")
        .navigationBarTitleDisplayMode(.inline)
    }
}
