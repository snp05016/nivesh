import SwiftUI
import Combine
import UserNotifications

@main
struct stockmeApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    @StateObject private var authManager = AuthManager()
    @StateObject private var reportManager = LocalReportManager()
    @StateObject private var tutorialManager = TutorialManager()
    @StateObject private var notificationManager = NotificationManager.shared
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @AppStorage("hasAcceptedDisclaimer") private var hasAcceptedDisclaimer = false
    @AppStorage("darkMode") private var darkMode = false
    @AppStorage("dev_welcome_notification") private var devWelcomeNotification = false

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
                Task {
                    await notificationManager.requestAuthorization()
                }
                // Dev welcome notification (triggered by toggle in Settings dev tools)
                if devWelcomeNotification {
                    NotificationManager.shared.scheduleLocal(
                        title: "Welcome to Nivesh",
                        body: "Developer tools active — notification pipeline verified.",
                        subtitle: "Environment: DEBUG"
                    )
                }
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
