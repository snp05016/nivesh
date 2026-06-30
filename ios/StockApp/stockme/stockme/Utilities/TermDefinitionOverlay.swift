import SwiftUI

// MARK: - Haptic Helper (UIKit-safe for widget extension)

#if canImport(UIKit)
import UIKit
private func triggerImpactHaptic() {
    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
}
private func triggerSelectionHaptic() {
    UISelectionFeedbackGenerator().selectionChanged()
}
#else
private func triggerImpactHaptic() {}
private func triggerSelectionHaptic() {}
#endif

// MARK: - ViewModifier

/// Applies a long-press gesture to any Text view. When held for 0.5s,
/// displays a tooltip card with the financial term's definition and example.
struct TermTooltipModifier: ViewModifier {
    let term: String
    @State private var showTooltip = false

    func body(content: Content) -> some View {
        content
            .onLongPressGesture(minimumDuration: 0.5) {
                triggerImpactHaptic()
                showTooltip = true
            }
            .overlay {
                if showTooltip, let entry = FinanceTerms.shared.lookup(term) {
                    TermTooltipCard(entry: entry, onDismiss: { showTooltip = false })
                        .transition(.opacity.combined(with: .scale(scale: 0.95, anchor: .center)))
                        .animation(.spring(response: 0.25, dampingFraction: 0.8), value: showTooltip)
                        .zIndex(999)
                }
            }
            .buttonStyle(EKPressStyle())
    }
}

// MARK: - View Extension

extension View {
    /// Attach a long-press handler that shows the definition tooltip for `term`.
    /// Safe to call on any view — if the term is not in the dictionary, no overlay appears.
    func financeTerm(_ term: String) -> some View {
        modifier(TermTooltipModifier(term: term))
    }
}

// MARK: - Tooltip Card

struct TermTooltipCard: View {
    let entry: FinanceTerm
    let onDismiss: () -> Void

    var body: some View {
        ZStack(alignment: .topTrailing) {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text(entry.term.uppercased())
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.5)
                    .foregroundStyle(Theme.securityGold)

                Text(entry.definition)
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)

                GuillocheDivider()

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("EXAMPLE")
                        .font(Theme.officialStampFont(size: 8))
                        .tracking(1.2)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(entry.example)
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .buttonStyle(EKPressStyle())
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .frame(maxWidth: min(UIScreen.main.bounds.width * 0.85, 500))

            Button(action: { HapticManager.selection();  HapticManager.selection()
                triggerSelectionHaptic()
                onDismiss()
            }) {
                Image(systemName: "xmark.circle.fill")
                    .font(.title3)
                    .foregroundStyle(Theme.inkTertiary)
            }
            .buttonStyle(.plain)
            .padding(Theme.Spacing.medium)
        }
        .padding(Theme.screenPadding)
        .background(
            Theme.inkPrimary.opacity(0.4)
                .ignoresSafeArea()
                .onTapGesture { onDismiss() }
        )
    }
}
