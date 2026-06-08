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
    // Fix 3.23: Deep-link 404 routing — catch delisted ticker deep links
    @State private var deepLinkTicker: String? = nil
    @State private var deepLinkError: String? = nil

    // ── Launch state machine ─────────────────────────────────────────────
    private enum LaunchPhase { case loading, biometricGate, mainInterface }
    @State private var launchPhase: LaunchPhase = .loading

    // ── Boot sync gate ───────────────────────────────────────────────────
    private let minimumLaunchDuration: TimeInterval = 3.0
    @State private var bootTasksComplete = false

    var body: some Scene {
        WindowGroup {
            ZStack {
                // ── Main interface (hidden during launch, revealed with spring)
                Group {
                    if !hasCompletedOnboarding {
                        OnboardingScreen { hasCompletedOnboarding = true }
                    } else if !hasAcceptedDisclaimer {
                        DisclaimerScreen { hasAcceptedDisclaimer = true }
                    } else if useBiometrics && isBiometricLocked {
                        biometricLockScreen
                    } else {
                        ContentView(bypassLaunch: true)
                    }
                }
                .environmentObject(authManager)
                .environmentObject(reportManager)
                .environmentObject(tutorialManager)
                .preferredColorScheme(darkMode ? .dark : nil)
                .opacity(launchPhase == .mainInterface ? 1 : 0)
                .scaleEffect(launchPhase == .mainInterface ? 1 : 1.02)

                // ── Launch overlay ───────────────────────────────────────
                if launchPhase == .loading {
                    LaunchSequenceView {
                        withAnimation(.spring(response: 0.45, dampingFraction: 0.8, blendDuration: 0)) {
                            launchPhase = .mainInterface
                        }
                    }
                    .transition(.opacity)
                }
            }
            .animation(.spring(response: 0.45, dampingFraction: 0.8, blendDuration: 0), value: launchPhase)
            .task {
                await performAsyncBoot()
            }
            .onAppear {
                Task { await notificationManager.requestAuthorization() }
                if useBiometrics { authenticateWithBiometrics() }
                if devWelcomeNotification {
                    NotificationManager.shared.scheduleLocal(
                        title: "Welcome to Nivesh",
                        body: "Developer tools active — notification pipeline verified.",
                        subtitle: "Environment: DEBUG"
                    )
                }
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

    // MARK: - Async Boot Synchronization

    private func performAsyncBoot() async {
        async let stockDB: Void = loadStockDatabase()
        async let authCheck: Void = verifyAuthSession()
        async let cacheWarm: Void = preWarmCaches()

        _ = await (stockDB, authCheck, cacheWarm)
        await MainActor.run { bootTasksComplete = true }

        // Sync gate: ensure minimum video playback before allowing exit
        try? await Task.sleep(nanoseconds: UInt64(minimumLaunchDuration * 1_000_000_000))

        // Bay: boot done + minimum video elapsed → LaunchSequenceView exits
        // The LaunchSequenceView's internal animation (~3.1s) aligns with this gate
    }

    private func loadStockDatabase() async {
        await Task.detached(priority: .utility) {
            _ = StockDatabase.all
            print("[Boot] StockDatabase loaded: \(StockDatabase.all.count) entries")
        }.value
    }

    private func verifyAuthSession() async {
        // AuthManager restores session from keychain on init — token ready or guest
        let loggedIn = authManager.isLoggedIn
        print("[Boot] Auth session: \(loggedIn ? "token ready" : "guest mode")")
    }

    private func preWarmCaches() async {
        await Task.detached(priority: .background) {
            let resp = try? await NetworkManager.shared.getMarketIndices()
            if let r = resp {
                print("[Boot] Market indices cache warm: \(r.indices.count) indices")
            }
        }.value
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
