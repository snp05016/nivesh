import SwiftUI
import UserNotifications

struct SettingsScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager

    @AppStorage("biometricTimeout") private var biometricTimeoutRaw = "immediately"
    @AppStorage("darkMode") private var darkMode = false
    @AppStorage("pushNotifications") private var pushNotifications = true
    @AppStorage("morningBriefTime") private var morningBriefTime: Double = 0 // storing seconds from midnight
    @AppStorage("defaultDeepScan") private var defaultDeepScan = false
    @AppStorage("dataRefreshRate") private var dataRefreshRate = "Real-time"
    @AppStorage("homeAutoRefreshSeconds") private var homeAutoRefreshSeconds = "0"
    @AppStorage("currencyDisplay") private var currencyDisplay = "Lakhs/Crores"
    @AppStorage("ipoAlerts") private var ipoAlerts = false
    @AppStorage("dev_welcome_notification") private var devWelcomeNotification = false
    @AppStorage("notificationSound") private var notificationSound = "Default"
    @AppStorage("selectedTheme") private var selectedThemeRaw = AppTheme.darkImmersive.rawValue

    // Trading Preferences
    @AppStorage("nivesh_defaultScanType") private var defaultScanType = "ask"
    @AppStorage("nivesh_autoRunOnTap") private var autoRunOnTap = false
    @AppStorage("nivesh_riskTolerance") private var riskTolerance = "Moderate"
    @AppStorage("nivesh_defaultExchange") private var defaultExchange = "Auto"
    @AppStorage("nivesh_minMarketCap") private var minMarketCap = "Any"
    @AppStorage("nivesh_signalChangeAlerts") private var signalChangeAlerts = false

    // AI & Analysis
    @AppStorage("nivesh_autoRegenerateStale") private var autoRegenerateStale = false
    @AppStorage("nivesh_minConfidenceAlert") private var minConfidenceAlert = "50%"
    @AppStorage("nivesh_analysisLanguage") private var analysisLanguage = "English"
    @AppStorage("nivesh_debateRounds") private var debateRounds = "1"
    @AppStorage("nivesh_showGovernanceFirst") private var showGovernanceFirst = false
    @AppStorage("nivesh_alertOnBuy") private var alertOnBuy = true
    @AppStorage("nivesh_alertOnSell") private var alertOnSell = true
    @AppStorage("nivesh_muteHoldSignals") private var muteHoldSignals = false

    // Appearance
    @AppStorage("nivesh_fontSize") private var fontSize = "Standard"
    @AppStorage("nivesh_layoutDensity") private var layoutDensity = "Standard"
    @AppStorage("nivesh_defaultChartRange") private var defaultChartRange = "1M"
    @AppStorage("nivesh_reduceAnimations") private var reduceAnimations = false
    @AppStorage("nivesh_showHindiLabels") private var showHindiLabels = true

    // Data & Privacy
    @AppStorage("nivesh_hidePortfolioValues") private var hidePortfolioValues = false
    @AppStorage("nivesh_biometricTradeLock") private var biometricTradeLock = false

    @StateObject private var notificationManager = NotificationManager.shared

    @State private var showClearHistoryAlert = false
    @State private var showServerURLSheet = false
    @State private var serverURLDraft = ""
    @State private var serverTestResult: String? = nil
    @State private var serverTestLoading = false

    // Dev Tools
    @State private var showDevTools = false
    @State private var devToolsTapCount = 0
    @State private var showTestNotifSheet = false
    @State private var testNotifTicker = ""
    @State private var testNotifExchange = "NSE"
    @State private var notifToastMessage: String? = nil
    @State private var notifPermissionStatus: String = "Not Asked"
    @State private var youtubeHarvestLoading = false

    private var morningBriefDate: Binding<Date> {
        Binding(
            get: {
                let calendar = Calendar.current
                let startOfDay = calendar.startOfDay(for: Date())
                return startOfDay.addingTimeInterval(morningBriefTime)
            },
            set: { newDate in
                let calendar = Calendar.current
                let components = calendar.dateComponents([.hour, .minute], from: newDate)
                let hours = components.hour ?? 0
                let minutes = components.minute ?? 0
                morningBriefTime = Double(hours * 3600 + minutes * 60)
            }
        )
    }

    var body: some View {
        NavigationStack {
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
                        }

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

                    Section {
                        ToggleNoteRow(icon: "bell.badge", color: Theme.bearRed, title: "Signal Change Alerts", isOn: $signalChangeAlerts)
                        DatePickerNoteRow(icon: "clock.fill", color: Theme.securityGold, title: "Morning Brief Time", selection: morningBriefDate)
                        PickerNoteRow(icon: "speaker.wave.2", color: Theme.bearRed, title: "Notification Sound", selection: $notificationSound, options: ["Default", "rupee_rustle.mp3"])
                        NavigationLink(destination: QuietHoursView()) {
                            HStack {
                                SettingIcon(icon: "moon.zzz", color: Theme.inkSecondary)
                                Text("QUIET HOURS")
                                    .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                    } header: {
                        Text("NOTIFICATIONS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

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

                    Section {
                        // Denomination theme
                        ForEach(AppTheme.allCases, id: \.self) { theme in
                            HStack {
                                Circle().fill(theme == .darkImmersive ? Color(uiColor:"C8A800") : Color(uiColor:"8B5A42")).frame(width: 24, height: 24)
                                Text(verbatim: theme == .darkImmersive ? "₹200 Dark" : "₹10 Classic")
                                    .font(Theme.engravedSerif(size: 14)).foregroundStyle(Theme.inkPrimary)
                                Spacer()
                                if theme.rawValue == selectedThemeRaw {
                                    Image(systemName: "checkmark").foregroundStyle(Theme.securityGold)
                                }
                            }
                            .contentShape(Rectangle())
                            .onTapGesture {
                                HapticManager.impact(.medium)
                                withAnimation(.spring(response: 0.4, dampingFraction: 0.72)) {
                                    selectedThemeRaw = theme.rawValue
                                    ThemeManager.shared.current = theme
                                }
                            }
                        }

                        ToggleNoteRow(icon: "moon.fill", color: .indigo, title: "Dark Inks", isOn: $darkMode)
                        PickerNoteRow(icon: "textformat.size", color: Theme.inkSecondary, title: "Font Size", selection: $fontSize, options: ["Small", "Standard", "Large"])
                        PickerNoteRow(icon: "rectangle.3.group", color: Theme.inkSecondary, title: "Layout Density", selection: $layoutDensity, options: ["Compact", "Standard", "Spacious"])
                        PickerNoteRow(icon: "chart.xyaxis.line", color: Theme.securityGold, title: "Default Chart Range", selection: $defaultChartRange, options: ["1M", "3M", "6M", "1Y"])
                        ToggleNoteRow(icon: "hare", color: Theme.inkSecondary, title: "Reduce Animations", isOn: $reduceAnimations)
                        ToggleNoteRow(icon: "character.bubble", color: Theme.inkSecondary, title: "Show Hindi Labels", isOn: $showHindiLabels)
                    } header: {
                        Text("APPEARANCE").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

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

                    Section {
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

                    if showDevTools {
                        Section {
                            Button("Push Test Notification") { showTestNotifSheet = true }
                            Button("Push Morning Summary Now") { pushMorningSummary() }
                        } header: {
                            Text("DEVELOPER TOOLS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .alert("Void All Records?", isPresented: $showClearHistoryAlert) {
                Button("Cancel", role: .cancel) {}
                Button("Void", role: .destructive) { reportManager.savedReports.removeAll() }
            }
        }
    }

    private func pushMorningSummary() {
        Task {
            do {
                let payload = try await NetworkManager.shared.sendMorningSummaryNotification()
                NetworkManager.shared.scheduleLocalNotification(
                    title: payload.title,
                    body: payload.body,
                    userInfo: payload.data.map {
                        Dictionary(uniqueKeysWithValues: $0.map { ($0.key, $0.value as Any) })
                    } ?? [:]
                )
                notifToastMessage = "Morning summary sent"
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
            } catch {
                notifToastMessage = "Failed: \(error.localizedDescription)"
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
            }
        }
    }

    private var devToolsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
                Text("डेव टूल्स")
                    .font(Theme.hindiFont(size: 9))
                    .foregroundStyle(Theme.inkSecondary)
                Text("DEVELOPER TOOLS")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.bearRed)
                BanknoteSignalBadge(text: "DEV ONLY", color: Theme.bearRed, rotation: -2)
                    .scaleEffect(0.7)
            }
            .padding(.horizontal, Theme.Spacing.small)

            VStack(spacing: Theme.Spacing.none) {
                // Row 1 — Test Push Notification
                HStack {
                    SettingIcon(icon: "bell.badge.fill", color: Theme.holdAmber)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("TEST STOCK NOTIFICATION")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("Send a test push for any stock")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(Theme.securityGold)
                }
                .padding(.vertical, Theme.Spacing.standard)
                .contentShape(Rectangle())
                .onTapGesture { showTestNotifSheet = true }

                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                // Row 2 — Morning Summary Push
                HStack {
                    SettingIcon(icon: "sun.horizon.fill", color: Theme.securityGold)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("PUSH MORNING SUMMARY NOW")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("Send today's brief as a notification")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                }
                .padding(.vertical, Theme.Spacing.standard)
                .contentShape(Rectangle())
                .onTapGesture {
                    Task {
                        do {
                            let payload = try await NetworkManager.shared.sendMorningSummaryNotification()
                            NetworkManager.shared.scheduleLocalNotification(title: payload.title, body: payload.body, userInfo: payload.data.map { Dictionary(uniqueKeysWithValues: $0.map { ($0.key, $0.value as Any) }) } ?? [:])
                            notifToastMessage = "Morning summary sent"
                            DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
                        } catch {
                            notifToastMessage = "Failed: \(error.localizedDescription)"
                            DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
                        }
                    }
                }

                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                // Row 3 — Harvest YouTube Now
                HStack {
                    SettingIcon(icon: "play.circle.fill", color: Theme.bullGreen)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("HARVEST YOUTUBE NOW")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("Run channel + portfolio harvest on demand")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    if youtubeHarvestLoading {
                        ProgressView().tint(Theme.inkSecondary)
                    } else {
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundStyle(Theme.securityGold)
                    }
                }
                .padding(.vertical, Theme.Spacing.standard)
                .contentShape(Rectangle())
                .onTapGesture {
                    youtubeHarvestLoading = true
                    Task {
                        do {
                            let result = try await NetworkManager.shared.triggerYouTubeHarvest()
                            let ch = result.channel_harvest.videos_added ?? 0
                            let pf = result.portfolio_harvest.videos_added ?? 0
                            notifToastMessage = "Harvest done: \(ch) channel + \(pf) portfolio videos"
                            youtubeHarvestLoading = false
                            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { notifToastMessage = nil }
                        } catch {
                            notifToastMessage = "Harvest failed: \(error.localizedDescription)"
                            youtubeHarvestLoading = false
                            DispatchQueue.main.asyncAfter(deadline: .now() + 3) { notifToastMessage = nil }
                        }
                    }
                }

                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                // Row 4 — Notification Permission Status
                HStack {
                    SettingIcon(icon: "bell.fill", color: Theme.inkSecondary)
                    Text("NOTIFICATION STATUS")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkPrimary)
                    Spacer()
                    Text(notifPermissionStatus)
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundStyle(notifPermissionStatus == "Granted ✓" ? Theme.bullGreen : notifPermissionStatus == "Denied ✗" ? Theme.bearRed : Theme.holdAmber)
                }
                .padding(.vertical, Theme.Spacing.standard)
                .contentShape(Rectangle())
                .onTapGesture {
                    if notifPermissionStatus == "Denied ✗" {
                        if let url = URL(string: UIApplication.openSettingsURLString) {
                            UIApplication.shared.open(url)
                        }
                    }
                    // Refresh status
                    UNUserNotificationCenter.current().getNotificationSettings { settings in
                        DispatchQueue.main.async {
                            switch settings.authorizationStatus {
                            case .authorized: notifPermissionStatus = "Granted ✓"
                            case .denied: notifPermissionStatus = "Denied ✗"
                            default: notifPermissionStatus = "Not Asked"
                            }
                        }
                    }
                }

                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                // Row 4b — Welcome Notification Toggle
                HStack {
                    SettingIcon(icon: "party.popper.fill", color: Theme.bullGreen)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("WELCOME NOTIFICATION")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("Fire 'Welcome to Nivesh' on every app open")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    Toggle("", isOn: $devWelcomeNotification)
                        .tint(Theme.securityGold)
                        .labelsHidden()
                }
                .padding(.vertical, Theme.Spacing.standard)

                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                // Row 5 — APNs Device Token
                HStack {
                    SettingIcon(icon: "key.fill", color: Theme.inkTertiary)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("APNS DEVICE TOKEN")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                        let token = notificationManager.deviceToken
                            ?? UserDefaults.standard.string(forKey: "apns_device_token")
                            ?? "Not registered"
                        Text(token.count > 16 ? String(token.prefix(16)) + "..." : token)
                            .font(Theme.serialNumberFont(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                }
                .padding(.vertical, Theme.Spacing.standard)
                .contentShape(Rectangle())
                .onTapGesture {
                    let token = notificationManager.deviceToken
                        ?? UserDefaults.standard.string(forKey: "apns_device_token")
                    if let token = token {
                        UIPasteboard.general.string = token
                        notifToastMessage = "Token copied"
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
                    }
                }

                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                // Row 5b — Notification Registration Error
                if let error = notificationManager.registrationError {
                    ErrorDiagnoserView(
                        error: error,
                        context: ErrorDiagnostic(
                            endpoint: "/api/v1/notifications/register",
                            classification: "INFRASTRUCTURE_EXCEPTION"
                        )
                    )
                    .padding(.vertical, Theme.Spacing.medium)

                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                }

                // Row 6 — Reset Tutorial
                HStack {
                    SettingIcon(icon: "book.fill", color: Theme.securityGold)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("REPLAY APP TUTORIAL")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("See the guided tour again")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(Theme.securityGold)
                }
                .padding(.vertical, Theme.Spacing.standard)
                .contentShape(Rectangle())
                .onTapGesture {
                    UserDefaults.standard.removeObject(forKey: "nivesh_tutorial_completed_v1")
                    // The tutorialManager is injected via EnvironmentObject in the parent
                    // Post a notification so stockmeApp can handle it
                    NotificationCenter.default.post(name: Notification.Name("resetTutorial"), object: nil)
                }

                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                // Row 7 — Reset Onboarding
                HStack {
                    SettingIcon(icon: "trash.fill", color: Theme.bearRed)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("CLEAR ALL USERDEFAULTS")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.bearRed)
                        Text("Simulates fresh install")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                }
                .padding(.vertical, Theme.Spacing.standard)
                .contentShape(Rectangle())
                .onTapGesture {
                    let domain = Bundle.main.bundleIdentifier!
                    UserDefaults.standard.removePersistentDomain(forName: domain)
                    authManager.logout()
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .banknoteCard()
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.bearRed.opacity(0.3), lineWidth: 0.5)
            )

            if let toast = notifToastMessage {
                Text(toast)
                    .font(Theme.serialNumberFont(size: 11))
                    .foregroundStyle(.white)
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.vertical, Theme.Spacing.medium)
                    .background(Color.black.opacity(0.8))
                    .cornerRadius(Theme.CornerRadius.medium)
                    .transition(.opacity)
            }
        }
        .onAppear {
            UNUserNotificationCenter.current().getNotificationSettings { settings in
                DispatchQueue.main.async {
                    switch settings.authorizationStatus {
                    case .authorized: notifPermissionStatus = "Granted ✓"
                    case .denied: notifPermissionStatus = "Denied ✗"
                    default: notifPermissionStatus = "Not Asked"
                    }
                }
            }
        }
        .sheet(isPresented: $showTestNotifSheet) {
            testNotifSheet
        }
    }

    private var testNotifSheet: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                VStack(spacing: Theme.Spacing.screen) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("TICKER SYMBOL")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkSecondary)
                        TextField("e.g. RELIANCE", text: $testNotifTicker)
                            .autocapitalization(.allCharacters)
                            .disableAutocorrection(true)
                            .font(Theme.serialNumberFont(size: 15))
                            .foregroundStyle(Theme.inkPrimary)
                            .padding(Theme.Spacing.standard)
                            .banknoteCard()
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("EXCHANGE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkSecondary)
                        Picker("Exchange", selection: $testNotifExchange) {
                            Text("NSE").tag("NSE")
                            Text("BSE").tag("BSE")
                        }
                        .pickerStyle(.segmented)
                    }
                    Button {
                        Task {
                            do {
                                let payload = try await NetworkManager.shared.sendTestNotification(ticker: testNotifTicker.uppercased(), exchange: testNotifExchange)
                                NetworkManager.shared.scheduleLocalNotification(title: payload.title, body: payload.body, userInfo: payload.data.map { Dictionary(uniqueKeysWithValues: $0.map { ($0.key, $0.value as Any) }) } ?? [:])
                                notifToastMessage = "Notification sent — check your lock screen"
                                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
                                showTestNotifSheet = false
                            } catch {
                                notifToastMessage = "Failed: check server connection"
                                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
                            }
                        }
                    } label: {
                        Text("SEND TEST NOTIFICATION")
                            .font(Theme.officialStampFont(size: 10))
                            .foregroundStyle(Theme.canvasDeep)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.standard)
                            .background(testNotifTicker.isEmpty ? Theme.inkTertiary : Theme.securityGold)
                            .cornerRadius(Theme.CornerRadius.medium)
                    }
                    .disabled(testNotifTicker.isEmpty)
                    Spacer()
                }
                .padding(Theme.Spacing.screen)
            }
            .navigationTitle("Test Notification")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

