import SwiftUI
import Charts
import Combine

struct ValuationCalendarView: View {
    @StateObject private var vm = ValuationCalendarViewModel()
    let userId: Int

    @State private var selectedSnapshot: ValuationSnapshot? = nil
    @State private var selectedMonth: Date = Date()

    private let goldAccent = Color(red: 0.78, green: 0.64, blue: 0.25)
    private let bullGreen  = Color(red: 0.10, green: 0.53, blue: 0.24)
    private let bearRed    = Color(red: 0.72, green: 0.09, blue: 0.09)
    private let dimText    = Color.primary.opacity(0.45)

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(PaperTexture().opacity(0.6))
                .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.primary.opacity(0.07), lineWidth: 0.5))

            RBISealBackground().opacity(0.04)

            HStack(spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 0) {

                    // Card Header
                    VStack(alignment: .leading, spacing: 2) {
                        Text("मूल्यांकन इतिहास")
                            .font(.system(size: 10, weight: .regular))
                            .foregroundColor(dimText)
                        HStack {
                            Text("PORTFOLIO CALENDAR")
                                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                .tracking(2.0)
                                .foregroundColor(.primary.opacity(0.45))
                            Spacer()
                            // Period selector
                            HStack(spacing: 4) {
                                ForEach(["1M", "3M", "6M", "1Y"], id: \.self) { period in
                                    Button(action: { vm.fetchHistory(userId: userId, period: period) }) {
                                        Text(period)
                                            .font(.system(size: 9, weight: .semibold, design: .monospaced))
                                            .foregroundColor(vm.selectedPeriod == period ? goldAccent : dimText)
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 3)
                                            .background(vm.selectedPeriod == period ? goldAccent.opacity(0.12) : Color.clear)
                                            .cornerRadius(4)
                                    }
                                    .buttonStyle(EKPressStyle())
                                }
                            }
                        }
                    }
                    .padding(.bottom, 10)

                    GuillocheDivider()
                        .padding(.bottom, 14)

                    // Summary Stats Row
                    if let summary = vm.summary {
                        HStack(spacing: 0) {
                            StatPill(
                                label: "PERIOD CHANGE",
                                value: formatCurrency(summary.periodChangeValue),
                                color: summary.periodChangeValue >= 0 ? bullGreen : bearRed
                            )
                            Divider().frame(height: 30).opacity(0.2)
                            StatPill(
                                label: "PEAK",
                                value: formatCurrency(summary.peakValue),
                                color: goldAccent
                            )
                            Divider().frame(height: 30).opacity(0.2)
                            StatPill(
                                label: "DATA POINTS",
                                value: "\(summary.dataPoints) days",
                                color: dimText
                            )
                        }
                        .padding(.bottom, 14)
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
                                AxisGridLine().foregroundStyle(Color.primary.opacity(0.06))
                                AxisValueLabel(format: .dateTime.month(.abbreviated))
                                    .font(.system(size: 9))
                                    .foregroundStyle(dimText)
                            }
                        }
                        .chartYAxis {
                            AxisMarks(position: .trailing) { value in
                                AxisGridLine().foregroundStyle(Color.primary.opacity(0.06))
                                AxisValueLabel {
                                    if let v = value.as(Double.self) {
                                        Text(formatCompact(v))
                                            .font(.system(size: 9, design: .monospaced))
                                            .foregroundStyle(dimText)
                                    }
                                }
                            }
                        }
                        .frame(height: 140)
                        .chartOverlay { proxy in
                            GeometryReader { geo in
                                Rectangle().fill(.clear).contentShape(Rectangle())
                                    .gesture(DragGesture(minimumDistance: 0)
                                        .onChanged { drag in
                                            let x = drag.location.x - geo.frame(in: .local).minX
                                            if let date: Date = proxy.value(atX: x) {
                                                selectedSnapshot = vm.snapshots.min(by: {
                                                    abs($0.parsedDate.timeIntervalSince(date)) <
                                                    abs($1.parsedDate.timeIntervalSince(date))
                                                })
                                            }
                                        }
                                    )
                            }
                        }
                        .padding(.bottom, 12)

                        // Selected day tooltip
                        if let sel = selectedSnapshot {
                            HStack {
                                Text(sel.date)
                                    .font(.system(size: 11, design: .monospaced))
                                    .foregroundColor(dimText)
                                Spacer()
                                Text(formatCurrency(sel.totalValue))
                                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                    .foregroundColor(.primary.opacity(0.85))
                                Text(String(format: "%+.2f%%", sel.pnlPercent))
                                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                                    .foregroundColor(sel.pnlPercent >= 0 ? bullGreen : bearRed)
                            }
                            .padding(.horizontal, 4)
                            .padding(.bottom, 8)
                        }

                        // Calendar Heat Grid
                        CalendarHeatGrid(snapshots: vm.snapshots, selectedMonth: $selectedMonth)
                            .padding(.bottom, 4)
                    } else if vm.isLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity, minHeight: 200)
                    } else {
                        Text("No valuation history yet. First snapshot captured at market close.")
                            .font(.system(size: 12))
                            .foregroundColor(dimText)
                            .frame(maxWidth: .infinity, minHeight: 80)
                            .multilineTextAlignment(.center)
                    }
                }
                .padding(14)
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

    private let columns = Array(repeating: GridItem(.flexible(), spacing: 4), count: 7)
    private let dayLabels = ["M", "T", "W", "T", "F", "S", "S"]
    private let goldAccent = Color(red: 0.78, green: 0.64, blue: 0.25)
    private let bullGreen  = Color(red: 0.10, green: 0.53, blue: 0.24)
    private let bearRed    = Color(red: 0.72, green: 0.09, blue: 0.09)

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
        VStack(spacing: 4) {
            // Month navigation
            HStack {
                Button(action: { changeMonth(-1) }) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(.primary.opacity(0.45))
                }
                .buttonStyle(EKPressStyle())
                Spacer()
                Text(selectedMonth, format: .dateTime.month(.wide).year())
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundColor(.primary.opacity(0.55))
                Spacer()
                Button(action: { changeMonth(1) }) {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(.primary.opacity(0.45))
                }
                .buttonStyle(EKPressStyle())
            }
            .padding(.bottom, 4)

            // Day labels
            LazyVGrid(columns: columns, spacing: 4) {
                ForEach(dayLabels, id: \.self) { label in
                    Text(label)
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundColor(.primary.opacity(0.30))
                        .frame(maxWidth: .infinity)
                }
            }

            // Day cells
            LazyVGrid(columns: columns, spacing: 4) {
                ForEach(0..<daysInSelectedMonth.count, id: \.self) { idx in
                    if let date = daysInSelectedMonth[idx] {
                        let dateStr = ISO8601DateFormatter().string(from: date).prefix(10).description
                        let pnl = pnlByDate[dateStr]
                        DayCell(date: date, pnlPercent: pnl)
                    } else {
                        Color.clear.frame(height: 28)
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
    private let bullGreen  = Color(red: 0.10, green: 0.53, blue: 0.24)
    private let bearRed    = Color(red: 0.72, green: 0.09, blue: 0.09)

    var cellColor: Color {
        guard let pnl = pnlPercent else { return Color.primary.opacity(0.05) }
        if pnl >= 1.5  { return bullGreen.opacity(0.85) }
        if pnl >= 0.5  { return bullGreen.opacity(0.50) }
        if pnl >= 0.0  { return bullGreen.opacity(0.20) }
        if pnl >= -0.5 { return bearRed.opacity(0.20) }
        if pnl >= -1.5 { return bearRed.opacity(0.50) }
        return bearRed.opacity(0.85)
    }

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 5)
                .fill(cellColor)
                .frame(height: 28)
            Text("\(Calendar.current.component(.day, from: date))")
                .font(.system(size: 10, weight: pnlPercent != nil ? .semibold : .regular, design: .monospaced))
                .foregroundColor(
                    pnlPercent != nil
                        ? Color.primary.opacity(0.80)
                        : Color.primary.opacity(0.25)
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
        VStack(alignment: .center, spacing: 3) {
            Text(label)
                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                .tracking(1.0)
                .foregroundColor(Color.primary.opacity(0.35))
            Text(value)
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
    }
}
