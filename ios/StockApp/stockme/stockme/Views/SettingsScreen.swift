import SwiftUI
import UserNotifications

struct SettingsScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager

    @AppStorage("useBiometrics") private var useBiometrics = false
    @AppStorage("darkMode") private var darkMode = false
    @AppStorage("pushNotifications") private var pushNotifications = true
    @AppStorage("defaultDeepScan") private var defaultDeepScan = false
    @AppStorage("dataRefreshRate") private var dataRefreshRate = "Real-time"
    @AppStorage("currencyDisplay") private var currencyDisplay = "Lakhs/Crores"
    @AppStorage("ipoAlerts") private var ipoAlerts = false

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

    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .fifty)

                ScrollView {
                    VStack(spacing: 32) {
                        // User profile note
                        if let user = authManager.currentUser {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("प्रमाणित उपयोगकर्ता / VERIFIED USER")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundColor(Theme.inkSecondary)

                                HStack(spacing: 16) {
                                    ZStack {
                                        Rectangle()
                                            .fill(Color(hex: "E5E0D5"))
                                            .frame(width: 60, height: 75)
                                            .overlay(
                                                Text(String(user.displayName.prefix(1)))
                                                    .font(.system(size: 32, weight: .bold))
                                                    .foregroundColor(Theme.inkPrimary.opacity(0.2))
                                            )
                                        Color.orange.opacity(0.04)
                                    }
                                    .overlay(Rectangle().stroke(Theme.borderFine, lineWidth: 0.5))

                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(user.displayName.uppercased())
                                            .font(Theme.engravedSerif(size: 20, weight: .bold))
                                            .foregroundColor(Theme.inkPrimary)
                                        Text("REGISTRY ID: 00\(user.userId)7249")
                                            .font(Theme.serialNumberFont(size: 11))
                                            .foregroundColor(Theme.inkSecondary)
                                    }
                                    Spacer()

                                    BanknoteSignalBadge(text: "AUTH", color: Theme.securityGold, rotation: -4)
                                }
                            }
                            .padding(24)
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, 12)
                        }

                        VStack(spacing: 28) {
                            SettingsNoteGroup(title: "App Preferences", hindi: "ऐप प्राथमिकताएं") {
                                ToggleNoteRow(icon: "moon.fill", color: .indigo, title: "Dark Inks", isOn: $darkMode)
                                ToggleNoteRow(icon: "faceid", color: Theme.bullGreen, title: "Security Threads (Face ID)", isOn: $useBiometrics)
                                ToggleNoteRow(icon: "waveform.badge.magnifyingglass", color: Theme.securityGold, title: "Deep Scan by Default", isOn: $defaultDeepScan)
                            }

                            SettingsNoteGroup(title: "Data Registry", hindi: "डेटा रजिस्ट्री") {
                                PickerNoteRow(icon: "indianrupeesign", color: Theme.bullGreen, title: "Currency Format", selection: $currencyDisplay, options: ["Lakhs/Crores", "Absolute"])
                            }

                            SettingsNoteGroup(title: "Archives", hindi: "अभिलेखागार") {
                                HStack {
                                    SettingIcon(icon: "trash.fill", color: Theme.bearRed)
                                    Text("VOID ALL RECORDS")
                                        .font(Theme.officialStampFont(size: 9))
                                        .foregroundColor(Theme.inkPrimary)
                                    Spacer()
                                    Text("\(reportManager.savedReports.count)")
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundColor(Theme.inkSecondary)
                                }
                                .padding(.vertical, 14)
                                .contentShape(Rectangle())
                                .onTapGesture { showClearHistoryAlert = true }
                            }

                            SettingsNoteGroup(title: "Server Connection", hindi: "सर्वर कनेक्शन") {
                                HStack {
                                    SettingIcon(icon: "network", color: Theme.securityGold)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("SERVER URL")
                                            .font(Theme.officialStampFont(size: 9))
                                            .foregroundColor(Theme.inkPrimary)
                                        Text(NetworkManager.shared.baseURL)
                                            .font(Theme.serialNumberFont(size: 10))
                                            .foregroundColor(Theme.inkTertiary)
                                            .lineLimit(1)
                                    }
                                    Spacer()
                                    Button("Change") {
                                        serverURLDraft = NetworkManager.shared.baseURL
                                        serverTestResult = nil
                                        showServerURLSheet = true
                                    }
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.securityGold)
                                }
                                .padding(.vertical, 14)
                                Divider().background(Theme.inkSecondary.opacity(0.05))
                                ToggleNoteRow(icon: "bell.badge", color: Theme.securityGold, title: "IPO Alerts", isOn: $ipoAlerts)
                            }

                            // Logout stamp
                            Button(action: { authManager.logout() }) {
                                HStack {
                                    Spacer()
                                    Text("VOID SESSION / SIGN OUT")
                                        .font(Theme.officialStampFont(size: 9))
                                        .foregroundColor(Theme.bearRed)
                                    Spacer()
                                }
                                .padding(.vertical, 18)
                                .banknoteCard()
                            }

                            if showDevTools {
                                devToolsSection
                            }

                            // Official seal footer
                            VStack(spacing: 8) {
                                Image(systemName: "laurel.leading")
                                    .font(.system(size: 30))
                                    .foregroundColor(Theme.inkSecondary.opacity(0.1))

                                Text("NIVESH OFFICIAL TENDER v1.0")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundColor(Theme.inkTertiary)
                                    .onTapGesture(count: 3) {
                                        let gen = UIImpactFeedbackGenerator(style: .heavy)
                                        gen.impactOccurred()
                                        showDevTools.toggle()
                                    }
                            }
                            .padding(.top, 20)
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
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .bottom, spacing: 6) {
                Text("डेव टूल्स")
                    .font(Theme.hindiFont(size: 9))
                    .foregroundColor(Theme.inkSecondary)
                Text("DEVELOPER TOOLS")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundColor(Theme.bearRed)
                BanknoteSignalBadge(text: "DEV ONLY", color: Theme.bearRed, rotation: -2)
                    .scaleEffect(0.7)
            }
            .padding(.horizontal, 4)

            VStack(spacing: 0) {
                // Row 1 — Test Push Notification
                HStack {
                    SettingIcon(icon: "bell.badge.fill", color: Theme.holdAmber)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("TEST STOCK NOTIFICATION")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                        Text("Send a test push for any stock")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(Theme.securityGold)
                }
                .padding(.vertical, 14)
                .contentShape(Rectangle())
                .onTapGesture { showTestNotifSheet = true }

                Divider().background(Theme.inkSecondary.opacity(0.05))

                // Row 2 — Morning Summary Push
                HStack {
                    SettingIcon(icon: "sun.horizon.fill", color: Theme.securityGold)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("PUSH MORNING SUMMARY NOW")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                        Text("Send today's brief as a notification")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                }
                .padding(.vertical, 14)
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

                Divider().background(Theme.inkSecondary.opacity(0.05))

                // Row 3 — Harvest YouTube Now
                HStack {
                    SettingIcon(icon: "play.circle.fill", color: Theme.bullGreen)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("HARVEST YOUTUBE NOW")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                        Text("Run channel + portfolio harvest on demand")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                    if youtubeHarvestLoading {
                        ProgressView().tint(Theme.inkSecondary)
                    } else {
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundColor(Theme.securityGold)
                    }
                }
                .padding(.vertical, 14)
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

                Divider().background(Theme.inkSecondary.opacity(0.05))

                // Row 4 — Notification Permission Status
                HStack {
                    SettingIcon(icon: "bell.fill", color: Theme.inkSecondary)
                    Text("NOTIFICATION STATUS")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundColor(Theme.inkPrimary)
                    Spacer()
                    Text(notifPermissionStatus)
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundColor(notifPermissionStatus == "Granted ✓" ? Theme.bullGreen : notifPermissionStatus == "Denied ✗" ? Theme.bearRed : Theme.holdAmber)
                }
                .padding(.vertical, 14)
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

                Divider().background(Theme.inkSecondary.opacity(0.05))

                // Row 5 — APNs Device Token
                HStack {
                    SettingIcon(icon: "key.fill", color: Theme.inkTertiary)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("APNS DEVICE TOKEN")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                        let token = UserDefaults.standard.string(forKey: "apns_device_token") ?? "Not registered"
                        Text(token.count > 16 ? String(token.prefix(16)) + "..." : token)
                            .font(Theme.serialNumberFont(size: 9))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                }
                .padding(.vertical, 14)
                .contentShape(Rectangle())
                .onTapGesture {
                    if let token = UserDefaults.standard.string(forKey: "apns_device_token") {
                        UIPasteboard.general.string = token
                        notifToastMessage = "Token copied"
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { notifToastMessage = nil }
                    }
                }

                Divider().background(Theme.inkSecondary.opacity(0.05))

                // Row 6 — Reset Tutorial
                HStack {
                    SettingIcon(icon: "book.fill", color: Theme.securityGold)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("REPLAY APP TUTORIAL")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                        Text("See the guided tour again")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(Theme.securityGold)
                }
                .padding(.vertical, 14)
                .contentShape(Rectangle())
                .onTapGesture {
                    UserDefaults.standard.removeObject(forKey: "nivesh_tutorial_completed_v1")
                    // The tutorialManager is injected via EnvironmentObject in the parent
                    // Post a notification so stockmeApp can handle it
                    NotificationCenter.default.post(name: Notification.Name("resetTutorial"), object: nil)
                }

                Divider().background(Theme.inkSecondary.opacity(0.05))

                // Row 7 — Reset Onboarding
                HStack {
                    SettingIcon(icon: "trash.fill", color: Theme.bearRed)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("CLEAR ALL USERDEFAULTS")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.bearRed)
                        Text("Simulates fresh install")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    Spacer()
                }
                .padding(.vertical, 14)
                .contentShape(Rectangle())
                .onTapGesture {
                    let domain = Bundle.main.bundleIdentifier!
                    UserDefaults.standard.removePersistentDomain(forName: domain)
                    authManager.logout()
                }
            }
            .padding(.horizontal, 16)
            .banknoteCard()
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Theme.bearRed.opacity(0.3), lineWidth: 0.5)
            )

            if let toast = notifToastMessage {
                Text(toast)
                    .font(Theme.serialNumberFont(size: 11))
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Color.black.opacity(0.8))
                    .cornerRadius(8)
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
                VStack(spacing: 20) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("TICKER SYMBOL")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkSecondary)
                        TextField("e.g. RELIANCE", text: $testNotifTicker)
                            .autocapitalization(.allCharacters)
                            .disableAutocorrection(true)
                            .font(Theme.serialNumberFont(size: 15))
                            .foregroundColor(Theme.inkPrimary)
                            .padding(14)
                            .banknoteCard()
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Text("EXCHANGE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkSecondary)
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
                            .foregroundColor(Theme.canvasDeep)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(testNotifTicker.isEmpty ? Theme.inkTertiary : Theme.securityGold)
                            .cornerRadius(8)
                    }
                    .disabled(testNotifTicker.isEmpty)
                    Spacer()
                }
                .padding(20)
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
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .bottom, spacing: 6) {
                Text(hindi)
                    .font(Theme.hindiFont(size: 9))
                    .foregroundColor(Theme.inkSecondary)
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundColor(Theme.inkPrimary)
            }
            .padding(.horizontal, 4)

            VStack(spacing: 0) { content }
                .padding(.horizontal, 16)
                .banknoteCard()
        }
    }
}