private struct SettingIcon: View {
    let icon: String
    let color: Color

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(color.opacity(0.05))
                .frame(width: 32, height: 32)
            Image(systemName: icon)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(color.opacity(0.6))
        }
        .padding(.trailing, Theme.Spacing.standard)
    }
}

private struct ToggleNoteRow: View {
    let icon: String
    let color: Color
    let title: String
    @Binding var isOn: Bool

    var body: some View {
        HStack {
            SettingIcon(icon: icon, color: color)
            Toggle(isOn: $isOn) {
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkPrimary)
            }
            .tint(Theme.securityGold)
        }
        .padding(.vertical, Theme.Spacing.standard)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

private struct PickerNoteRow: View {
    let icon: String
    let color: Color
    let title: String
    @Binding var selection: String
    let options: [String]

    var body: some View {
        HStack {
            SettingIcon(icon: icon, color: color)
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            Picker("", selection: $selection) {
                ForEach(options, id: \.self) { option in
                    Text(option).tag(option)
                }
            }
            .tint(Theme.inkSecondary)
        }
        .padding(.vertical, Theme.Spacing.standard)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

private struct DatePickerNoteRow: View {
    let icon: String
    let color: Color
    let title: String
    @Binding var selection: Date

    var body: some View {
        HStack {
            SettingIcon(icon: icon, color: color)
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            DatePicker("", selection: $selection, displayedComponents: .hourAndMinute)
                .labelsHidden()
                .tint(Theme.securityGold)
        }
        .padding(.vertical, Theme.Spacing.standard)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

private struct ServerURLSheet: View {
    @Binding var draft: String
    @Binding var testResult: String?
    @Binding var testLoading: Bool
    let onSave: (String) -> Void
    @Environment(\.dismiss) var dismiss

    var isValidURL: Bool {
        draft.lowercased().hasPrefix("http://") || draft.lowercased().hasPrefix("https://")
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                VStack(spacing: Theme.Spacing.large) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("SERVER URL")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkSecondary)
                        TextField("http://127.0.0.1:8000", text: $draft)
                            .font(Theme.serialNumberFont(size: 15))
                            .foregroundStyle(Theme.inkPrimary)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                        Text("Must start with http:// or https://")
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundStyle(Theme.inkTertiary)
                    }

                    // Test connection
                    Button {
                        testLoading = true
                        testResult = nil
                        Task {
                            NetworkManager.shared.updateBaseURL(draft)
                            let ok = (try? await NetworkManager.shared.checkHealth()) ?? false
                            testResult = ok ? "✓ Connected successfully" : "✗ Cannot reach server"
                            testLoading = false
                        }
                    } label: {
                        HStack {
                            if testLoading { ProgressView().tint(Theme.inkPrimary) }
                            else { Text("TEST CONNECTION").font(Theme.officialStampFont(size: 9)) }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(Theme.Spacing.standard)
                        .background(isValidURL ? Theme.inkSecondary.opacity(0.08) : Theme.inkSecondary.opacity(0.03))
                        .foregroundStyle(isValidURL ? Theme.inkPrimary : Theme.inkTertiary)
                        .banknoteCard()
                    }
                    .disabled(!isValidURL || testLoading)

                    if let result = testResult {
                        Text(result)
                            .font(Theme.serialNumberFont(size: 13))
                            .foregroundStyle(result.hasPrefix("✓") ? Theme.bullGreen : Theme.bearRed)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    Spacer()
                }
                .padding(Theme.Spacing.screen)
            }
            .navigationTitle("Server Connection")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(draft)
                        dismiss()
                    }
                    .disabled(!isValidURL)
                }
            }
        }
    }
}
