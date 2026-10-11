import SwiftUI

/// Persistent "DEMO DATA" banner pinned to the top of a screen whose content is
/// simulated (UX-22). Debug-only hubs (ReleaseGate) wear it so the disclosure
/// travels with the destination, not just the Markets card caption.
struct DemoDataRibbon: ViewModifier {
    let isActive: Bool

    @ViewBuilder
    func body(content: Content) -> some View {
        if isActive {
            content.safeAreaInset(edge: .top, spacing: 0) {
                Text("DEMO DATA: not real prices, offers or accounts")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.0)
                    .foregroundStyle(Theme.inkPrimary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.medium)
                    .padding(.horizontal, Theme.screenPadding)
                    .background(Theme.holdAmber.opacity(0.15))
            }
        } else {
            content
        }
    }
}

extension View {
    func demoDataRibbon(_ isActive: Bool = true) -> some View { modifier(DemoDataRibbon(isActive: isActive)) }
}
