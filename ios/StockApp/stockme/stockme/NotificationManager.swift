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
    }

    /// Called by AppDelegate when APNs token is received
    func handleDeviceToken(_ token: Data) {
        let tokenString = token.map { String(format: "%02x", $0) }.joined()
        self.deviceToken = tokenString
        print("[Nivesh/APNs] Device token: \(tokenString)")
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

    /// Schedule a local notification immediately
    func scheduleLocal(title: String, body: String, subtitle: String = "") {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        if !subtitle.isEmpty { content.subtitle = subtitle }
        
        let customSound = UserDefaults.standard.string(forKey: "notificationSound") ?? "Default"
        if customSound == "Default" {
            content.sound = .default
        } else {
            content.sound = UNNotificationSound(named: UNNotificationSoundName(customSound))
        }

        let request = UNNotificationRequest(
            identifier: "nivesh_local_\(UUID().uuidString.prefix(8))",
            content: content,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("[Nivesh/Local] Failed: \(error.localizedDescription)")
            }
        }
    }
}