private struct SettingIcon: View {
    let icon: String
    let color: Color

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 4)
                .fill(color.opacity(0.05))
                .frame(width: 32, height: 32)
            Image(systemName: icon)
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(color.opacity(0.6))
        }
        .padding(.trailing, 12)
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
                    .foregroundColor(Theme.inkPrimary)
            }
            .tint(Theme.securityGold)
        }
        .padding(.vertical, 12)
        Divider().background(Theme.inkSecondary.opacity(0.05))
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
                .foregroundColor(Theme.inkPrimary)
            Spacer()
            Picker("", selection: $selection) {
                ForEach(options, id: \.self) { option in
                    Text(option).tag(option)
                }
            }
            .tint(Theme.inkSecondary)
        }
        .padding(.vertical, 12)
        Divider().background(Theme.inkSecondary.opacity(0.05))
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
                VStack(spacing: 24) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("SERVER URL")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkSecondary)
                        TextField("http://127.0.0.1:8000", text: $draft)
                            .font(Theme.serialNumberFont(size: 15))
                            .foregroundColor(Theme.inkPrimary)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                            .padding(16)
                            .banknoteCard()
                        Text("Must start with http:// or https://")
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundColor(Theme.inkTertiary)
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
                        .padding(14)
                        .background(isValidURL ? Theme.inkSecondary.opacity(0.08) : Theme.inkSecondary.opacity(0.03))
                        .foregroundColor(isValidURL ? Theme.inkPrimary : Theme.inkTertiary)
                        .banknoteCard()
                    }
                    .disabled(!isValidURL || testLoading)

                    if let result = testResult {
                        Text(result)
                            .font(Theme.serialNumberFont(size: 13))
                            .foregroundColor(result.hasPrefix("✓") ? Theme.bullGreen : Theme.bearRed)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    Spacer()
                }
                .padding(20)
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
