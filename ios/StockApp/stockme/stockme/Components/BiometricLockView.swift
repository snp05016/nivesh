import SwiftUI
import UIKit

/// Full-screen app lock. Hosted by LockOverlayWindow above the live ContentView so
/// tabs, navigation, sheets and typed input survive a relock.
struct BiometricLockView: View {
    var message: String?
    let onUnlock: () -> Void
    let onSignOut: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.large) {
            Image(systemName: "lock.fill")
                .font(.largeTitle)
                .foregroundStyle(Theme.securityGold)
            Text("NIVESH")
                .font(Font.custom("Georgia-Bold", size: 28, relativeTo: .title))
                .foregroundStyle(Theme.inkPrimary)
            Text("Authenticate to continue")
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary)
            if let message {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(Theme.inkSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Spacing.xLarge)
            }
            Button {
                HapticManager.selection()
                onUnlock()
            } label: {
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "lock.fill")
                    Text("Unlock")
                }
                .font(.body.weight(.medium))
                .foregroundStyle(Theme.canvas)
                .padding(.horizontal, Theme.Spacing.xLarge).padding(.vertical, Theme.Spacing.standard)
                .background(Theme.securityGold)
                .cornerRadius(Theme.CornerRadius.large)
            }
            .buttonStyle(EKPressStyle())
            Button(action: onSignOut) {
                Text("Sign out")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.canvas.ignoresSafeArea())
    }
}

/// Covers the window while the app is inactive or backgrounded so the
/// app-switcher snapshot never shows portfolio values.
struct PrivacyCoverView: View {
    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()
            VStack(spacing: Theme.Spacing.medium) {
                Image(systemName: "lock.fill")
                    .font(.largeTitle)
                    .foregroundStyle(Theme.securityGold)
                Text("NIVESH")
                    .font(Font.custom("Georgia-Bold", size: 28, relativeTo: .title))
                    .foregroundStyle(Theme.inkPrimary)
            }
        }
        .accessibilityHidden(true)
    }
}

/// What the lock window shows; nil hides it.
enum LockOverlay: Equatable {
    case lock(message: String?)
    case privacy
}

/// Hosts the lock and privacy cover in a dedicated UIWindow at .alert + 1.
/// A SwiftUI .overlay on the root view sits beneath every .sheet/.fullScreenCover
/// (separate UIKit presentations), which would leave an open sheet usable above the
/// lock and visible in the app-switcher snapshot.
@MainActor
final class LockOverlayWindow {
    private var window: UIWindow?

    func show(_ overlay: LockOverlay?, style: UIUserInterfaceStyle,
              onUnlock: @escaping () -> Void, onSignOut: @escaping () -> Void) {
        guard let overlay else {
            let scene = window?.windowScene
            window?.isHidden = true
            window = nil
            // Hand key status back to the app's main window.
            scene?.windows.first { !$0.isHidden && $0.windowLevel == .normal }?.makeKey()
            return
        }
        let content: AnyView
        switch overlay {
        case .lock(let message):
            content = AnyView(BiometricLockView(message: message, onUnlock: onUnlock, onSignOut: onSignOut))
        case .privacy:
            content = AnyView(PrivacyCoverView())
        }
        if let host = window?.rootViewController as? UIHostingController<AnyView> {
            host.rootView = content
        } else {
            let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            guard let scene = scenes.first(where: { $0.activationState == .foregroundActive }) ?? scenes.first
            else { return }
            let host = UIHostingController(rootView: content)
            host.view.accessibilityViewIsModal = true
            let newWindow = UIWindow(windowScene: scene)
            newWindow.windowLevel = .alert + 1
            newWindow.rootViewController = host
            window = newWindow
        }
        window?.overrideUserInterfaceStyle = style
        if case .lock = overlay {
            // Drop the keyboard of a field focused beneath the lock (its text is kept).
            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
            window?.makeKeyAndVisible()
        } else {
            window?.isHidden = false
        }
    }
}
