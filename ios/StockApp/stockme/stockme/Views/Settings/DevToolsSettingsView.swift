import SwiftUI
import UserNotifications

struct DevToolsSettingsView: View {
    @EnvironmentObject var authManager: AuthManager

    @AppStorage("dev_welcome_notification") private var devWelcomeNotification = false

    @StateObject private var notificationManager = NotificationManager.shared

    @State private var showTestNotifSheet = false
    @State private var testNotifTicker = ""
    @State private var testNotifExchange = "NSE"
    @State private var notifToastMessage: String? = nil
    @State private var notifPermissionStatus: String = "Not Asked"
    @State private var youtubeHarvestLoading = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)

            ScrollView {
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
                            pushMorningSummary()
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
                }
                .padding(Theme.Spacing.screen)
            }

            if let toast = notifToastMessage {
                VStack {
                    Spacer()
                    Text(toast)
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundStyle(.white)
                        .padding(.horizontal, Theme.Spacing.card)
                        .padding(.vertical, Theme.Spacing.medium)
                        .background(Color.black.opacity(0.8))
                        .cornerRadius(Theme.CornerRadius.medium)
                        .transition(.opacity)
                        .padding(.bottom, Theme.Spacing.screen)
                }
                .zIndex(1)
            }
        }
        .navigationTitle("Dev Tools")
        .navigationBarTitleDisplayMode(.inline)
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
