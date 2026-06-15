import SwiftUI

struct SPSkeletonBlock: View {
    let rows: Int
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            ForEach(0..<rows, id: \.self) { i in
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.08))
                    .frame(maxWidth: .infinity)
                    .frame(height: 20 + CGFloat(i % 2) * 8)
                    .shimmerPlaceholder(isLoading: true)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct SPEmptyStateView: View {
    let message: String
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "doc.questionmark")
                .font(.largeTitle)
                .foregroundStyle(Theme.inkTertiary)
            Text(message)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .body))
                .foregroundStyle(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.xLarge)
        .banknoteCard()
    }
}

struct SPLegendDot: View {
    let color: Color
    let label: String
    let value: Double
    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Circle().fill(color).frame(width: Theme.Spacing.medium, height: Theme.Spacing.medium)
            Text("\(label) \(String(format: "%.1f", value))%")
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(1)
                .minimumScaleFactor(0.82)
        }
    }
}

struct SPCompactChartValue: View {
    let label: String
    let value: String
    let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .tracking(0.8)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, Theme.Spacing.tight)
        .padding(.horizontal, Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
    }
}
