import SwiftUI

// MARK: - Banknote Dialog
//
// App-owned replacement for the native `.confirmationDialog` / `.alert`.
// The native variants render translucent "oval" action buttons, draw system
// separators/borders around every button, and scale their text with the
// device's Dynamic Type setting — so they look different on every iPhone.
//
// This dialog is drawn entirely in-app with the Banknote aesthetic, fixed
// typography, no translucent ovals and no per-button system borders, so it is
// identical on every device.
//
// Usage:
//   .banknoteDialog("Remove TICKER?", isPresented: $show, message: "…", buttons: [
//       .init("Remove", role: .destructive) { remove() },
//       .cancel()
//   ])

struct BanknoteDialogButton: Identifiable {
    enum Role { case normal, destructive, cancel }

    let id = UUID()
    let title: String
    let role: Role
    let action: () -> Void

    init(_ title: String, role: Role = .normal, action: @escaping () -> Void = {}) {
        self.title = title
        self.role = role
        self.action = action
    }

    /// Convenience cancel button.
    static func cancel(_ title: String = "Cancel", action: @escaping () -> Void = {}) -> BanknoteDialogButton {
        BanknoteDialogButton(title, role: .cancel, action: action)
    }
}

private struct BanknoteDialogCard: View {
    let title: String
    let message: String?
    let accessory: AnyView?
    let buttons: [BanknoteDialogButton]
    let onClose: () -> Void

    var body: some View {
        ZStack {
            // Dimmed scrim — tapping it cancels, matching action-sheet behaviour.
            Theme.inkPrimary.opacity(0.5)
                .ignoresSafeArea()
                .onTapGesture { onClose() }

            VStack(spacing: Theme.Spacing.card) {
                VStack(spacing: Theme.Spacing.medium) {
                    Text(title.uppercased())
                        .font(Theme.officialStampFont(size: 13))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)

                    if let message, !message.isEmpty {
                        Text(message)
                            .font(Theme.engravedSerif(size: 14, weight: .regular))
                            .foregroundStyle(Theme.inkSecondary)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(.top, Theme.Spacing.tight)

                if let accessory {
                    accessory
                }

                GuillocheDivider()

                VStack(spacing: Theme.Spacing.medium) {
                    ForEach(buttons) { button in
                        dialogButton(button)
                    }
                }
            }
            .padding(Theme.Spacing.large)
            .banknoteCard()
            .frame(maxWidth: min(UIScreen.main.bounds.width * 0.86, 460))
            .padding(.horizontal, Theme.screenPadding)
        }
    }

    private func dialogButton(_ button: BanknoteDialogButton) -> some View {
        Button {
    HapticManager.selection()
            HapticManager.selection()
            onClose()
            button.action()
        } label: {
            Text(button.title)
                .font(Theme.engravedSerif(size: 15, weight: .bold))
                .foregroundStyle(foreground(for: button.role))
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.standard)
                .background(background(for: button.role))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
        .buttonStyle(EKPressStyle())
    }

    private func foreground(for role: BanknoteDialogButton.Role) -> Color {
        switch role {
        case .normal:      return Theme.canvas
        case .destructive: return Theme.bearRed
        case .cancel:      return Theme.inkSecondary
        }
    }

    private func background(for role: BanknoteDialogButton.Role) -> Color {
        switch role {
        case .normal:      return Theme.securityGold
        case .destructive: return Theme.bearRed.opacity(0.12)
        case .cancel:      return Theme.canvasDeep
        }
    }
}

private struct BanknoteDialogModifier: ViewModifier {
    @Binding var isPresented: Bool
    let title: String
    let message: String?
    let accessory: AnyView?
    let buttons: [BanknoteDialogButton]

    func body(content: Content) -> some View {
        content.overlay {
            if isPresented {
                BanknoteDialogCard(
                    title: title,
                    message: message,
                    accessory: accessory,
                    buttons: buttons,
                    onClose: { isPresented = false }
                )
                .transition(.opacity.combined(with: .scale(scale: 0.96, anchor: .center)))
                .animation(.spring(response: 0.28, dampingFraction: 0.86), value: isPresented)
                .zIndex(1000)
            }
        }
    }
}

extension View {
    /// In-app, device-consistent replacement for `.confirmationDialog` / `.alert`.
    func banknoteDialog(
        _ title: String,
        isPresented: Binding<Bool>,
        message: String? = nil,
        buttons: [BanknoteDialogButton]
    ) -> some View {
        modifier(BanknoteDialogModifier(
            isPresented: isPresented,
            title: title,
            message: message,
            accessory: nil,
            buttons: buttons
        ))
    }

    /// Variant that hosts a custom accessory control (e.g. a toggle) between the
    /// message and the action buttons.
    func banknoteDialog<Accessory: View>(
        _ title: String,
        isPresented: Binding<Bool>,
        message: String? = nil,
        buttons: [BanknoteDialogButton],
        @ViewBuilder accessory: () -> Accessory
    ) -> some View {
        modifier(BanknoteDialogModifier(
            isPresented: isPresented,
            title: title,
            message: message,
            accessory: AnyView(accessory()),
            buttons: buttons
        ))
    }
}
