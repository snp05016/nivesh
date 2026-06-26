import SwiftUI
import Combine
import UserNotifications
import LocalAuthentication

// MARK: - Biometric Timeout Options

enum BiometricTimeout: String, CaseIterable {
    case immediately = "immediately"
    case oneMin      = "1min"
    case fiveMin     = "5min"
    case fifteenMin  = "15min"
    case never       = "never"

    var label: String {
        switch self {
        case .immediately: return "Immediately"
        case .oneMin:      return "After 1 min"
        case .fiveMin:     return "After 5 min"
        case .fifteenMin:  return "After 15 min"
        case .never:       return "Never"
        }
    }

    /// Seconds before re-lock; nil means never re-lock
    var seconds: TimeInterval? {
        switch self {
        case .immediately: return 0
        case .oneMin:      return 60
        case .fiveMin:     return 300
        case .fifteenMin:  return 900
        case .never:       return nil
        }
    }
}

@main
struct stockmeApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    @StateObject private var authManager = AuthManager()
    @StateObject private var reportManager = LocalReportManager()
    @StateObject private var tutorialManager = TutorialManager()
    @StateObject private var notificationManager = NotificationManager.shared
    @StateObject private var engineManager = AnalysisEngineManager.shared
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @AppStorage("hasAcceptedDisclaimer") private var hasAcceptedDisclaimer = false
    @AppStorage("hasSeenTutorial") private var hasSeenTutorial = false
    @State private var enginePollingStarted = false
    @State private var launchAnimDone = false
    @AppStorage("nivesh_crashCountSeen") private var crashCountSeen: Int = 0
    @State private var newCrashesSinceLastBoot: Int = 0
    @AppStorage("darkMode") private var darkMode = false
    @AppStorage("nivesh_reduceAnimations") private var reduceAnimations = false
    @AppStorage("dev_welcome_notification") private var devWelcomeNotification = false

    // Item 5 + 28: Configurable biometric timeout
    // "immediately" | "1min" | "5min" | "15min" | "never"
    @AppStorage("biometricTimeout") private var biometricTimeoutRaw = BiometricTimeout.immediately.rawValue
    @AppStorage("lastActiveTimestamp") private var lastActiveTimestamp: Double = 0

    @State private var isBiometricLocked = false
    @State private var isAuthenticating = false
    @State private var wentToBackground = false
    @Environment(\.scenePhase) private var scenePhase

    // Fix 3.23: Deep-link 404 routing — catch delisted ticker deep links
    @State private var deepLinkTicker: String? = nil
    @State private var deepLinkError: String? = nil

    // ── Launch state machine ─────────────────────────────────────────────
    private enum LaunchPhase { case loading, biometricGate, mainInterface }
    @State private var launchPhase: LaunchPhase = .loading

    // ── Boot sync gate ───────────────────────────────────────────────────
    private let minimumLaunchDuration: TimeInterval = 3.0
    @State private var bootTasksComplete = false

    private var biometricTimeout: BiometricTimeout {
        BiometricTimeout(rawValue: biometricTimeoutRaw) ?? .immediately
    }

    /// True when biometrics are enabled (timeout != "never")
    private var biometricsEnabled: Bool {
        biometricTimeout != .never
    }

    /// True when the timeout has elapsed since last active timestamp
    private var timeoutHasElapsed: Bool {
        guard biometricsEnabled else { return false }
        guard let secs = biometricTimeout.seconds else { return false }
        if secs == 0 { return true }   // "immediately" → always re-lock on background
        let elapsed = Date().timeIntervalSince1970 - lastActiveTimestamp
        return elapsed >= secs
    }

    var body: some Scene {
        WindowGroup {
            ZStack {
                // ── Main interface (hidden during launch, revealed with spring)
                Group {
                    if !hasSeenTutorial {
                        InteractiveTutorialScreen { hasSeenTutorial = true }
                    } else if !hasCompletedOnboarding {
                        OnboardingScreen { hasCompletedOnboarding = true }
                    } else if !hasAcceptedDisclaimer {
                        DisclaimerScreen { hasAcceptedDisclaimer = true }
                    } else if biometricsEnabled && isBiometricLocked {
                        biometricLockScreen
                    } else {
                        ContentView(bypassLaunch: true)
                    }
                }
                .environmentObject(authManager)
                .environmentObject(reportManager)
                .environmentObject(tutorialManager)
                .environmentObject(engineManager)
                .preferredColorScheme(darkMode ? .dark : nil)
                .buttonStyle(PlainButtonStyle())
                .pickerStyle(.menu)
                .controlSize(.small)
                .opacity(launchPhase == .mainInterface ? 1 : 0)
                .scaleEffect(launchPhase == .mainInterface ? 1 : 1.02)

                // ── Launch overlay ───────────────────────────────────────
                if launchPhase == .loading {
                    LaunchSequenceView(isAnimationComplete: $launchAnimDone)
                        .transition(.opacity)
                }
            }
            // Pin the type size so the app renders identically on every device,
            // ignoring the user's system "Larger Text" / Dynamic Type setting.
            // All `relativeTo:` fonts now resolve against this fixed scale.
            .dynamicTypeSize(.large)
            .animation(reduceAnimations ? .none : .spring(response: 0.45, dampingFraction: 0.8, blendDuration: 0), value: launchPhase)
            .onChange(of: launchAnimDone) { done in
                if done {
                    // Restore window UITraitCollection based on user's dark-mode preference
                    // (launch sequence forced it to .dark; now hand back control).
                    let style: UIUserInterfaceStyle = darkMode ? .dark : .unspecified
                    UIApplication.shared.connectedScenes
                        .compactMap { $0 as? UIWindowScene }
                        .flatMap { $0.windows }
                        .forEach { $0.overrideUserInterfaceStyle = style }
                    withAnimation(.spring(response: 0.45, dampingFraction: 0.8, blendDuration: 0)) {
                        launchPhase = .mainInterface
                    }
                }
            }
            .onChange(of: darkMode) { _, newValue in
                // Keep UITraitCollection in sync so Theme.* colors resolve correctly
                // (they read UITraitCollection.current.userInterfaceStyle, not SwiftUI's scheme).
                let style: UIUserInterfaceStyle = newValue ? .dark : .unspecified
                UIApplication.shared.connectedScenes
                    .compactMap { $0 as? UIWindowScene }
                    .flatMap { $0.windows }
                    .forEach { $0.overrideUserInterfaceStyle = style }
            }
            .task {
                await performAsyncBoot()
            }
            .onAppear {
                Task { await notificationManager.requestAuthorization() }
                let currentCrashes = CrashLog.shared.count()
                if currentCrashes > crashCountSeen {
                    newCrashesSinceLastBoot = currentCrashes - crashCountSeen
                }
                // Initial lock on cold launch — only if biometrics enabled
                if biometricsEnabled && !isAuthenticating {
                    isBiometricLocked = true
                    authenticateWithBiometrics()
                }
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
            // Item 5 + 28: Scene phase tracking for timeout-based lock.
            // Only .background (not .inactive) counts as "left the app" —
            // .inactive fires during Face ID itself, which would cause an infinite re-auth loop.
            .onChange(of: scenePhase) { _, newPhase in
                switch newPhase {
                case .background:
                    if biometricsEnabled {
                        lastActiveTimestamp = Date().timeIntervalSince1970
                        wentToBackground = true
                    }
                case .inactive:
                    break  // Face ID causes .inactive — ignore to avoid loop
                case .active:
                    if biometricsEnabled && wentToBackground && timeoutHasElapsed && !isAuthenticating {
                        wentToBackground = false
                        isBiometricLocked = true
                        authenticateWithBiometrics()
                    } else if !biometricsEnabled {
                        isBiometricLocked = false
                        wentToBackground = false
                    } else {
                        wentToBackground = false
                    }
                @unknown default:
                    break
                }
            }
            .onOpenURL { url in
                handleDeepLink(url)
            }
        }
    }

    private func handleDeepLink(_ url: URL) {
        guard url.scheme == "nivesh" else { return }
        
        let path = url.path
        let components = path.split(separator: "/").map(String.init)
        
        if url.host == "analyze", let ticker = components.first {
            NotificationCenter.default.post(name: Notification.Name("DeepLinkAnalyze"), object: ticker.uppercased())
        } else if url.host == "watchlist", components.first == "add", components.count > 1 {
            let ticker = components[1]
            NotificationCenter.default.post(name: Notification.Name("DeepLinkWatchlistAdd"), object: ticker.uppercased())
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
    HapticManager.selection()
                HapticManager.selection()
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
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.canvas)
    }

    private func authenticateWithBiometrics() {
        guard !isAuthenticating else { return }
        isAuthenticating = true

        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            print("[Nivesh/Biometrics] Not available: \(error?.localizedDescription ?? "unknown")")
            isAuthenticating = false
            isBiometricLocked = false  // fallback — skip biometrics if not available
            return
        }
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                               localizedReason: "Unlock Nivesh to access your portfolio") { success, authError in
            DispatchQueue.main.async {
                self.isAuthenticating = false
                if success {
                    self.isBiometricLocked = false
                    self.lastActiveTimestamp = Date().timeIntervalSince1970
                    print("[Nivesh/Biometrics] Authenticated successfully")
                } else {
                    print("[Nivesh/Biometrics] Failed: \(authError?.localizedDescription ?? "unknown")")
                    // Stay locked — user can tap the button to retry
                }
            }
        }
    }
}

