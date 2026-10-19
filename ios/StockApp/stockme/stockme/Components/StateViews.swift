import SwiftUI

// C9: one state system for loading, empty, failed and offline sections.

nonisolated enum LoadPhase: Equatable {
    case loading, loaded, empty, failed(String), offline

    /// - hasLoaded: a successful response has arrived at least once (not "has non-empty data").
    /// - isEmpty: the loaded content is empty.
    /// - error: the stored, already friendly message of the last failure, shown verbatim.
    /// Empty only after a successful response; a failure with nothing loaded is never empty.
    static func resolve(isLoading: Bool, hasLoaded: Bool, isEmpty: Bool, error: String?, isOnline: Bool) -> LoadPhase {
        if hasLoaded && isEmpty { return .empty }
        if hasLoaded { return .loaded }      // a later refresh failure keeps showing the data
        if isLoading { return .loading }     // first load, or a retry in progress
        if !isOnline { return .offline }
        if let error { return .failed(error) }
        return .loading                      // idle before the first load starts
    }
}

struct StateCard<Content: View>: View {
    let title: String
    let phase: LoadPhase
    var asOf: Date? = nil
    var emptyMessage: String = "Nothing to show yet."
    var emptyActionTitle: String? = nil
    var emptyAction: (() -> Void)? = nil
    var onRetry: (() -> Void)? = nil
    @ViewBuilder var content: () -> Content

    var body: some View {
        switch phase {
        case .loading:
            StateSkeleton(lines: 3)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Loading \(title)")
        case .empty:
            StateMessage(icon: "tray", message: emptyMessage,
                         actionTitle: emptyActionTitle, action: emptyAction)
        case .failed(let message):
            StateMessage(icon: "exclamationmark.triangle", message: message,
                         actionTitle: onRetry == nil ? nil : "Try again",
                         actionLabel: "Retry loading \(title)", action: retry)
        case .offline:
            StateMessage(icon: "wifi.slash",
                         message: "You're offline. Connect to the internet to load \(title).",
                         actionTitle: onRetry == nil ? nil : "Try again",
                         actionLabel: "Retry loading \(title)", action: retry)
        case .loaded:
            VStack(alignment: .leading, spacing: 6) {
                content()
                if let asOf { AsOfStamp(date: asOf) }
            }
        }
    }

    @MainActor private func retry() {
        HapticManager.selection()
        onRetry?()
    }
}

/// Icon plus text (never colour-only meaning), with an optional 44 pt action.
struct StateMessage: View {
    let icon: String
    let message: String
    var actionTitle: String? = nil
    var actionLabel: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(Theme.inkSecondary)
                .accessibilityHidden(true)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            if let actionTitle, let action {
                Button(actionTitle, action: action)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.securityGold)
                    .frame(minWidth: 44, minHeight: 44)
                    .contentShape(Rectangle())
                    .accessibilityLabel(actionLabel ?? actionTitle)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
    }
}

struct StateSkeleton: View {
    var lines: Int = 3
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @State private var dimmed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(0..<lines, id: \.self) { i in
                RoundedRectangle(cornerRadius: 4)
                    .fill(Theme.inkTertiary.opacity(0.12))
                    .frame(height: 12)
                    // Shorter last row reads as a paragraph (fixed trailing inset).
                    .padding(.trailing, i == lines - 1 ? 60 : 0)
            }
        }
        .redacted(reason: .placeholder)
        .opacity(dimmed ? 0.5 : 1)
        .onAppear {
            guard !(systemReduceMotion || Theme.reduceAnimations) else { return }
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { dimmed = true }
        }
    }
}

struct AsOfStamp: View {
    let date: Date
    var prefix: String = "As of"

    private static let formatter: RelativeDateTimeFormatter = {
        let f = RelativeDateTimeFormatter()
        f.locale = Locale(identifier: "en_IN")
        f.unitsStyle = .full
        return f
    }()

    var body: some View {
        Text("\(prefix) \(Self.formatter.localizedString(for: date, relativeTo: Date()))")
            .font(.caption)
            .foregroundStyle(Theme.inkTertiary)
    }
}
