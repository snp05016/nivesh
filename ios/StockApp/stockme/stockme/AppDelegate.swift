import UIKit
import UserNotifications

class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        UserDefaults.standard.set(token, forKey: "apns_device_token")
        Task {
            try? await NetworkManager.shared.registerDeviceToken(token: token)
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        print("[APNs] Failed to register: \(error)")
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        if let ticker = userInfo["ticker"] as? String {
            NotificationCenter.default.post(
                name: .openStockAnalysis,
                object: nil,
                userInfo: ["ticker": ticker]
            )
        }
        completionHandler()
    }
}

extension Notification.Name {
    static let openStockAnalysis = Notification.Name("openStockAnalysis")
}
