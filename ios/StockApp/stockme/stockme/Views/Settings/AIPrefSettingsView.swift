import SwiftUI

struct AIPrefSettingsView: View {
    @AppStorage("defaultDeepScan") private var defaultDeepScan = false
    @AppStorage("nivesh_autoRegenerateStale") private var autoRegenerateStale = false
    @AppStorage("nivesh_minConfidenceAlert") private var minConfidenceAlert = "50%"
    @AppStorage("nivesh_analysisLanguage") private var analysisLanguage = "English"
    @AppStorage("nivesh_debateRounds") private var debateRounds = "1"
    @AppStorage("nivesh_showGovernanceFirst") private var showGovernanceFirst = false
    @AppStorage("nivesh_alertOnBuy") private var alertOnBuy = true
    @AppStorage("nivesh_alertOnSell") private var alertOnSell = true
    @AppStorage("nivesh_muteHoldSignals") private var muteHoldSignals = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)
            
            List {
                Section {
                    ToggleNoteRow(icon: "waveform.badge.magnifyingglass", color: Theme.securityGold, title: "Deep Scan by Default", isOn: $defaultDeepScan)
                    ToggleNoteRow(icon: "arrow.triangle.2.circlepath", color: Theme.bearRed, title: "Auto-regenerate Stale", isOn: $autoRegenerateStale)
                    PickerNoteRow(icon: "gauge.with.dots.needle.33percent", color: Theme.bullGreen, title: "Min Confidence Alert", selection: $minConfidenceAlert, options: ["50%", "65%", "75%", "90%"])
                    PickerNoteRow(icon: "globe", color: Theme.inkSecondary, title: "Analysis Language", selection: $analysisLanguage, options: ["English", "Hindi", "Hinglish"])
                    PickerNoteRow(icon: "arrow.triangle.branch", color: Theme.securityGold, title: "Debate Rounds", selection: $debateRounds, options: ["1", "2", "3"])
                    ToggleNoteRow(icon: "shield.lefthalf.filled", color: Theme.inkSecondary, title: "Show Governance First", isOn: $showGovernanceFirst)
                    ToggleNoteRow(icon: "arrow.up.circle", color: Theme.bullGreen, title: "Alert on BUY", isOn: $alertOnBuy)
                    ToggleNoteRow(icon: "arrow.down.circle", color: Theme.bearRed, title: "Alert on SELL", isOn: $alertOnSell)
                    ToggleNoteRow(icon: "pause.circle", color: Theme.holdAmber, title: "Mute HOLD Signals", isOn: $muteHoldSignals)
                } header: {
                    Text("AI & ANALYSIS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("AI & Analysis")
        .navigationBarTitleDisplayMode(.inline)
    }
}
