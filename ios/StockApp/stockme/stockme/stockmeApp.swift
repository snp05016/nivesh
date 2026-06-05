import SwiftUI
import Combine
import UserNotifications
import LocalAuthentication

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
    @AppStorage("useBiometrics") private var useBiometrics = false
    @State private var isBiometricLocked = true

    var body: some Scene {
        WindowGroup {
            Group {
                if !hasCompletedOnboarding {
                    OnboardingScreen { hasCompletedOnboarding = true }
                } else if !hasAcceptedDisclaimer {
                    DisclaimerScreen { hasAcceptedDisclaimer = true }
                } else if useBiometrics && isBiometricLocked {
                    biometricLockScreen
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
                if useBiometrics {
                    authenticateWithBiometrics()
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

    // MARK: - Biometric Auth

    private var biometricLockScreen: some View {
        VStack(spacing: Theme.Spacing.large) {
            Image(systemName: "faceid")
                .font(.largeTitle)
                .foregroundStyle(Theme.securityGold)
            Text("NIVESH")
                .font(Font.custom("Georgia-Bold", size: 28, relativeTo: .title))
                .foregroundStyle(Theme.inkPrimary)
            Text("Authenticate to continue")
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary)
            Button {
                authenticateWithBiometrics()
            } label: {
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "faceid")
                    Text("Unlock with Face ID")
                }
                .font(.body.weight(.medium))
                .foregroundStyle(Theme.canvas)
                .padding(.horizontal, Theme.Spacing.xLarge).padding(.vertical, Theme.Spacing.standard)
                .background(Theme.securityGold)
                .cornerRadius(Theme.CornerRadius.large)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.canvas)
    }

    private func authenticateWithBiometrics() {
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            print("[Nivesh/Biometrics] Not available: \(error?.localizedDescription ?? "unknown")")
            isBiometricLocked = false  // fallback — skip biometrics if not available
            return
        }
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                               localizedReason: "Unlock Nivesh to access your portfolio") { success, authError in
            DispatchQueue.main.async {
                if success {
                    isBiometricLocked = false
                    print("[Nivesh/Biometrics] Authenticated successfully")
                } else {
                    print("[Nivesh/Biometrics] Failed: \(authError?.localizedDescription ?? "unknown")")
                    // Stay locked — user can tap button to retry
                }
            }
        }
    }
}
