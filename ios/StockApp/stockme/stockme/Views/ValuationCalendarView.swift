import SwiftUI
import Charts
import Combine

struct ValuationCalendarView: View {
    @StateObject private var vm = ValuationCalendarViewModel()
    let userId: Int

    @State private var selectedSnapshot: ValuationSnapshot? = nil
    @State private var selectedMonth: Date = Date()

    private let goldAccent = Theme.securityGold
    private let bullGreen  = Theme.bullGreen
    private let bearRed    = Theme.bearRed
    private let dimText    = Theme.inkSecondary

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .fill(.ultraThinMaterial)
                .overlay(PaperTexture().opacity(0.6))
                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderFine, lineWidth: 0.5))

            RBISealBackground().opacity(0.04)

            HStack(spacing: Theme.Spacing.none) {
                SecurityThread()

                VStack(alignment: .leading, spacing: Theme.Spacing.none) {

                    // Card Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("मूल्यांकन इतिहास")
                            .font(.caption)
                            .foregroundStyle(dimText)
                        HStack {
                            Text("PORTFOLIO CALENDAR")
                                .font(Theme.serialNumberFont(size: 11))
                                .tracking(2.0)
                                .foregroundStyle(Theme.inkSecondary)
                            Spacer()
                            // Period selector
                            HStack(spacing: Theme.Spacing.small) {
                                ForEach(["1M", "3M", "6M", "1Y"], id: \.self) { period in
                                    Button(action: { vm.fetchHistory(userId: userId, period: period) }) {
                                        Text(period)
                                            .font(Theme.serialNumberFont(size: 9))
                                            .foregroundStyle(vm.selectedPeriod == period ? goldAccent : dimText)
                                            .padding(.horizontal, Theme.Spacing.tight)
                                            .padding(.vertical, 3)
                                            .background(vm.selectedPeriod == period ? goldAccent.opacity(0.12) : Color.clear)
                                            .cornerRadius(Theme.CornerRadius.small)
                                    }
                                    .buttonStyle(EKPressStyle())
                                }
                            }
                        }
                    }
                    .padding(.bottom, Theme.Spacing.medium)

                    SectionDivider()
                        .padding(.bottom, Theme.Spacing.card)

                    // Summary Stats Row
                    if let summary = vm.summary {
                        HStack(spacing: Theme.Spacing.none) {
                            StatPill(
                                label: "PERIOD CHANGE",
                                value: formatCurrency(summary.periodChangeValue),
                                color: summary.periodChangeValue >= 0 ? bullGreen : bearRed
                            )
                            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 30)
                            StatPill(
                                label: "PEAK",
                                value: formatCurrency(summary.peakValue),
                                color: goldAccent
                            )
                            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 30)
                            StatPill(
                                label: "DATA POINTS",
                                value: "\(summary.dataPoints) days",
                                color: dimText
                            )
                        }
                        .padding(.bottom, Theme.Spacing.standard)
                    }

                    // Swift Charts: Value Over Time
                    if !vm.snapshots.isEmpty {
                        Chart {
                            ForEach(vm.snapshots) { snap in
                                LineMark(
                                    x: .value("Date", snap.parsedDate),
                                    y: .value("Value", snap.totalValue)
                                )
                                .foregroundStyle(goldAccent)
                                .lineStyle(StrokeStyle(lineWidth: 1.5))

                                AreaMark(
                                    x: .value("Date", snap.parsedDate),
                                    y: .value("Value", snap.totalValue)
                                )
                                .foregroundStyle(
                                    LinearGradient(
                                        colors: [goldAccent.opacity(0.25), goldAccent.opacity(0.0)],
                                        startPoint: .top,
                                        endPoint: .bottom
                                    )
                                )
                            }

                            // Highlight selected point
                            if let sel = selectedSnapshot {
                                PointMark(
                                    x: .value("Date", sel.parsedDate),
                                    y: .value("Value", sel.totalValue)
                                )
                                .foregroundStyle(goldAccent)
                                .symbolSize(60)
                            }
                        }
                        .chartXAxis {
                            AxisMarks(values: .stride(by: .month)) { _ in
                                AxisGridLine().foregroundStyle(Theme.borderFine)
                                AxisValueLabel(format: .dateTime.month(.abbreviated))
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(dimText)
                            }
                        }
                        .chartYAxis {
                            AxisMarks(position: .trailing) { value in
                                AxisGridLine().foregroundStyle(Theme.borderFine)
                                AxisValueLabel {
                                    if let v = value.as(Double.self) {
                                        Text(formatCompact(v))
                                            .font(Theme.serialNumberFont(size: 9))
                                            .foregroundStyle(dimText)
                                    }
                                }
                            }
                        }
                        .frame(height: UIScreen.main.bounds.width * 0.38)
                        .chartOverlay { proxy in
                            Rectangle().fill(.clear).contentShape(Rectangle())
                                .gesture(DragGesture(minimumDistance: 0)
                                    .onChanged { drag in
                                        let x = drag.location.x
                                        if let date: Date = proxy.value(atX: x) {
                                            selectedSnapshot = vm.snapshots.min(by: {
                                                abs($0.parsedDate.timeIntervalSince(date)) <
                                                abs($1.parsedDate.timeIntervalSince(date))
                                            })
                                        }
                                    }
                                )
                        }
                        .padding(.bottom, 12)

                        // Selected day tooltip
                        if let sel = selectedSnapshot {
                            HStack {
                                Text(sel.date)
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(dimText)
                                Spacer()
                                Text(formatCurrency(sel.totalValue))
                                    .font(Theme.serialNumberFont(size: 13))
                                    .foregroundStyle(.secondary)
                                Text(String(format: "%+.2f%%", sel.pnlPercent))
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundStyle(sel.pnlPercent >= 0 ? bullGreen : bearRed)
                            }
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.bottom, Theme.Spacing.medium)
                        }

                        // Calendar Heat Grid
                        CalendarHeatGrid(snapshots: vm.snapshots, selectedMonth: $selectedMonth)
                            .padding(.bottom, 4)
                    } else if vm.isLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity, minHeight: 200)
                    } else {
                        Text("No valuation history yet. First snapshot captured at market close.")
                            .font(Theme.officialStampFont(size: 12))
                            .foregroundStyle(dimText)
                            .frame(maxWidth: .infinity, minHeight: 80)
                            .multilineTextAlignment(.center)
                    }
                }
                .padding(Theme.Spacing.card)
            }
        }
        .onAppear { vm.fetchHistory(userId: userId, period: "3M") }
    }

    private func formatCurrency(_ value: Double) -> String {
        if abs(value) >= 1_00_00_000 {
            return String(format: "₹%.2fCr", value / 1_00_00_000)
        } else if abs(value) >= 1_00_000 {
            return String(format: "₹%.2fL", value / 1_00_000)
        }
        return String(format: "₹%.0f", value)
    }

    private func formatCompact(_ value: Double) -> String {
        if abs(value) >= 1_00_00_000 {
            return String(format: "%.1fCr", value / 1_00_00_000)
        } else if abs(value) >= 1_00_000 {
            return String(format: "%.1fL", value / 1_00_000)
        }
        return String(format: "%.0f", value)
    }
}

