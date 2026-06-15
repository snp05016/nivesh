import SwiftUI

struct QuantitativeDriversCard: View {
    let drivers: [String: Double]

    private var sortedDrivers: [(String, Double)] {
        drivers.sorted { abs($0.value) > abs($1.value) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            headerView

            if sortedDrivers.isEmpty {
                emptyStateView
            } else {
                driversListView
            }
        }
        .banknoteCard()
    }

    // Extracted to separate View to prevent chkstk_darwin
    private var headerView: some View {
        HStack {
            Text("STATISTICAL DRIVERS (SHAP)")
                .font(Theme.officialStampFont(size: 12))
                .foregroundStyle(Theme.inkTertiary)
                .tracking(1.5)
            Spacer()
            Text("Impact")
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
        }
    }

    private var emptyStateView: some View {
        Text("No statistically significant drivers detected.")
            .font(Theme.engravedSerif(size: 13, relativeTo: .caption))
            .foregroundStyle(Theme.inkSecondary)
    }

    private var driversListView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            ForEach(sortedDrivers, id: \.0) { name, value in
                DriverRow(name: name, value: value)
            }
        }
    }
}

// Extracted to separate View struct (AGENTS.md §6.6)
struct DriverRow: View {
    let name: String
    let value: Double

    private var isPositive: Bool { value > 0 }
    private var barFraction: CGFloat { min(CGFloat(abs(value)), 1.0) }

    // Proportional widths (AGENTS.md §2.2 — no hardcoded px)
    private var barTrackWidth: CGFloat { UIScreen.main.bounds.width * 0.14 }
    private var valueWidth: CGFloat    { UIScreen.main.bounds.width * 0.11 }

    var body: some View {
        HStack(spacing: Theme.Spacing.tight) {
            Text(name)
                .font(Theme.engravedSerif(size: 13, relativeTo: .caption))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Bar
            ZStack(alignment: isPositive ? .trailing : .leading) {
                Rectangle()
                    .fill(Theme.borderFine.opacity(0.3))
                    .frame(width: barTrackWidth, height: 6)
                    .cornerRadius(3)

                Rectangle()
                    .fill(isPositive ? Theme.bullGreen : Theme.bearRed)
                    .frame(width: barTrackWidth * barFraction, height: 6)
                    .cornerRadius(3)
            }
            .frame(width: barTrackWidth, height: 6)

            // Value
            Text(String(format: "%+.2f", value))
                .font(Theme.serialNumberFont(size: 12))
                .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
                .frame(width: valueWidth, alignment: .trailing)
        }
        .frame(maxWidth: .infinity)
    }
}
