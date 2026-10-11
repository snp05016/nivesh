import UIKit

// Notification presentation and taps are handled by NotificationManager,
// which is the UNUserNotificationCenter delegate.
class AppDelegate: NSObject, UIApplicationDelegate {

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        CrashInterceptor.register()
        // Install the notification delegate before launch finishes so a tap that
        // cold-launches the app is still delivered to didReceive.
        _ = NotificationManager.shared
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        NotificationManager.shared.handleDeviceToken(deviceToken)
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        NotificationManager.shared.handleRegistrationError(error)
    }
}

extension Notification.Name {
    static let watchlistUpdated = Notification.Name("watchlistUpdated")
}
