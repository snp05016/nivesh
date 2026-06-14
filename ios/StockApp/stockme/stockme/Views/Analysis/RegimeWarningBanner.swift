import SwiftUI

struct RegimeWarningBanner: View {
    let regime: String

    var isHighRisk: Bool {
        regime.contains("Crisis") || regime.contains("High Volatility")
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: isHighRisk ? "exclamationmark.triangle.fill" : "info.circle.fill")
                .foregroundStyle(isHighRisk ? Theme.holdAmber : Theme.inkTertiary)
                .font(.system(size: 20))

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("MARKET REGIME")
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkSecondary)

                Text(regime)
                    .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .caption))
                    .foregroundStyle(Theme.inkPrimary)

                if isHighRisk {
                    Text("Fundamental indicators and historical valuations are currently less reliable in this regime.")
                        .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer()
        }
        .padding(Theme.Spacing.card)
        .background(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .fill(isHighRisk ? Theme.holdAmber.opacity(0.12) : Theme.borderSage.opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(isHighRisk ? Theme.holdAmber.opacity(0.3) : Theme.borderFine, lineWidth: 1)
        )
    }
}
