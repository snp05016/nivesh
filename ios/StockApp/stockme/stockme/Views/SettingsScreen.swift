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
    @AppStorage("currencyDisplay") private var currencyDisplay = "Lakhs/Crores"
    @AppStorage("ipoAlerts") private var ipoAlerts = false
    @AppStorage("dev_welcome_notification") private var devWelcomeNotification = false
    @AppStorage("notificationSound") private var notificationSound = "Default"

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

                ScrollView {
                    VStack(spacing: Theme.Spacing.xLarge) {
                        // User profile note
                        if let user = authManager.currentUser {
                            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                                Text("प्रमाणित उपयोगकर्ता / VERIFIED USER")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundStyle(Theme.inkSecondary)

                                HStack(spacing: Theme.Spacing.card) {
                                    ZStack {
                                        Rectangle()
                                            .fill(Theme.avatarBackground)
                                            .frame(width: UIScreen.main.bounds.width * 0.16, height: UIScreen.main.bounds.width * 0.20)
                                            .overlay(
                                            Text(String(user.displayName.prefix(1)))
                                                .font(.title.weight(.bold))
                                                .foregroundStyle(Theme.inkPrimary.opacity(0.2))
                                        )
                                    Color.orange.opacity(0.04)
                                    }
                                    .overlay(Rectangle().stroke(Theme.borderFine, lineWidth: 0.5))

                                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                        Text(user.displayName.uppercased())
                                            .font(Theme.engravedSerif(size: 20, weight: .bold))
                                            .foregroundStyle(Theme.inkPrimary)
                                        Text("REGISTRY ID: 00\(user.userId)7249")
                                            .font(Theme.serialNumberFont(size: 11))
                                            .foregroundStyle(Theme.inkSecondary)
                                    }
                                    Spacer()

                                    BanknoteSignalBadge(text: "AUTH", color: Theme.securityGold, rotation: -4)
                                }
                            }
                            .padding(Theme.Spacing.large)
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, Theme.Spacing.standard)
                        }

                        VStack(spacing: Theme.Spacing.large) {
                            SettingsNoteGroup(title: "App Preferences", hindi: "ऐप प्राथमिकताएं") {
                                ToggleNoteRow(icon: "moon.fill", color: .indigo, title: "Dark Inks", isOn: $darkMode)
                                PickerNoteRow(icon: "faceid", color: Theme.bullGreen, title: "Security Threads (Face ID)", selection: $biometricTimeoutRaw, options: ["immediately", "1min", "5min", "15min", "never"])
                                ToggleNoteRow(icon: "waveform.badge.magnifyingglass", color: Theme.securityGold, title: "Deep Scan by Default", isOn: $defaultDeepScan)
                                DatePickerNoteRow(icon: "clock.fill", color: Theme.securityGold, title: "Morning Brief Time", selection: morningBriefDate)
                                PickerNoteRow(icon: "bell.fill", color: Theme.bearRed, title: "Notification Sound", selection: $notificationSound, options: ["Default", "rupee_rustle.mp3"])
                            }

                            SettingsNoteGroup(title: "Denomination Theme", hindi: "मुद्रा थीम") {
                                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                                    Text("DENOMINATION THEME")
                                        .font(Theme.officialStampFont(size: 9)).tracking(1.5)
                                        .foregroundStyle(Theme.inkTertiary)

                                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())],
                                              spacing: Theme.Spacing.standard) {
                                        ForEach(AppTheme.allCases, id: \.self) { theme in
                                            Button(action: {
                                                HapticManager.selection()
                                                ThemeManager.shared.current = theme
                                            }) {
                                                HStack(spacing: Theme.Spacing.medium) {
                                                    Circle()
                                                        .fill(theme.swatchColor)
                                                        .frame(width: 20, height: 20)
                                                        .overlay(Circle().stroke(Color.white.opacity(0.3), lineWidth: 0.5))
                                                    Text(theme.displayName)
                                                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                                                        .foregroundStyle(Theme.inkPrimary)
                                                        .lineLimit(1)
                                                    Spacer()
                                                    if ThemeManager.shared.current == theme {
                                                        Image(systemName: "checkmark")
                                                            .font(.caption.weight(.bold))
                                                            .foregroundStyle(Theme.securityGold)
                                                    }
                                                }
                                                .padding(Theme.Spacing.standard)
                                                .background(ThemeManager.shared.current == theme
                                                            ? Theme.securityGold.opacity(0.08) : Theme.canvasDeep)
                                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                                                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                                    .stroke(ThemeManager.shared.current == theme
                                                            ? Theme.securityGold.opacity(0.4) : Theme.borderFine, lineWidth: 0.5))
                                            }
                                            .buttonStyle(EKPressStyle())
                                        }
                                    }
                                }
                                .padding(.vertical, Theme.Spacing.standard)
                            }

                            SettingsNoteGroup(title: "Data Registry", hindi: "डेटा रजिस्ट्री") {
                                PickerNoteRow(icon: "indianrupeesign", color: Theme.bullGreen, title: "Currency Format", selection: $currencyDisplay, options: ["Lakhs/Crores", "Absolute"])
                            }

                            SettingsNoteGroup(title: "Archives", hindi: "अभिलेखागार") {
                                HStack {
                                    SettingIcon(icon: "trash.fill", color: Theme.bearRed)
                                    Text("VOID ALL RECORDS")
                                        .font(Theme.officialStampFont(size: 9))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Spacer()
                                    Text("\(reportManager.savedReports.count)")
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                                .padding(.vertical, Theme.Spacing.standard)
                                .contentShape(Rectangle())
                                .onTapGesture { showClearHistoryAlert = true }
                            }

                            SettingsNoteGroup(title: "Server Connection", hindi: "सर्वर कनेक्शन") {
                                HStack {
                                    SettingIcon(icon: "network", color: Theme.securityGold)
                                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                        Text("SERVER URL")
                                            .font(Theme.officialStampFont(size: 9))
                                            .foregroundStyle(Theme.inkPrimary)
                                        Text(NetworkManager.shared.baseURL)
                                            .font(Theme.serialNumberFont(size: 10))
                                            .foregroundStyle(Theme.inkTertiary)
                                            .lineLimit(1)
                                    }
                                    Spacer()
                                    Button("Change") {
                                        serverURLDraft = NetworkManager.shared.baseURL
                                        serverTestResult = nil
                                        showServerURLSheet = true
                                    }
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.securityGold)
                                }
                                .padding(.vertical, Theme.Spacing.standard)
                                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                                ToggleNoteRow(icon: "bell.badge", color: Theme.securityGold, title: "IPO Alerts", isOn: $ipoAlerts)
                            }

                            // Logout stamp
                            Button(action: { authManager.logout() }) {
                                HStack {
                                    Spacer()
                                    Text("VOID SESSION / SIGN OUT")
                                        .font(Theme.officialStampFont(size: 9))
                                        .foregroundStyle(Theme.bearRed)
                                    Spacer()
                                }
                                .padding(.vertical, Theme.Spacing.card)
                                .banknoteCard()
                            }

                            if showDevTools {
                                devToolsSection
                            }

                            // Official seal footer
                            VStack(spacing: Theme.Spacing.medium) {
                                Image(systemName: "laurel.leading")
                                    .font(.title)
                                    .foregroundStyle(Theme.inkSecondary.opacity(0.1))

                                Text("NIVESH OFFICIAL TENDER v1.0")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundStyle(Theme.inkTertiary)
                                    .onTapGesture(count: 3) {
                                        let gen = UIImpactFeedbackGenerator(style: .heavy)
                                        gen.impactOccurred()
                                        showDevTools.toggle()
                                    }
                            }
                            .padding(.top, Theme.Spacing.screen)
                        }
                        .padding(.horizontal, Theme.screenPadding)

                        Spacer(minLength: 40)
                    }
                }
            }
            .navigationTitle("Registry Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Theme.canvasDeep, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .alert("Void History", isPresented: $showClearHistoryAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Void All", role: .destructive) {
                    let reportsToDelete = reportManager.savedReports
                    for report in reportsToDelete {
                        reportManager.deleteReport(ticker: report.ticker)
                    }
                }
            } message: {
                Text("Are you sure you want to permanently void all locally saved AI analysis reports? This action cannot be reversed.")
            }
        }
        .sheet(isPresented: $showServerURLSheet) {
            ServerURLSheet(
                draft: $serverURLDraft,
                testResult: $serverTestResult,
                testLoading: $serverTestLoading
            ) { newURL in
                NetworkManager.shared.updateBaseURL(newURL)
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

private struct SettingsNoteGroup<Content: View>: View {
    let title: String
    let hindi: String
    let content: Content

    init(title: String, hindi: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.hindi = hindi
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
                Text(hindi)
                    .font(Theme.hindiFont(size: 9))
                    .foregroundStyle(Theme.inkSecondary)
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkPrimary)
            }
            .padding(.horizontal, Theme.Spacing.small)

            VStack(spacing: Theme.Spacing.none) { content }
                .padding(.horizontal, Theme.Spacing.card)
                .banknoteCard()
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