// MARK: - Calendar Heat Grid

struct CalendarHeatGrid: View {
    let snapshots: [ValuationSnapshot]
    @Binding var selectedMonth: Date

    private let columns = Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.small), count: 7)
    private let dayLabels = ["M", "T", "W", "T", "F", "S", "S"]
    private let goldAccent = Theme.securityGold
    private let bullGreen  = Theme.bullGreen
    private let bearRed    = Theme.bearRed

    // Build lookup dict from snapshot date string to pnl_percent
    var pnlByDate: [String: Double] {
        Dictionary(uniqueKeysWithValues: snapshots.map { ($0.date, $0.pnlPercent) })
    }

    var daysInSelectedMonth: [Date?] {
        let cal = Calendar.current
        let range = cal.range(of: .day, in: .month, for: selectedMonth)!
        let firstDay = cal.date(from: cal.dateComponents([.year, .month], from: selectedMonth))!
        let weekdayOffset = (cal.component(.weekday, from: firstDay) + 5) % 7 // Monday = 0
        var days: [Date?] = Array(repeating: nil, count: weekdayOffset)
        for day in 1...range.count {
            if let d = cal.date(byAdding: .day, value: day - 1, to: firstDay) {
                days.append(d)
            }
        }
        return days
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            // Month navigation
            HStack {
                Button(action: { changeMonth(-1) }) {
                    Image(systemName: "chevron.left")
                        .font(Theme.officialStampFont(size: 11))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .buttonStyle(EKPressStyle())
                Spacer()
                Text(selectedMonth, format: .dateTime.month(.wide).year())
                    .font(Theme.serialNumberFont(size: 11))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                Button(action: { changeMonth(1) }) {
                    Image(systemName: "chevron.right")
                        .font(Theme.officialStampFont(size: 11))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .buttonStyle(EKPressStyle())
                .accessibilityLabel("Next month")
            }
            .padding(.bottom, Theme.Spacing.small)

            // Day labels
            LazyVGrid(columns: columns, spacing: Theme.Spacing.small) {
                ForEach(dayLabels, id: \.self) { label in
                    Text(label)
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                        .frame(maxWidth: .infinity)
                }
            }

            // Day cells
            LazyVGrid(columns: columns, spacing: Theme.Spacing.small) {
                ForEach(0..<daysInSelectedMonth.count, id: \.self) { idx in
                    if let date = daysInSelectedMonth[idx] {
                        let dateStr = ISO8601DateFormatter().string(from: date).prefix(10).description
                        let pnl = pnlByDate[dateStr]
                        DayCell(date: date, pnlPercent: pnl)
                    } else {
                        Color.clear.frame(minHeight: 28)
                    }
                }
            }
        }
    }

    func changeMonth(_ delta: Int) {
        selectedMonth = Calendar.current.date(
            byAdding: .month, value: delta, to: selectedMonth
        ) ?? selectedMonth
    }
}

