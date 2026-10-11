import SwiftUI

// MARK: - Banknote Back Button
//
// A fully app-owned back control that replaces the SwiftUI/UIKit native back
// button (which renders the previous screen's title, varies per device/locale,
// and scales with the system Dynamic Type setting). This chevron-in-a-coin
// looks identical on every device.
//
// Usage on any pushed screen:
//   @Environment(\.dismiss) private var dismiss
//   ...
//   .banknoteBackButton { HapticManager.selection();  dismiss() }
//
// Or, when navigating via a NavigationPath binding:
//   .banknoteBackButton { HapticManager.selection();  path.removeLast() }

struct BanknoteBackButton: View {
    let action: () -> Void

    var body: some View {
        Button { HapticManager.selection(); 
    HapticManager.selection()
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
    }
}
