import SwiftUI
import Combine
import UserNotifications

@main
struct stockmeApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    @StateObject private var authManager = AuthManager()
    @StateObject private var reportManager = LocalReportManager()
    @StateObject private var tutorialManager = TutorialManager()
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @AppStorage("hasAcceptedDisclaimer") private var hasAcceptedDisclaimer = false
    @AppStorage("darkMode") private var darkMode = false

    var body: some Scene {
        WindowGroup {
            Group {
                if !hasCompletedOnboarding {
                    OnboardingScreen {
                        hasCompletedOnboarding = true
                    }
                } else if !hasAcceptedDisclaimer {
                    DisclaimerScreen {
                        hasAcceptedDisclaimer = true
                    }
                } else {
                    ContentView()
                }
            }
            .environmentObject(authManager)
            .environmentObject(reportManager)
            .environmentObject(tutorialManager)
            .preferredColorScheme(darkMode ? .dark : nil)
            .onAppear {
                requestNotificationPermissions()
                // Listen for tutorial reset from Settings dev tools
                NotificationCenter.default.addObserver(
                    forName: Notification.Name("resetTutorial"),
                    object: nil, queue: .main
                ) { _ in
                    tutorialManager.resetForTesting()
                    tutorialManager.isShowingTutorial = true
                }
            }
        }
    }

    private func requestNotificationPermissions() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .badge, .sound]
        ) { granted, _ in
            UserDefaults.standard.set(granted, forKey: "notifications_granted")
            if granted {
                DispatchQueue.main.async {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
        }
    }
}