struct DayCell: View {
    let date: Date
    let pnlPercent: Double?
    private let bullGreen  = Theme.bullGreen
    private let bearRed    = Theme.bearRed

    var cellColor: Color {
        guard let pnl = pnlPercent else { return Theme.borderFine }
        if pnl >= 1.5  { return bullGreen.opacity(0.85) }
        if pnl >= 0.5  { return bullGreen.opacity(0.50) }
        if pnl >= 0.0  { return bullGreen.opacity(0.20) }
        if pnl >= -0.5 { return bearRed.opacity(0.20) }
        if pnl >= -1.5 { return bearRed.opacity(0.50) }
        return bearRed.opacity(0.85)
    }

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                .fill(cellColor)
                .frame(minHeight: 28)
            Text("\(Calendar.current.component(.day, from: date))")
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(
                    pnlPercent != nil
                        ? .secondary
                        : Theme.inkTertiary
                )
        }
    }
}

// MARK: - Supporting ViewModel

class ValuationCalendarViewModel: ObservableObject {
    @Published var snapshots: [ValuationSnapshot] = []
    @Published var summary: ValuationSummary? = nil
    @Published var isLoading = false
    @Published var selectedPeriod: String = "3M"

    func fetchHistory(userId: Int, period: String) {
        selectedPeriod = period
        isLoading = true

        let days: Int
        switch period {
        case "1M": days = 30
        case "3M": days = 90
        case "6M": days = 180
        case "1Y": days = 365
        default: days = 90
        }

        Task {
            do {
                let response = try await HomeFeedService.shared.fetchValuationHistory(userId: userId, days: days)
                await MainActor.run {
                    self.snapshots = response.snapshots
                    self.summary = response.summary
                    self.isLoading = false
                }
            } catch {
                await MainActor.run { self.isLoading = false }
            }
        }
    }
}

// MARK: - StatPill Component

struct StatPill: View {
    let label: String
    let value: String
    let color: Color
    var body: some View {
        VStack(alignment: .center, spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.serialNumberFont(size: 8))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 12))
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity)
    }
}
