import SwiftUI
import UserNotifications
import OSLog
import Combine
@MainActor
final class NotificationManager: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationManager()

    /// Fix 3.22: APNs failure state — disable Send Test Alert when registration fails
    @Published var isAuthorized = false
    @Published var deviceToken: String? = nil
    @Published var registrationError: String? = nil
    @Published var isTokenRegistrationFailed = false

    private override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }

    /// Request notification permissions
    func requestAuthorization() async {
        do {
            let granted = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .badge, .sound])
            self.isAuthorized = granted
            if granted {
                await MainActor.run {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
            os_log(.info, "[Nivesh/Notifications] Authorization: %{public}@", granted ? "granted" : "denied")
        } catch {
            self.registrationError = error.localizedDescription
            GlobalErrorDiagnoser.shared.track(
                "Notification authorization failed: \(error.localizedDescription)",
                diagnostic: ErrorDiagnostic(classification: "INFRASTRUCTURE_EXCEPTION")
            )
        }
        // Runs at launch and sign-in (the only callers), so the device mute matches the
        // server before the user ever opens Settings > Notifications.
        await syncPushMaster()
    }

    // MARK: - Push master switch (nivesh_pushMasterEnabled <-> server alerts_enabled)

    private static let pushMasterKey = "nivesh_pushMasterEnabled"
    private static let pushMasterSyncedKey = "nivesh_pushMasterSynced"
    /// alerts_enabled as last known on the server; a local change equal to it is not re-sent.
    private var serverPushMaster: Bool?

    var pushMasterEnabled: Bool {
        UserDefaults.standard.object(forKey: Self.pushMasterKey) as? Bool ?? true
    }

    /// Reconciles the local switch with the server. Network failures keep the local value;
    /// the next call retries.
    func syncPushMaster() async {
        let defaults = UserDefaults.standard
        do {
            if !defaults.bool(forKey: Self.pushMasterSyncedKey),
               defaults.object(forKey: Self.pushMasterKey) as? Bool == false {
                // One-time migration: older builds kept this switch on-device only, so the
                // server never learned an explicit OFF. Send it rather than adopt the server default.
                try await NetworkManager.shared.updateAlertsEnabled(false)
                serverPushMaster = false
            } else {
                let enabled = try await NetworkManager.shared.fetchPreferences().alertsEnabled ?? true
                serverPushMaster = enabled
                defaults.set(enabled, forKey: Self.pushMasterKey)
            }
            defaults.set(true, forKey: Self.pushMasterSyncedKey)
        } catch {
            os_log(.info, "[Nivesh/Notifications] Push switch sync deferred: %{public}@", error.localizedDescription)
        }
        scheduleMorningBrief()
    }

    /// Persists a change of the local switch (already written to UserDefaults).
    /// Returns nil when there was nothing to send, true when saved, false when the save
    /// failed and the switch was reverted.
    func pushMasterChanged(to enabled: Bool) async -> Bool? {
        scheduleMorningBrief()
        guard enabled != serverPushMaster else { return nil }
        do {
            try await NetworkManager.shared.updateAlertsEnabled(enabled)
            serverPushMaster = enabled
            UserDefaults.standard.set(true, forKey: Self.pushMasterSyncedKey)
            return true
        } catch {
            // Revert so the switch never claims a state the server does not have.
            serverPushMaster = !enabled
            UserDefaults.standard.set(!enabled, forKey: Self.pushMasterKey)
            scheduleMorningBrief()
            return false
        }
    }

    /// Called by AppDelegate when APNs token is received
    func handleDeviceToken(_ token: Data) {
        let tokenString = token.map { String(format: "%02x", $0) }.joined()
        self.deviceToken = tokenString
        os_log(.info, "[Nivesh/APNs] Token received")

        // Persist to UserDefaults for legacy access
        UserDefaults.standard.set(tokenString, forKey: "apns_device_token")

        // Send to backend
        Task {
            await syncTokenToBackend(tokenString)
        }
    }

    func handleRegistrationError(_ error: Error) {
        self.registrationError = error.localizedDescription
        print("[Nivesh/APNs] Registration failed: \(error.localizedDescription)")
    }

    private func syncTokenToBackend(_ token: String) async {
        do {
            try await NetworkManager.shared.registerDeviceToken(token: token)
            print("[Nivesh/APNs] Token synced to backend")
        } catch {
            self.registrationError = "Token sync failed: \(error.localizedDescription)"
            GlobalErrorDiagnoser.shared.trackNetworkError(error, endpoint: "/api/v1/notifications/register")
        }
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// Show notification when app is in foreground
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    /// Notification tap: open the stock's action hub when the payload carries a ticker
    /// (price-alert pushes send `"ticker"` alongside `aps`).
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        route(userInfo: response.notification.request.content.userInfo)
        completionHandler()
    }

    /// Hands a valid push `ticker` to DeepLinkRouter; ignores missing or unknown tickers.
    func route(userInfo: [AnyHashable: Any]) {
        if let raw = userInfo["ticker"] as? String, let ticker = DeepLink.validTicker(raw) {
            DeepLinkRouter.shared.pendingTicker = ticker
        }
    }

    /// Schedule a local notification immediately, honouring the Push Notifications
    /// master switch, quiet hours and the chosen sound. scheduleMorningBrief also
    /// honours the master switch. (NetworkManager.scheduleLocalNotification bypasses
    /// both but has no callers.)
    func scheduleLocal(title: String, body: String, subtitle: String = "",
                       identifier: String? = nil, userInfo: [AnyHashable: Any] = [:]) {
        guard pushMasterEnabled else { return }

        // Quiet hours check
        if isInQuietHours() { return }

        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        if !subtitle.isEmpty { content.subtitle = subtitle }
        content.userInfo = userInfo

        let customSound = UserDefaults.standard.string(forKey: "notificationSound") ?? "Default"
        if customSound == "Default" {
            content.sound = .default
        } else {
            content.sound = UNNotificationSound(named: UNNotificationSoundName(customSound))
        }

        let request = UNNotificationRequest(
            identifier: identifier ?? "nivesh_local_\(UUID().uuidString.prefix(8))",
            content: content,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("[Nivesh/Local] Failed: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Morning Brief Scheduling

    func scheduleMorningBrief() {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: ["nivesh_morning_brief"])
        // Master switch OFF cancels the repeating brief; ON (via syncPushMaster or
        // pushMasterChanged) re-adds it.
        guard pushMasterEnabled else { return }

        let totalSecs = UserDefaults.standard.double(forKey: "morningBriefTime")
        guard totalSecs > 0 else { return }

        let hour = Int(totalSecs) / 3600
        let minute = (Int(totalSecs) % 3600) / 60

        let content = UNMutableNotificationContent()
        content.title = "Morning Brief"
        content.body = "Your daily market overview is ready."
        content.sound = .default

        var dateComponents = DateComponents()
        dateComponents.hour = hour
        dateComponents.minute = minute

        let trigger = UNCalendarNotificationTrigger(dateMatching: dateComponents, repeats: true)
        let request = UNNotificationRequest(identifier: "nivesh_morning_brief", content: content, trigger: trigger)
        center.add(request, withCompletionHandler: nil)
    }

    // MARK: - Quiet Hours

    private func isInQuietHours() -> Bool {
        // Same defaults as QuietHoursView's @AppStorage (22:00-07:00), so the window shown is the window enforced.
        let startSecs = UserDefaults.standard.object(forKey: "nivesh_quietHoursStart") as? Double ?? 79200
        let endSecs = UserDefaults.standard.object(forKey: "nivesh_quietHoursEnd") as? Double ?? 25200
        guard startSecs != endSecs else { return false }

        let daysData = UserDefaults.standard.data(forKey: "nivesh_quietHoursDays") ?? Data()
        let activeDays: Set<Int> = (try? JSONDecoder().decode(Set<Int>.self, from: daysData)) ?? Set(0...6)

        let cal = Calendar.current
        let now = Date()
        let weekday = cal.component(.weekday, from: now) - 1 // 0=Sun, matches QuietHoursView.dayNames
        guard activeDays.contains(weekday) else { return false }

        let midnight = cal.startOfDay(for: now)
        let currentSecs = now.timeIntervalSince(midnight)

        if startSecs < endSecs {
            return currentSecs >= startSecs && currentSecs < endSecs
        } else {
            return currentSecs >= startSecs || currentSecs < endSecs
        }
    }
}
