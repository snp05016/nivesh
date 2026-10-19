import SwiftUI

// MARK: - SettingsScreen

struct SettingsScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager

    // Trading. UX-18: rows with no consumer (Risk Tolerance, Default Exchange, Notification
    // Sound, Biometric for Trades, IPO Alerts) were removed rather than left as no-ops.
    @AppStorage("nivesh_defaultScanType") private var defaultScanType = "ask"
    @AppStorage("nivesh_autoRunOnTap") private var autoRunOnTap = false

    // Notifications
    @AppStorage("morningBriefTime") private var morningBriefTime: Double = 0

    // AI & Analysis
    @AppStorage("defaultDeepScan") private var defaultDeepScan = false
    @AppStorage("nivesh_autoRegenerateStale") private var autoRegenerateStale = false
    // Spec D20: reports are English only, so the language and debate-round pickers were removed.
    @AppStorage("nivesh_showGovernanceFirst") private var showGovernanceFirst = false

    // Appearance
    @AppStorage("selectedTheme") private var selectedThemeRaw = AppTheme.darkImmersive.rawValue
    @AppStorage("darkMode") private var darkMode = false
    @AppStorage("nivesh_fontSize") private var fontSize = "Standard"
    @AppStorage("nivesh_layoutDensity") private var layoutDensity = "Standard"
    @AppStorage("nivesh_defaultChartRange") private var defaultChartRange = "1M"
    @AppStorage("nivesh_reduceAnimations") private var reduceAnimations = false
    @AppStorage(HapticManager.enabledKey) private var hapticsEnabled = true
    @AppStorage("nivesh_showHindiLabels") private var showHindiLabels = true

    // Data & Privacy
    @AppStorage("biometricTimeout") private var biometricTimeoutRaw = "immediately"
    @AppStorage("nivesh_hidePortfolioValues") private var hidePortfolioValues = false

    // Account
    @AppStorage("currencyDisplay") private var currencyDisplay = "Lakhs/Crores"
    @AppStorage("homeAutoRefreshSeconds") private var homeAutoRefreshSeconds = "0"

    #if DEBUG
    // Dev (debug builds only)
    @State private var showDevTools = false
    @State private var devToolsTapCount = 0
    #endif
    @State private var showClearHistoryAlert = false
    @State private var showCalculators = false
    @State private var showDeleteAccount = false
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
        // Group, not NavigationStack: Settings is pushed onto HomeScreen's stack (no nesting).
        Group {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: Theme.Spacing.large) {
                        profileSection
                        tradingSection
                        notificationsSection
                        aiSection
                        appearanceSection
                        toolsSection
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
            // Sheet, not NavRow: CalculatorsView owns a NavigationStack (no nesting).
            .sheet(isPresented: $showCalculators) { CalculatorsView() }
            // FINSEC-03: in-app account deletion (App Store 5.1.1(v)); the sheet owns its NavigationStack.
            .sheet(isPresented: $showDeleteAccount) { DeleteAccountSheet().environmentObject(authManager) }
            .onAppear {
                // Older builds stored display text ("Ask Every Time", "Deep"); StockActionHubView reads lowercase keys.
                let normalized = defaultScanType == "Ask Every Time" ? "ask" : defaultScanType.lowercased()
                if normalized != defaultScanType { defaultScanType = normalized }
            }
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
                                Text("Account #\(String(user.userId))")
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
            PickerRow(icon: "sparkles", color: Theme.securityGold, title: "Default Scan Type", selection: $defaultScanType, options: ["ask", "standard", "deep", "extreme"],
                      labels: ["ask": "Ask Every Time", "standard": "Standard", "deep": "Deep", "extreme": "Extreme"])
            ToggleRow(icon: "bolt.fill", color: Theme.bullGreen, title: "Auto-run on Stock Tap", isOn: $autoRunOnTap)
            NavRow(icon: "tag", color: Theme.inkSecondary, title: "Sector Blacklist", destination: SectorBlacklistView())
        }
    }

    // MARK: - Notifications

    private var notificationsSection: some View {
        SettingsGroup(title: "NOTIFICATIONS", hindi: "सूचनाएं") {
            DateRow(icon: "clock.fill", color: Theme.securityGold, title: "Morning Brief Time", selection: morningBriefDate)
            NavRow(icon: "moon.zzz", color: Theme.inkSecondary, title: "Quiet Hours", destination: QuietHoursView())
            NavRow(icon: "bell.badge.circle", color: Theme.securityGold, title: "Notification Preferences", destination: NotificationPreferencesView())
        }
    }

    // MARK: - AI & Analysis

    private var aiSection: some View {
        SettingsGroup(title: "AI & ANALYSIS", hindi: "एआई विश्लेषण") {
            ToggleRow(icon: "waveform.badge.magnifyingglass", color: Theme.securityGold, title: "Deep Scan by Default", isOn: $defaultDeepScan)
            ToggleRow(icon: "arrow.triangle.2.circlepath", color: Theme.bearRed, title: "Auto-regenerate Stale", isOn: $autoRegenerateStale)
            ToggleRow(icon: "shield.lefthalf.filled", color: Theme.inkSecondary, title: "Show Governance First", isOn: $showGovernanceFirst)
        }
    }

    // MARK: - Appearance

    private var appearanceSection: some View {
        SettingsGroup(title: "APPEARANCE", hindi: "दिखावट") {
            ForEach(AppTheme.allCases, id: \.self) { theme in
                Button {
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
                .accessibilityAddTraits(theme.rawValue == selectedThemeRaw ? .isSelected : [])
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            }
            ToggleRow(icon: "moon.fill", color: .indigo, title: "Always Dark", isOn: $darkMode)
            PickerRow(icon: "textformat.size", color: Theme.inkSecondary, title: "Font Size", selection: $fontSize, options: ["Small", "Standard", "Large"])
            PickerRow(icon: "rectangle.3.group", color: Theme.inkSecondary, title: "Layout Density", selection: $layoutDensity, options: ["Compact", "Standard", "Spacious"])
            PickerRow(icon: "chart.xyaxis.line", color: Theme.securityGold, title: "Default Chart Range", selection: $defaultChartRange, options: ["1M", "3M", "6M", "1Y"])
            ToggleRow(icon: "hare", color: Theme.inkSecondary, title: "Reduce Animations", isOn: $reduceAnimations)
            ToggleRow(icon: "hand.tap", color: Theme.inkSecondary, title: "Haptic Feedback", isOn: $hapticsEnabled)
            ToggleRow(icon: "character.bubble", color: Theme.inkSecondary, title: "Show Hindi Labels", isOn: $showHindiLabels)
        }
    }

    // MARK: - Tools

    private var toolsSection: some View {
        SettingsGroup(title: "TOOLS", hindi: "उपकरण") {
            Button {
                HapticManager.selection()
                showCalculators = true
            } label: {
                RowLabel(icon: "function", color: Theme.securityGold, title: "CALCULATORS")
            }
            .buttonStyle(EKPressStyle())
        }
    }

    // MARK: - Data & Privacy

    private var dataSection: some View {
        SettingsGroup(title: "DATA & PRIVACY", hindi: "डेटा और गोपनीयता") {
            NavRow(icon: "doc.text", color: Theme.securityGold, title: "Saved Reports", destination: ReportManagerView(reportManager: reportManager), badge: "\(reportManager.savedReports.count)")
            NavRow(icon: "hand.raised", color: Theme.securityGold, title: "Privacy Policy", destination: DisclosureDetailView(key: .privacyPolicy))
            NavRow(icon: "doc.plaintext", color: Theme.securityGold, title: "Terms of Use", destination: DisclosureDetailView(key: .termsOfUse))
            NavRow(icon: "envelope", color: Theme.securityGold, title: "Contact & Grievance Officer", destination: DisclosureDetailView(key: .grievanceOfficer))
            NavRow(icon: "network", color: Theme.securityGold, title: DisclosureKey.dataSharingGovernance.displayTitle, destination: DisclosureDetailView(key: .dataSharingGovernance))
            Button {
                HapticManager.selection()
                URLCache.shared.removeAllCachedResponses()
            } label: {
                RowLabel(icon: "photo.on.rectangle.angled", color: Theme.inkSecondary, title: "CLEAR IMAGE CACHE")
            }
            .buttonStyle(EKPressStyle())
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            Button {
                HapticManager.selection()
                reportManager.savedReports.removeAll()
            } label: {
                RowLabel(icon: "brain.head.profile", color: Theme.bearRed, title: "CLEAR ANALYSIS CACHE")
            }
            .buttonStyle(EKPressStyle())
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            PickerRow(icon: "lock.shield", color: Theme.securityGold, title: "Biometric Lock", selection: $biometricTimeoutRaw, options: BiometricTimeout.allCases.map(\.rawValue),
                      labels: Dictionary(uniqueKeysWithValues: BiometricTimeout.allCases.map { ($0.rawValue, $0.label) }))
            ToggleRow(icon: "eye.slash", color: Theme.inkSecondary, title: "Hide Portfolio Values", isOn: $hidePortfolioValues)
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
            PickerRow(icon: "arrow.triangle.2.circlepath", color: Theme.inkSecondary, title: "Home Auto-refresh", selection: $homeAutoRefreshSeconds, options: ["0", "30", "60", "120"],
                      labels: ["0": "Off", "30": "30 sec", "60": "1 min", "120": "2 min"])
            Button(role: .destructive) { HapticManager.selection();  showClearHistoryAlert = true } label: {
                RowLabel(icon: "trash", color: Theme.bearRed, title: "VOID ALL RECORDS", tint: Theme.bearRed)
            }
            .buttonStyle(EKPressStyle())
            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            Button(role: .destructive) { HapticManager.selection();  authManager.logout() } label: {
                RowLabel(icon: "door.right.hand.open", color: Theme.bearRed, title: "SIGN OUT", tint: Theme.bearRed)
            }
            .buttonStyle(EKPressStyle())
            if authManager.isLoggedIn {
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                Button(role: .destructive) { HapticManager.selection(); showDeleteAccount = true } label: {
                    RowLabel(icon: "person.crop.circle.badge.xmark", color: Theme.bearRed, title: "DELETE ACCOUNT", tint: Theme.bearRed)
                }
                .buttonStyle(EKPressStyle())
            }
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
                    .accessibilityHidden(true)
                Text(title).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                    .accessibilityAddTraits(.isHeader)
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
        .accessibilityHidden(true)
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
    /// Human-readable text per stored option; options without an entry show as-is.
    var labels: [String: String] = [:]
    var body: some View {
        HStack {
            RowIcon(icon: icon, color: color)
            Text(title.uppercased()).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                .accessibilityHidden(true) // the Picker below carries the title
            Spacer()
            Picker(title, selection: $selection) {
                ForEach(options, id: \.self) { Text(labels[$0] ?? $0).tag($0) }
            }.labelsHidden().tint(Theme.inkSecondary)
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
                .accessibilityHidden(true) // the DatePicker below carries the title
            Spacer()
            DatePicker(title, selection: $selection, displayedComponents: .hourAndMinute).labelsHidden().tint(Theme.securityGold)
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
            .accessibilityElement(children: .combine)
        }
        .buttonStyle(EKPressStyle())
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}
