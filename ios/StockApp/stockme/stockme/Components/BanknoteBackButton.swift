import SwiftUI

// MARK: - Banknote Back Button
//
// A fully app-owned back control that replaces the SwiftUI/UIKit native back
// button (which renders the previous screen's title and varies per
// device/locale). The chevron uses Theme.engravedSerif, so it scales with
// Dynamic Type (up to AX2) inside its fixed coin; VoiceOver reads it as "Back".
//
// Usage on any pushed screen:
//   @Environment(\.dismiss) private var dismiss
//   ...
//   .banknoteBackButton { dismiss() }   // the button already plays the haptic
//
// Or, when navigating via a NavigationPath binding:
//   .banknoteBackButton { path.removeLast() }

struct BanknoteBackButton: View {
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            Image(systemName: "chevron.left")
                .font(Theme.engravedSerif(size: 16, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)
                .frame(width: Theme.Spacing.large, height: Theme.Spacing.large)
                .padding(Theme.Spacing.medium)
                .background(Theme.canvasDeep)
                .clipShape(Circle())
                .overlay(
                    Circle().stroke(Theme.borderFine, lineWidth: 0.5)
                )
        }
        .buttonStyle(EKPressStyle())
        .accessibilityLabel("Back")
    }
}

extension View {
    /// Hides the native back button and installs the app-owned `BanknoteBackButton`
    /// in the navigation bar's leading slot, for device-consistent appearance.
    func banknoteBackButton(_ action: @escaping () -> Void) -> some View {
        self
            .navigationBarBackButtonHidden(true)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    BanknoteBackButton(action: action)
                }
            }
            // Hiding the native back button also disables the edge-swipe pop
            // gesture; re-enable it so one-handed users can still swipe back.
            .background { PopGestureEnabler().frame(width: 0, height: 0).accessibilityHidden(true) }
    }
}

/// Re-arms `interactivePopGestureRecognizer` for the enclosing navigation
/// controller. UIKit's default delegate refuses to begin once the back button
/// is hidden, so a shared delegate allows it whenever there is a screen to pop
/// and no transition is already running (the root-swipe freeze guard).
private struct PopGestureEnabler: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> Controller { Controller() }
    func updateUIViewController(_ controller: Controller, context: Context) {}

    final class Controller: UIViewController {
        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            navigationController?.interactivePopGestureRecognizer?.isEnabled = true
            navigationController?.interactivePopGestureRecognizer?.delegate = PopGestureDelegate.shared
        }
    }
}

private final class PopGestureDelegate: NSObject, UIGestureRecognizerDelegate {
    static let shared = PopGestureDelegate()

    func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        // The pop recognizer lives on the navigation controller's root view,
        // whose next responder is the navigation controller itself.
        guard let nav = gestureRecognizer.view?.next as? UINavigationController else { return false }
        return nav.viewControllers.count > 1 && nav.transitionCoordinator == nil
    }
}