// MARK: - Interactive Tutorial

struct InteractiveTutorialScreen: View {
    let onFinish: () -> Void
    @State private var currentPage = 0

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            TabView(selection: $currentPage) {
                TutorialPageView(
                    title: "Banknote Aesthetic",
                    subtitle: "Crafted for clarity. Every element feels like a secure, tactile piece of currency.",
                    iconName: "banknote"
                )
                .tag(0)

                TutorialPageView(
                    title: "AI Analysis",
                    subtitle: "Deep semantic understanding of market movements, news, and earnings.",
                    iconName: "brain.head.profile"
                )
                .tag(1)

                TutorialPageView(
                    title: "Portfolio Management",
                    subtitle: "Track your wealth with precision and actionable insights.",
                    iconName: "chart.pie.fill"
                )
                .tag(2)
            }
            .tabViewStyle(.page(indexDisplayMode: .always))

            VStack {
                Spacer()
                Button(action: { HapticManager.selection();  HapticManager.selection()
                    if currentPage < 2 {
                        withAnimation { currentPage += 1 }
                    } else {
                        onFinish()
                    }
                }) {
                    Text(currentPage < 2 ? "Next" : "Get Started")
                        .font(Theme.officialStampFont(size: 14))
                        .foregroundStyle(Theme.canvasDeep)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(Theme.securityGold)
                        .cornerRadius(Theme.CornerRadius.medium)
                }
                .buttonStyle(EKPressStyle())
                .padding(Theme.Spacing.screen)
            }
        }
    }
}

struct TutorialPageView: View {
    let title: String
    let subtitle: String
    let iconName: String

    var body: some View {
        VStack(spacing: Theme.Spacing.large) {
            Image(systemName: iconName)
                .resizable()
                .scaledToFit()
                .frame(width: 80, height: 80)
                .foregroundStyle(Theme.securityGold)
                .padding(.bottom, 20)

            Text(title.uppercased())
                .font(Theme.engravedSerif(size: 24, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)
                .multilineTextAlignment(.center)

            Text(subtitle)
                .font(.body)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
        }
    }
}
