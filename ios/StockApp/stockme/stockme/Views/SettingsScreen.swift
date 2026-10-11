import SwiftUI

// MARK: - SettingsScreen

struct SettingsScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager

    // Trading
    @AppStorage("nivesh_defaultScanType") private var defaultScanType = "ask"
    @AppStorage("nivesh_autoRunOnTap") private var autoRunOnTap = false
    @AppStorage("nivesh_riskTolerance") private var riskTolerance = "Moderate"
    @AppStorage("nivesh_defaultExchange") private var defaultExchange = "Auto"
    @AppStorage("nivesh_minMarketCap") private var minMarketCap = "Any"

    // Notifications
    @AppStorage("nivesh_signalChangeAlerts") private var signalChangeAlerts = false
    @AppStorage("morningBriefTime") private var morningBriefTime: Double = 0
    @AppStorage("notificationSound") private var notificationSound = "Default"

    // AI & Analysis
    @AppStorage("defaultDeepScan") private var defaultDeepScan = false
    @AppStorage("nivesh_autoRegenerateStale") private var autoRegenerateStale = false
    @AppStorage("nivesh_minConfidenceAlert") private var minConfidenceAlert = "50%"
    @AppStorage("nivesh_analysisLanguage") private var analysisLanguage = "English"
    @AppStorage("nivesh_debateRounds") private var debateRounds = "1"
    @AppStorage("nivesh_showGovernanceFirst") private var showGovernanceFirst = false
    @AppStorage("nivesh_alertOnBuy") private var alertOnBuy = true
    @AppStorage("nivesh_alertOnSell") private var alertOnSell = true
    @AppStorage("nivesh_muteHoldSignals") private var muteHoldSignals = false

    // Appearance
    @AppStorage("selectedTheme") private var selectedThemeRaw = AppTheme.darkImmersive.rawValue
    @AppStorage("darkMode") private var darkMode = false
    @AppStorage("nivesh_fontSize") private var fontSize = "Standard"
    @AppStorage("nivesh_layoutDensity") private var layoutDensity = "Standard"
    @AppStorage("nivesh_defaultChartRange") private var defaultChartRange = "1M"
    @AppStorage("nivesh_reduceAnimations") private var reduceAnimations = false
    @AppStorage("nivesh_showHindiLabels") private var showHindiLabels = true

    // Data & Privacy
    @AppStorage("biometricTimeout") private var biometricTimeoutRaw = "immediately"
    @AppStorage("nivesh_hidePortfolioValues") private var hidePortfolioValues = false
    @AppStorage("nivesh_biometricTradeLock") private var biometricTradeLock = false

    // Account
    @AppStorage("currencyDisplay") private var currencyDisplay = "Lakhs/Crores"
    @AppStorage("homeAutoRefreshSeconds") private var homeAutoRefreshSeconds = "0"
    @AppStorage("ipoAlerts") private var ipoAlerts = false

    #if DEBUG
    // Dev (debug builds only)
    @State private var showDevTools = false
    @State private var devToolsTapCount = 0
    #endif
    @State private var showClearHistoryAlert = false
    @StateObject private var notificationManager = NotificationManager.shared

    private var morningBriefDate: Binding<Date> {
        Binding(get: {
            Calendar.current.startOfDay(for: Date()).addingTimeInterval(morningBriefTime)
        }, set: { newDate in
            let c = Calendar.current.dateComponents([.hour, .minute], from: newDate)
            morningBriefTime = Double((c.hour ?? 0) * 3600 + (c.minute ?? 0) * 60)
            NotificationManager.shared.scheduleMorningBrief()
        })
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: Theme.Spacing.large) {
                        profileSection
                        tradingSection
                        notificationsSection
                        aiSection
                        appearanceSection
                        dataSection
                        accountSection
                        #if DEBUG
                        if showDevTools { devSection }
                        #endif
                    }
                    .padding(.horizontal, Theme.Spacing.screen)
                    .padding(.vertical, Theme.Spacing.large)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .banknoteDialog(
                "Void All Records?",
                isPresented: $showClearHistoryAlert,
                message: "This permanently clears all saved analysis reports.",
                buttons: [
                    .init("Void", role: .destructive) { reportManager.savedReports.removeAll() },
                    .cancel()
                ]
            )
        }
    }

    // MARK: - Profile

    private var profileSection: some View {
        Group {
            if let user = authManager.currentUser {
                VStack(spacing: Theme.Spacing.none) {
                    NavigationLink(destination: ProfileSettingsView()) {
                        HStack(spacing: Theme.Spacing.card) {
                            ZStack {
                                Circle().fill(Theme.securityGold).frame(width: 56, height: 56)
                                    .shadow(color: Theme.securityGold.opacity(0.3), radius: 8, y: 4)
                                Text(String(user.displayName.prefix(1)).uppercased())
                                    .font(Theme.serialNumberFont(size: 24, relativeTo: .body).weight(.semibold))
                                    .foregroundStyle(Theme.canvas)
                            }
                            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                Text(user.displayName)
                                    .font(Theme.engravedSerif(size: 20, weight: .semibold)).foregroundStyle(Theme.inkPrimary)
                                Text("Registry #\(String(user.userId))-AUTH")
                                    .font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.inkTertiary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .padding(Theme.Spacing.card)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(EKPressStyle())
                    #if DEBUG
                    .simultaneousGesture(TapGesture().onEnded {
                        devToolsTapCount += 1
                        if devToolsTapCount >= 3 {
                            HapticManager.success()
                            withAnimation { showDevTools = true }
                            devToolsTapCount = 0
                        } else {
                            HapticManager.selection()
                        }
                    })
                    #endif
                }
                .banknoteCard()
            }
        }
    }

    // MARK: - Trading Preferences

    private var tradingSection: some View {
        SettingsGroup(title: "TRADING PREFERENCES", hindi: "व्यापार प्राथमिकताएं") {
            PickerRow(icon: "sparkles", color: Theme.securityGold, title: "Default Scan Type", selection: $defaultScanType, options: ["Ask Every Time", "Standard", "Deep", "Extreme"])
            ToggleRow(icon: "bolt.fill", color: Theme.bullGreen, title: "Auto-run on Stock Tap", isOn: $autoRunOnTap)
            PickerRow(icon: "shield.checkered", color: Theme.securityGold, title: "Risk Tolerance", selection: $riskTolerance, options: ["Conservative", "Moderate", "Aggressive"])
            PickerRow(icon: "building.2", color: Theme.inkSecondary, title: "Default Exchange", selection: $defaultExchange, options: ["Auto", "NSE", "BSE"])
            NavRow(icon: "tag", color: Theme.inkSecondary, title: "Sector Blacklist", destination: SectorBlacklistView())
            PickerRow(icon: "chart.bar", color: Theme.inkSecondary, title: "Min Market Cap", selection: $minMarketCap, options: ["Any", "Large (>20K Cr)", "Mid (5-20K Cr)", "Small (<5K Cr)"])
        }
    }

    // MARK: - Notifications

    private var notificationsSection: some View {
        SettingsGroup(title: "NOTIFICATIONS", hindi: "सूचनाएं") {
            ToggleRow(icon: "bell.badge", color: Theme.bearRed, title: "Signal Change Alerts", isOn: $signalChangeAlerts)
            DateRow(icon: "clock.fill", color: Theme.securityGold, title: "Morning Brief Time", selection: morningBriefDate)
            PickerRow(icon: "speaker.wave.2", color: Theme.bearRed, title: "Notification Sound", selection: $notificationSound, options: ["Default", "rupee_rustle.mp3"])
            NavRow(icon: "moon.zzz", color: Theme.inkSecondary, title: "Quiet Hours", destination: QuietHoursView())
            NavRow(icon: "bell.badge.circle", color: Theme.securityGold, title: "Notification Preferences", destination: NotificationPreferencesView())
        }
    }

    // MARK: - AI & Analysis

    private var aiSection: some View {
        SettingsGroup(title: "AI & ANALYSIS", hindi: "एआई विश्लेषण") {
            ToggleRow(icon: "waveform.badge.magnifyingglass", color: Theme.securityGold, title: "Deep Scan by Default", isOn: $defaultDeepScan)
            ToggleRow(icon: "arrow.triangle.2.circlepath", color: Theme.bearRed, title: "Auto-regenerate Stale", isOn: $autoRegenerateStale)
            PickerRow(icon: "gauge.with.dots.needle.33percent", color: Theme.bullGreen, title: "Min Confidence Alert", selection: $minConfidenceAlert, options: ["50%", "65%", "75%", "90%"])
            PickerRow(icon: "globe", color: Theme.inkSecondary, title: "Analysis Language", selection: $analysisLanguage, options: ["English", "Hindi", "Hinglish"])
            PickerRow(icon: "arrow.triangle.branch", color: Theme.securityGold, title: "Debate Rounds", selection: $debateRounds, options: ["1", "2", "3"])
            ToggleRow(icon: "shield.lefthalf.filled", color: Theme.inkSecondary, title: "Show Governance First", isOn: $showGovernanceFirst)
            ToggleRow(icon: "arrow.up.circle", color: Theme.bullGreen, title: "Alert on BUY", isOn: $alertOnBuy)
            ToggleRow(icon: "arrow.down.circle", color: Theme.bearRed, title: "Alert on SELL", isOn: $alertOnSell)
            ToggleRow(icon: "pause.circle", color: Theme.holdAmber, title: "Mute HOLD Signals", isOn: $muteHoldSignals)
        }
    }

    // MARK: - Appearance

    private var appearanceSection: some View {
        SettingsGroup(title: "APPEARANCE", hindi: "दिखावट") {
            ForEach(AppTheme.allCases, id: \.self) { theme in
                Button { HapticManager.selection(); 
    HapticManager.selection()
                    HapticManager.impact(.medium)
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.72)) {
                        selectedThemeRaw = theme.rawValue
                        ThemeManager.shared.current = theme
                    }
                } label: {
                    HStack(spacing: Theme.Spacing.standard) {
                        Circle().fill(theme.swatchColor).frame(width: 24, height: 24)
                        Text(theme.displayName)
                            .font(Theme.engravedSerif(size: 14)).foregroundStyle(Theme.inkPrimary)
                        Spacer()
                        if theme.rawValue == selectedThemeRaw {
                            Image(systemName: "checkmark").foregroundStyle(Theme.securityGold)
                        }
                    }
                    .padding(.vertical, Theme.Spacing.standard)
                    .contentShape(Rectangle())
                }
                .buttonStyle(EKPressStyle())
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            }
            ToggleRow(icon: "moon.fill", color: .indigo, title: "Dark Inks", isOn: $darkMode)
            PickerRow(icon: "textformat.size", color: Theme.inkSecondary, title: "Font Size", selection: $fontSize, options: ["Small", "Standard", "Large"])
            PickerRow(icon: "rectangle.3.group", color: Theme.inkSecondary, title: "Layout Density", selection: $layoutDensity, options: ["Compact", "Standard", "Spacious"])
            PickerRow(icon: "chart.xyaxis.line", color: Theme.securityGold, title: "Default Chart Range", selection: $defaultChartRange, options: ["1M", "3M", "6M", "1Y"])
            ToggleRow(icon: "hare", color: Theme.inkSecondary, title: "Reduce Animations", isOn: $reduceAnimations)
            ToggleRow(icon: "character.bubble", color: Theme.inkSecondary, title: "Show Hindi Labels", isOn: $showHindiLabels)
        }
    }

    // MARK: - Data & Privacy

    private var dataSection: some View {
        SettingsGroup(title: "DATA & PRIVACY", hindi: "डेटा और गोपनीयता") {
            NavRow(icon: "doc.text", color: Theme.securityGold, title: "Saved Reports", destination: ReportManagerView(reportManager: reportManager), badge: "\(reportManager.savedReports.count)")
            NavRow(icon: "hand.raised", color: Theme.securityGold, title: "Privacy Policy", destination: DisclosureDetailView(key: .privacyPolicy))
            NavRow(icon: "network", color: Theme.securityGold, title: "Data Sharing Governance", destination: DisclosureDetailView(key: .dataSharingGovernance))
            Button { HapticManager.selection(); 
    HapticManager.selection()
                HapticManager.selection()
                URLCache.shared.removeAllCachedResponses()
            } label: {
                RowLabel(icon: "photo.on.rectangle.angled", color: Theme.inkSecondary, title: "CLEAR IMAGE CACHE")
            }
            .buttonStyle(EKPressStyle())
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            Button { HapticManager.selection(); 
    HapticManager.selection()
                HapticManager.selection()
                reportManager.savedReports.removeAll()
            } label: {
                RowLabel(icon: "brain.head.profile", color: Theme.bearRed, title: "CLEAR ANALYSIS CACHE")
            }
            .buttonStyle(EKPressStyle())
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            PickerRow(icon: "lock.shield", color: Theme.securityGold, title: "Biometric Lock", selection: $biometricTimeoutRaw, options: ["immediately", "1min", "5min", "15min", "never"])
            ToggleRow(icon: "eye.slash", color: Theme.inkSecondary, title: "Hide Portfolio Values", isOn: $hidePortfolioValues)
            ToggleRow(icon: "touchid", color: Theme.securityGold, title: "Biometric for Trades", isOn: $biometricTradeLock)
        }
    }

    // MARK: - Account

    private var accountSection: some View {
        SettingsGroup(title: "ACCOUNT", hindi: "खाता") {
            NavRow(icon: "crown.fill", color: Theme.securityGold, title: "Subscription", destination: SubscriptionManagementView())
            // UX-22/IOSUI-13: password change, 2FA and sessions are simulated; Debug only.
            if ReleaseGate.demoFeatures {
                NavRow(icon: "lock.shield.fill", color: Theme.securityGold, title: "Account Security", destination: AccountSecurityView().demoDataRibbon())
            }
            PickerRow(icon: "indianrupeesign", color: Theme.securityGold, title: "Currency Format", selection: $currencyDisplay, options: ["Lakhs/Crores", "Absolute"])
            PickerRow(icon: "arrow.triangle.2.circlepath", color: Theme.inkSecondary, title: "Home Auto-refresh", selection: $homeAutoRefreshSeconds, options: ["0", "30", "60", "120"])
            ToggleRow(icon: "newspaper", color: Theme.securityGold, title: "IPO Alerts", isOn: $ipoAlerts)
            Button(role: .destructive) { HapticManager.selection();  showClearHistoryAlert = true } label: {
                RowLabel(icon: "trash", color: Theme.bearRed, title: "VOID ALL RECORDS", tint: Theme.bearRed)
            }
            .buttonStyle(EKPressStyle())
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            Button(role: .destructive) { HapticManager.selection();  authManager.logout() } label: {
                RowLabel(icon: "door.right.hand.open", color: Theme.bearRed, title: "VOID SESSION", tint: Theme.bearRed)
            }
            .buttonStyle(EKPressStyle())
        }
    }

    // MARK: - Dev Tools

    #if DEBUG
    private var devSection: some View {
        SettingsGroup(title: "DEVELOPER TOOLS", hindi: "डेव टूल्स") {
            NavRow(icon: "exclamationmark.shield.fill", color: Theme.bearRed, title: "Crash Lab (\(CrashLog.shared.count()))", destination: CrashLabView())
        }
    }
    #endif
}

