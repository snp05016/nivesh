import SwiftUI

/// Fix 1.6: Unified signal grammar — cohesive color band + directional arrow.
/// Replaces the mix of text-only signals, standalone colors, and shapes.
struct SignalBadgeView: View {
    let signal: String
    let confidencePct: Int

    private var direction: (text: String, color: Color, arrow: String) {
        let upper = signal.uppercased()
        if upper.contains("BULLISH") || upper.contains("BUY") {
            return ("BULLISH", Theme.bullGreen, "▲")
        } else if upper.contains("BEARISH") || upper.contains("SELL") {
            return ("BEARISH", Theme.bearRed, "▼")
        } else {
            return ("NEUTRAL", Theme.holdAmber, "—")
        }
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.tight) {
            Text(direction.arrow)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.bold))
                .foregroundColor(direction.color)

            Text(direction.text)
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.2)
                .foregroundColor(direction.color)

            Text("\(confidencePct)%")
                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkSecondary)
        }
        .padding(.horizontal, Theme.Spacing.small)
        .padding(.vertical, Theme.Spacing.xSmall)
        .background(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(direction.color.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .stroke(direction.color.opacity(0.3), lineWidth: 1)
                )
        )
    }
}