// MARK: - Reusable Row Components (private to this file)

private struct SettingsGroup<Content: View>: View {
    let title: String
    let hindi: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
                Text(hindi).font(Theme.hindiFont(size: 9)).foregroundStyle(Theme.inkSecondary)
                Text(title).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
            }
            .padding(.horizontal, Theme.Spacing.small)

            VStack(spacing: Theme.Spacing.none) { content }
                .banknoteCard()
        }
    }
}

private struct RowIcon: View {
    let icon: String; let color: Color
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(color.opacity(0.08)).frame(width: 32, height: 32)
            Image(systemName: icon)
                .font(.subheadline.weight(.medium)).foregroundStyle(color.opacity(0.7))
        }
        .padding(.trailing, Theme.Spacing.standard)
    }
}

private struct RowLabel: View {
    let icon: String; let color: Color; let title: String; var tint: Color? = nil
    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RowIcon(icon: icon, color: color)
            Text(title).font(Theme.officialStampFont(size: 9)).foregroundStyle(tint ?? Theme.inkPrimary)
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        .contentShape(Rectangle())
    }
}

private struct ToggleRow: View {
    let icon: String; let color: Color; let title: String; @Binding var isOn: Bool
    var body: some View {
        HStack {
            RowIcon(icon: icon, color: color)
            Toggle(isOn: $isOn) {
                Text(title.uppercased()).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
            }.tint(Theme.securityGold)
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

private struct PickerRow: View {
    let icon: String; let color: Color; let title: String; @Binding var selection: String; let options: [String]
    var body: some View {
        HStack {
            RowIcon(icon: icon, color: color)
            Text(title.uppercased()).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
            Spacer()
            Picker("", selection: $selection) {
                ForEach(options, id: \.self) { Text($0).tag($0) }
            }.tint(Theme.inkSecondary)
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

private struct DateRow: View {
    let icon: String; let color: Color; let title: String; @Binding var selection: Date
    var body: some View {
        HStack {
            RowIcon(icon: icon, color: color)
            Text(title.uppercased()).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
            Spacer()
            DatePicker("", selection: $selection, displayedComponents: .hourAndMinute).labelsHidden().tint(Theme.securityGold)
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

private struct NavRow<Destination: View>: View {
    let icon: String; let color: Color; let title: String; let destination: Destination; var badge: String? = nil
    var body: some View {
        NavigationLink(destination: destination) {
            HStack {
                RowIcon(icon: icon, color: color)
                Text(title.uppercased()).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                Spacer()
                if let badge = badge {
                    Text(badge).font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.inkTertiary)
                }
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.horizontal, Theme.Spacing.card)
            .contentShape(Rectangle())
        }
        .buttonStyle(EKPressStyle())
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}
