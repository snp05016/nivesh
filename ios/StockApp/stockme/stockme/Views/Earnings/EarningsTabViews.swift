import SwiftUI
import EventKit

// MARK: - 1.1 Earnings Progress View

struct EarningsProgressView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                // Full-page error if everything failed
                if vm.isTotalFailure {
                    ErrorDiagnoserView(
                        error: [
                            vm.feedError.map { "Feed: \($0)" },
                            vm.moversError.map { "Movers: \($0)" },
                        ].compactMap { $0 }.joined(separator: "\n\n"),
                        context: ErrorDiagnostic(endpoint: "/api/v1/market/dashboard-pulse", classification: "INFRASTRUCTURE_EXCEPTION"),
                        retryAction: { vm.load() }
                    )
                }

                // YoY Aggregate Indicators (backend sample only; no feed-derived stand-in)
                aggregateCard

                // 1.3 Market Cap Index Aggregator
                marketCapIndexCard
            }
            .padding(Theme.Spacing.card)
        }
        .background(Theme.canvas)
    }

    private var aggregateCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("YoY AGGREGATE MARKET HEALTH")
                .font(.caption2.weight(.bold).monospaced())
                .tracking(2)
                .foregroundStyle(Theme.inkSecondary)

            let health = vm.yoyMarketHealth

            HStack(spacing: Theme.Spacing.none) {
                aggregateMetric(
                    label: "AVG REVENUE GROWTH",
                    value: health?.revenueYoYPct,
                    isLoading: vm.isLoading && health == nil
                )
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 40).padding(.horizontal, Theme.Spacing.card)
                aggregateMetric(
                    label: "AVG NET PROFIT GROWTH",
                    value: health?.netProfitYoYPct,
                    isLoading: vm.isLoading && health == nil
                )
            }

            // Source label: what the numbers actually are, never "NSE AGGREGATE"
            Text(Self.aggregateSourceLabel(for: health))
                .font(.caption2.weight(.medium).monospaced())
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    /// Honest provenance label for the YoY card (FAKE-09).
    static func aggregateSourceLabel(for health: YoYMarketHealth?) -> String {
        guard let health else { return "UNAVAILABLE" }
        switch health.source {
        case "firecrawl": return "MONEYCONTROL AGGREGATE"
        case "yfinance_sample": return "LARGE-CAP SAMPLE · n=\(health.companiesReported)"
        case "fallback": return "UNAVAILABLE"
        default: return health.source.uppercased()
        }
    }

    private func aggregateMetric(label: String, value: Double?, isLoading: Bool) -> some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text(label)
                .font(.caption2.weight(.semibold).monospaced())
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
            if isLoading {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.12)).frame(width: colW * 0.17, height: 22)
            } else if let value {
                Text(IndianFormatter.delta(value))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(.title3.weight(.bold).monospaced())
                    .foregroundStyle(value >= 0 ? Theme.bullGreen : Theme.bearRed)
            } else {
                Text("—")
                    .font(.title3.weight(.bold).monospaced())
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // 1.3 Market Cap Index Aggregator — prefers backend grid, falls back to earnings table
    private var marketCapIndexCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("MARKET CAP INDEX AGGREGATOR")
                .font(.caption2.weight(.bold).monospaced())
                .tracking(2)
                .foregroundStyle(Theme.inkSecondary)

            if !vm.capIndexAggregator.isEmpty {
                // Backend pre-computed grid
                capGridTable
            } else if let dashErr = vm.dashboardError, vm.feed.isEmpty {
                // Backend failed + no feed fallback
                MarketSectionErrorRow(sectionLabel: "CAP INDEX GRID", errorMessage: dashErr)
            } else {
                // Fallback: per-company earnings table
                // 1.3 Multi-Tier Index Weight Tabs
                ScrollView(.horizontal) {
                    HStack(spacing: Theme.Spacing.tight) {
                        ForEach(["all", "nifty50", "large_cap", "mid_cap", "small_cap"], id: \.self) { cap in
                            Button(action: { HapticManager.selection(); vm.selectedMarketCap = cap }) {
                                Text(capLabel(cap))
                                    .font(.caption.weight(vm.selectedMarketCap == cap ? .bold : .regular))
                                    .foregroundStyle(vm.selectedMarketCap == cap ? Theme.securityGold : Theme.inkSecondary)
                                    .padding(.horizontal, Theme.Spacing.medium)
                                    .padding(.vertical, Theme.Spacing.tight)
                                    .background(vm.selectedMarketCap == cap ? Theme.securityGold.opacity(0.10) : Theme.canvasDeep)
                                    .cornerRadius(Theme.CornerRadius.tight)
                                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
                            }
                        }
                    }
                }
                .scrollIndicators(.hidden)
                earningsTable
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    /// Backend pre-computed cap grid table (from /api/v1/market/dashboard-pulse)
    private var capGridTable: some View {
        let colW = UIScreen.main.bounds.width - Theme.Spacing.card * 2  // available content width
        return VStack(spacing: Theme.Spacing.none) {
            // Header
            HStack(spacing: Theme.Spacing.none) {
                Text("BRACKET").tableHeaderStyle().frame(width: colW * 0.20, alignment: .leading)
                Text("MCAP").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("REVENUE").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("PROFIT").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .trailing)
                Text("PE").tableHeaderStyle().frame(width: colW * 0.10, alignment: .trailing)
            }
            .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.tight)
            .background(Theme.canvasDeep)

            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

            ForEach(vm.capIndexAggregator) { row in
                HStack(spacing: Theme.Spacing.none) {
                    Text(row.capBracket.uppercased())
                        .font(.caption2.weight(.bold).monospaced())
                        .foregroundStyle(row.capBracket == "All" ? Theme.securityGold : Theme.inkPrimary)
                        .frame(width: colW * 0.20, alignment: .leading)
                    Text(row.avgMarketCapCr)
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgRevenueCr)
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgNetProfitCr)
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                    Text(row.avgPeRatio.map { String(format: "%.1f", $0) } ?? "—")
                        .font(.caption2.monospaced()).foregroundStyle(Theme.inkTertiary)
                        .frame(width: colW * 0.10, alignment: .trailing)
                }
                .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.medium)
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
            }
        }
        .cornerRadius(Theme.CornerRadius.tight)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
    }

    private func capLabel(_ cap: String) -> String {
        switch cap {
        case "nifty50": return "Nifty 50"
        case "large_cap": return "Large Cap"
        case "mid_cap": return "Mid Cap"
        case "small_cap": return "Small Cap"
        default: return "All"
        }
    }

    private var earningsTable: some View {
        let colW = UIScreen.main.bounds.width - Theme.Spacing.card * 2
        return VStack(spacing: Theme.Spacing.none) {
            // Header row
            HStack(spacing: Theme.Spacing.none) {
                Text("COMPANY").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                Text("REVENUE").tableHeaderStyle().frame(minWidth: colW * 0.22, alignment: .trailing)
                Text("GROSS PROFIT").tableHeaderStyle().frame(minWidth: colW * 0.22, alignment: .trailing)
                Text("NET PROFIT").tableHeaderStyle().frame(minWidth: colW * 0.22, alignment: .trailing)
            }
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.tight)
            .background(Theme.canvasDeep)

            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

            if vm.feed.isEmpty && vm.isLoading {
                ForEach(0..<4, id: \.self) { _ in
                    tableRowPlaceholder
                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                }
            } else {
                let rows = Array(vm.capFilteredFeed.prefix(10))
                ForEach(rows) { result in
                    earningsTableRow(result, tableWidth: colW)
                    if result.id != rows.last?.id {
                        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                    }
                }
            }
        }
        .cornerRadius(Theme.CornerRadius.tight)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
    }

    private func earningsTableRow(_ r: EarningsResult, tableWidth: CGFloat) -> some View {
        let profitGrowth = r.netProfitGrowthPct
        return HStack(spacing: Theme.Spacing.none) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(r.ticker)
                    .font(.caption.weight(.semibold).monospaced())
                    .foregroundStyle(Theme.inkPrimary)
                Text(r.isConsolidated ? "Consolidated" : "Standalone")
                    .font(.caption2)
                    .foregroundStyle(Theme.inkTertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(IndianFormatter.formatLakhsCrores(r.revenue))
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .font(.caption.weight(.medium).monospaced())
                .foregroundStyle(Theme.inkPrimary)
                .frame(minWidth: tableWidth * 0.22, alignment: .trailing)

            Text(r.grossProfit != nil ? IndianFormatter.formatLakhsCrores(r.grossProfit!) : "—")
                .font(.caption.weight(.medium).monospaced())
                .foregroundStyle(Theme.inkSecondary)
                .frame(minWidth: tableWidth * 0.22, alignment: .trailing)

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(IndianFormatter.formatLakhsCrores(r.netProfit))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(.caption.weight(.medium).monospaced())
                    .foregroundStyle(Theme.inkPrimary)
                Text(IndianFormatter.delta(profitGrowth))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(profitGrowth >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
            .frame(minWidth: tableWidth * 0.22, alignment: .trailing)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.medium)
    }

    private var tableRowPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.medium) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.17, height: 12)
            Spacer()
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.medium)
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - 1.2 Earnings Calendar View

// MARK: - Mini Sparkline (7-day price context)

struct MiniSparkline: View {
    let data: [Double]
    let color: Color

    var body: some View {
        let sparkW: CGFloat = 36
        let sparkH: CGFloat = 16
        let minY = data.min() ?? 0
        let maxY = data.max() ?? 1
        let range = max(maxY - minY, 0.01)
        let stepX = sparkW / CGFloat(max(data.count - 1, 1))

        Path { path in
            for (i, val) in data.enumerated() {
                let x = CGFloat(i) * stepX
                let y = sparkH * CGFloat(1 - (val - minY) / range)
                if i == 0 { path.move(to: CGPoint(x: x, y: y)) }
                else { path.addLine(to: CGPoint(x: x, y: y)) }
            }
        }
        .stroke(color.opacity(0.6), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))
    }
}

// MARK: - Calendar View

struct EarningsCalendarView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @EnvironmentObject var authManager: AuthManager
    @State private var alertSetFor: String? = nil

    private let calendar = Calendar.current
    
    private func addEventToCalendar(title: String, dateStr: String) {
        let eventStore = EKEventStore()
        
        let completion: EKEventStoreRequestAccessCompletionHandler = { (granted, error) in
            if granted && error == nil {
                let event = EKEvent(eventStore: eventStore)
                event.title = title
                
                if let date = WireDate.day(dateStr) {
                    event.startDate = date
                    event.endDate = date.addingTimeInterval(60 * 60)
                    event.notes = "Earnings report"
                    event.calendar = eventStore.defaultCalendarForNewEvents
                    
                    do {
                        try eventStore.save(event, span: .thisEvent)
                        DispatchQueue.main.async {
                            HapticManager.notification(.success)
                        }
                    } catch {
                        DispatchQueue.main.async {
                            HapticManager.notification(.error)
                        }
                    }
                }
            }
        }
        
        eventStore.requestWriteOnlyAccessToEvents(completion: completion)
    }

    // Generate 14 days window centred on today
    private var calendarDays: [Date] {
        let today = Date()
        return (-3...10).compactMap { offset in
            calendar.date(byAdding: .day, value: offset, to: today)
        }
    }

    private func dayLabel(_ date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "dd"
        return f.string(from: date)
    }
    private func monthLabel(_ date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "MMM"
        return f.string(from: date).uppercased()
    }
    private func apiDate(_ date: Date) -> String {
        WireDate.dayKey(date)
    }
    private func isSelected(_ date: Date) -> Bool {
        calendar.isDate(date, inSameDayAs: vm.selectedCalendarDate)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                // 1.2 Horizontal Calendar Day Scroller
                calendarScrollRow
                GuillocheDivider()
                // Results for selected date
                selectedDayResults
            }
            .padding(Theme.Spacing.card)
        }
        .background(Theme.canvas)
    }

    private var calendarScrollRow: some View {
        let cellW = UIScreen.main.bounds.width / 5.5
        return ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.medium) {
                ForEach(calendarDays, id: \.self) { date in
                    Button(action: { HapticManager.selection(); vm.selectCalendarDate(date) }) {
                        calendarDayCell(date)
                    }
                    .buttonStyle(EKPressStyle())
                    .frame(width: cellW)
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.small)
        }
        .scrollIndicators(.hidden)
    }

    private func calendarDayCell(_ date: Date) -> some View {
        let sel = isSelected(date)
        let dayStr = apiDate(date)
        let dayResults = vm.calendarDayResults.filter { $0.resultDate == dayStr }
        let count = dayResults.count
        // Extract sparkline from any result that has it
        let sparkData = dayResults.first(where: { !$0.sparkline.isEmpty })?.sparkline ?? []

        return VStack(spacing: Theme.Spacing.small) {
            Text(monthLabel(date))
                .font(.caption2.weight(.medium).monospaced())
                .foregroundStyle(sel ? Theme.securityGold : Theme.inkTertiary)
            Text(dayLabel(date))
                .font(Theme.engravedSerif(size: 16, weight: .bold))
                .foregroundStyle(sel ? Theme.inkPrimary : Theme.inkSecondary)

            // Mini sparkline for dates with price data
            if !sparkData.isEmpty {
                MiniSparkline(data: sparkData, color: sel ? Theme.securityGold : Theme.inkTertiary)
                    .frame(width: 36, height: 16)
            } else if count > 0 {
                Text("\(count)")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(sel ? Theme.securityGold : Theme.inkTertiary)
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, Theme.Spacing.xSmall)
                    .background(sel ? Theme.securityGold.opacity(0.15) : Theme.inkTertiary.opacity(0.08))
                    .cornerRadius(Theme.CornerRadius.small)
            } else {
                Color.clear.frame(height: 16)
            }
        }
        .padding(.vertical, Theme.Spacing.medium)
        .background(sel ? Theme.securityGold.opacity(0.08) : Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(sel ? Theme.securityGold.opacity(0.4) : Theme.borderSage, lineWidth: sel ? 1 : 0.5)
        )
    }

    // 1.2 Earnings Count Volume Badge on day header
    private var selectedDayResults: some View {
        let humanDate: String = {
            let df = DateFormatter()
            df.dateFormat = "dd MMM"
            return df.string(from: vm.selectedCalendarDate)
        }()
        let count = vm.calendarDayResults.count
        return VStack(alignment: .leading, spacing: Theme.Spacing.standard) {

            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    // 1.2 count badge in title
                    Text("\(humanDate) — \(count) Earnings")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("Tap a company row to set an earnings alert")
                        .font(.caption)
                        .foregroundStyle(Theme.inkTertiary)
                }
                Spacer()
            }

            if vm.calendarDayResults.isEmpty {
                Text("No results scheduled for this date.")
                    .font(.footnote)
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, Theme.Spacing.large)
            } else {
                ForEach(vm.calendarDayResults) { result in
                    calendarResultRow(result)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func calendarResultRow(_ r: EarningsCalendarItem) -> some View {
        let userId = authManager.currentUser?.userId ?? 0
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                HStack(spacing: Theme.Spacing.tight) {
                    Text(r.ticker)
                        .font(.footnote.weight(.bold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                    Text(r.isConsolidated ? "Consol" : "Standalone")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.inkTertiary.opacity(0.08))
                        .cornerRadius(Theme.CornerRadius.small)
                    // 7-day price change badge
                    if let chg = r.priceChange7dPct {
                        Text(IndianFormatter.delta(chg))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(chg >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                Text(r.companyName)
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
                // Sparkline row
                if !r.sparkline.isEmpty {
                    MiniSparkline(data: r.sparkline, color: (r.priceChange7dPct ?? 0) >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(height: UIScreen.main.bounds.height * 0.024)
                        .padding(.top, Theme.Spacing.xSmall)
                }
            }
            Spacer()
            // 1.4 Embedded Alert Trigger
            VStack(spacing: Theme.Spacing.small) {
                Button(action: {
                    HapticManager.selection()
                    Task {
                        do {
                            try await NetworkManager.shared.setEarningsAlert(userId: userId, ticker: r.ticker, date: r.resultDate)
                            alertSetFor = r.ticker
                            HapticManager.notification(.success)
                        } catch {
                            vm.alertError = (error as? NetworkError)?.displayDetail ?? error.localizedDescription
                            HapticManager.notification(.error)
                        }
                    }
                }) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: alertSetFor == r.ticker ? "bell.fill" : "bell")
                            .font(.caption)
                        Text("Alert")
                            .font(.caption.weight(.medium))
                    }
                    .frame(width: colW * 0.17)
                    .foregroundStyle(alertSetFor == r.ticker ? Theme.securityGold : Theme.inkSecondary)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.tight)
                    .background(alertSetFor == r.ticker ? Theme.securityGold.opacity(0.10) : Theme.canvasDeep)
                    .cornerRadius(Theme.CornerRadius.tight)
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
                }
                
                Button(action: {
                    HapticManager.selection()
                    addEventToCalendar(title: "\(r.ticker) Earnings", dateStr: r.resultDate)
                }) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "calendar.badge.plus")
                            .font(.caption)
                        Text("iCal")
                            .font(.caption.weight(.medium))
                    }
                    .frame(width: colW * 0.17)
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.tight)
                    .background(Theme.canvasDeep)
                    .cornerRadius(Theme.CornerRadius.tight)
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderSage, lineWidth: 0.5))
                }
            }
        }
        .padding(.vertical, Theme.Spacing.medium)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }
}

// MARK: - 2.1 / 2.2 Earnings Feed View

struct EarningsFeedView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            // 2.2 Tabbed Performance Sorting Grid
            sortTabBar
            ScrollView {
                LazyVStack(spacing: Theme.Spacing.standard) {
                    if vm.isLoading && vm.feed.isEmpty {
                        ForEach(0..<6, id: \.self) { _ in feedCardPlaceholder }
                    } else if vm.filteredFeed.isEmpty {
                        // Universal diagnostic error display
                        ErrorDiagnoserView(
                            error: vm.feedError ?? vm.feedDiagnostic
                                ?? (vm.feedDataSource != nil
                                    ? "Data source: \(vm.feedDataSource!). No results available.\n\nQuarterly results for the tracked large caps could not be loaded. Please retry shortly."
                                    : "Backend returned empty results.\n\nQuarterly results for the tracked large caps could not be loaded. Please retry shortly."),
                            context: ErrorDiagnostic(
                                endpoint: "/api/v1/earnings/feed",
                                classification: vm.feedError != nil ? "INFRASTRUCTURE_EXCEPTION" : "DATA_EMPTY"
                            ),
                            retryAction: { vm.load() }
                        )
                    } else {
                        ForEach(vm.filteredFeed) { result in
                            EarningsResultCard(result: result)
                        }
                    }
                }
                .padding(Theme.Spacing.card)
            }
        }
        .background(Theme.canvas)
    }

    private var sortTabBar: some View {
        VStack(spacing: Theme.Spacing.none) {
            HStack(spacing: Theme.Spacing.none) {
                ForEach([("latest", "Latest Results"), ("best", "Best Performer"), ("worst", "Worst Performer")], id: \.0) { key, label in
                    Button(action: { HapticManager.selection(); vm.selectedSort = key }) {
                        Text(label)
                            .font(.caption.weight(vm.selectedSort == key ? .bold : .regular))
                            .foregroundStyle(vm.selectedSort == key ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.vertical, Theme.Spacing.medium)
                            .frame(maxWidth: .infinity)
                            .background(vm.selectedSort == key ? Theme.securityGold.opacity(0.08) : Color.clear)
                    }
                }
            }
            // Data source indicator
            if let src = vm.feedDataSource {
                HStack(spacing: Theme.Spacing.small) {
                    Circle()
                        .fill(src == "empty" ? Theme.bearRed : Theme.bullGreen)
                        .frame(width: 5, height: 5)
                    Text("Source: \(src.replacingOccurrences(of: "_", with: " ").uppercased())")
                        .font(.caption2.weight(.medium).monospaced())
                        .foregroundStyle(Theme.inkTertiary.opacity(0.6))
                }
                .padding(.vertical, Theme.Spacing.small)
            }
        }
        .background(Theme.canvasDeep)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }

    private var feedCardPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.28, height: 13)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(height: 13)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.45, height: 11)
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - 2.1 / 2.4 Earnings Result Card

struct EarningsResultCard: View {
    let result: EarningsResult

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Header row
            HStack(spacing: Theme.Spacing.medium) {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(result.ticker)
                            .font(.subheadline.weight(.bold).monospaced())
                            .foregroundStyle(Theme.inkPrimary)
                        Text(result.isConsolidated ? "CONSOL" : "STANDALONE")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(1)
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.inkTertiary.opacity(0.08))
                            .cornerRadius(Theme.CornerRadius.small)
                    }
                    Text(result.companyName)
                        .font(.caption)
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                    Text(IndianFormatter.price(result.ltp))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(.footnote.weight(.semibold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                    Text(IndianFormatter.delta(result.changePercent))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(.caption.weight(.bold))
                        .foregroundStyle(result.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
            }

            // Sparkline price context
            if let spark = result.sparkline, !spark.isEmpty {
                HStack(spacing: Theme.Spacing.medium) {
                    MiniSparkline(data: spark, color: result.netProfitGrowthPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(height: UIScreen.main.bounds.height * 0.026)
                    if let chg7d = result.priceChange7dPct {
                        Text("7d: \(IndianFormatter.delta(chg7d))")
                            .font(.caption2.weight(.medium).monospaced())
                            .foregroundStyle(chg7d >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                .padding(.vertical, Theme.Spacing.small)
            }

            GuillocheDivider()

            // 2.4 Historical period baseline rows
            HStack(spacing: Theme.Spacing.none) {
                metricColumn(
                    label: "NET SALES",
                    current: IndianFormatter.formatLakhsCrores(result.revenue),
                    growth: result.revenueGrowthPct
                )
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 44).padding(.horizontal, Theme.Spacing.medium)
                metricColumn(
                    label: "NET PROFIT",
                    current: IndianFormatter.formatLakhsCrores(result.netProfit),
                    growth: result.netProfitGrowthPct
                )
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 44).padding(.horizontal, Theme.Spacing.medium)
                metricColumn(
                    label: "MARGIN",
                    current: String(format: "%.1f%%", result.netProfitMarginPct),
                    growth: nil
                )
            }

            // 2.1 Absolute elapsed timestamp
            if let reportedDate = result.parsedReportedAt {
                Text(IndianFormatter.elapsed(from: reportedDate))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }

    private func metricColumn(label: String, current: String, growth: Double?) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label)
                .font(.caption2.weight(.semibold).monospaced())
                .tracking(1)
                .foregroundStyle(Theme.inkTertiary)
            Text(current)
                .font(.footnote.weight(.semibold).monospaced())
                .foregroundStyle(Theme.inkPrimary)
            if let g = growth {
                Text(IndianFormatter.delta(g))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(g >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - 4.1 / 4.2 / 4.3 Variance Tracker View

struct VarianceTrackerView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @State private var estimates: [EarningsEstimate] = []
    @State private var expectationFilter: String = "all"  // all | high | low
    @State private var isLoading = false

    var filteredEstimates: [EarningsEstimate] {
        switch expectationFilter {
        case "high":
            return estimates.filter { ($0.revenueSurprisePct ?? 0) > 5 }
        case "low":
            return estimates.filter { ($0.revenueSurprisePct ?? 0) < -5 }
        default:
            return estimates
        }
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            // 4.3 Pre-Result Sentiment Segmentation Tabs
            expectationFilterBar
            ScrollView {
                LazyVStack(spacing: Theme.Spacing.standard) {
                    if isLoading && estimates.isEmpty {
                        ForEach(0..<4, id: \.self) { _ in variancePlaceholder }
                    } else if filteredEstimates.isEmpty {
                        Text("No variance data available.")
                            .font(.footnote)
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(Theme.Spacing.xLarge)
                    } else {
                        ForEach(filteredEstimates) { est in
                            VarianceCard(estimate: est)
                        }
                    }
                }
                .padding(Theme.Spacing.card)
            }
        }
        .background(Theme.canvas)
        .onAppear { loadEstimates() }
    }

    private var expectationFilterBar: some View {
        HStack(spacing: Theme.Spacing.none) {
            ForEach([("all","All"), ("high","High Expectations"), ("low","Low Expectations")], id: \.0) { key, label in
                Button(action: { HapticManager.selection(); expectationFilter = key }) {
                    Text(label)
                        .font(.caption.weight(expectationFilter == key ? .bold : .regular))
                        .foregroundStyle(expectationFilter == key ? Theme.securityGold : Theme.inkTertiary)
                        .padding(.vertical, Theme.Spacing.medium)
                        .frame(maxWidth: .infinity)
                        .background(expectationFilter == key ? Theme.securityGold.opacity(0.08) : Color.clear)
                }
            }
        }
        .background(Theme.canvasDeep)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }

    private var variancePlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.28, height: 13)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(height: 60)
        }
        .padding(Theme.Spacing.standard).banknoteCard().shimmerPlaceholder(isLoading: true)
    }

    private func loadEstimates() {
        isLoading = true
        Task {
            // Load estimates for top 20 from current feed
            var loaded: [EarningsEstimate] = []
            for ticker in vm.filteredFeed.prefix(20).map({ $0.ticker }) {
                if let est = try? await NetworkManager.shared.fetchEarningsEstimates(ticker: ticker) {
                    loaded.append(est)
                }
            }
            estimates = loaded
            isLoading = false
        }
    }
}

// MARK: - 4.1 / 4.2 Variance Card

struct VarianceCard: View {
    let estimate: EarningsEstimate

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(estimate.ticker)
                        .font(.subheadline.weight(.bold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                    Text(estimate.companyName)
                        .font(.caption)
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                surpriseChip(pct: estimate.revenueSurprisePct ?? estimate.netProfitSurprisePct)
            }

            // 4.1 Three-column matrix: Revenue, Net Profit, EPS
            HStack(spacing: Theme.Spacing.none) {
                varianceColumn(label: "REVENUE",
                               estimate: estimate.revenueEstimate.map { IndianFormatter.formatLakhsCrores($0) },
                               actual: estimate.revenueActual.map { IndianFormatter.formatLakhsCrores($0) },
                               variancePct: estimate.revenueSurprisePct)
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 50).padding(.horizontal, Theme.Spacing.tight)
                varianceColumn(label: "NET PROFIT",
                               estimate: estimate.netProfitEstimate.map { IndianFormatter.formatLakhsCrores($0) },
                               actual: estimate.netProfitActual.map { IndianFormatter.formatLakhsCrores($0) },
                               variancePct: estimate.netProfitSurprisePct)
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(width: 0.5, height: 50).padding(.horizontal, Theme.Spacing.tight)
                varianceColumn(label: "EPS",
                               estimate: estimate.epsEstimate.map { String(format: "₹%.2f", $0) },
                               actual: estimate.epsActual.map { String(format: "₹%.2f", $0) },
                               variancePct: nil)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }

    private func varianceColumn(label: String, estimate: String?, actual: String?, variancePct: Double?) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text(label)
                .font(.caption2.weight(.semibold).monospaced())
                .tracking(1)
                .foregroundStyle(Theme.inkTertiary)
            if let est = estimate {
                HStack(spacing: Theme.Spacing.small) {
                    Text("Est:").font(.caption2).foregroundStyle(Theme.inkTertiary)
                    Text(est).font(.caption.weight(.medium)).foregroundStyle(Theme.inkSecondary)
                }
            }
            if let act = actual {
                HStack(spacing: Theme.Spacing.small) {
                    Text("Act:").font(.caption2).foregroundStyle(Theme.inkTertiary)
                    Text(act).font(.caption.weight(.semibold)).foregroundStyle(Theme.inkPrimary)
                }
            }
            if let pct = variancePct {
                Text(IndianFormatter.delta(pct))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(pct >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // 4.2 Semantic Color-Coded State Chips
    private func surpriseChip(pct: Double?) -> some View {
        guard let pct = pct else {
            return AnyView(EmptyView())
        }
        let beats = pct >= 0
        let label = beats ? "BEATS EXPECTATIONS" : "MISSED EXPECTATIONS"
        let color: Color = beats ? Theme.bullGreen : Theme.bearRed
        return AnyView(
            Text(label)
                .font(.caption2.weight(.bold).monospaced())
                .tracking(1)
                .foregroundStyle(color)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .background(color.opacity(0.10))
                .cornerRadius(Theme.CornerRadius.small)
                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(color.opacity(0.3), lineWidth: 0.5))
        )
    }
}

// MARK: - 5. Post-Result Price Action Monitor

struct PostResultMonitorView: View {
    @ObservedObject var vm: EarningsDashboardViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("POST-RESULT PRICE SHOCKER MATRIX")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("Equities experiencing peak volatility after earnings")
                            .font(.caption)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    // 5-second refresh indicator
                    HStack(spacing: Theme.Spacing.small) {
                        Circle()
                            .fill(Theme.bullGreen)
                            .frame(width: 6, height: 6)
                        Text("5s refresh")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.top, Theme.Spacing.card)

                // Table header
                let headerW = UIScreen.main.bounds.width
                HStack(spacing: Theme.Spacing.none) {
                    Text("COMPANY").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                    Text("RESULT DATE").tableHeaderStyle().frame(minWidth: headerW * 0.20, alignment: .trailing)
                    Text("LTP").tableHeaderStyle().frame(minWidth: headerW * 0.20, alignment: .trailing)
                    Text("CHG %").tableHeaderStyle().frame(minWidth: headerW * 0.16, alignment: .trailing)
                }
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.medium)
                .background(Theme.canvasDeep)

                if vm.isLoading && vm.postResultMovers.isEmpty {
                    ForEach(0..<5, id: \.self) { _ in
                        moverRowPlaceholder
                    }
                } else if vm.postResultMovers.isEmpty {
                    Text("No significant post-result movers currently.")
                        .font(.footnote)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(Theme.Spacing.xLarge)
                        .frame(maxWidth: .infinity)
                } else {
                    ForEach(vm.postResultMovers) { mover in
                        postResultRow(mover)
                        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5).padding(.horizontal, Theme.Spacing.card)
                    }
                }
            }
            .padding(.bottom, Theme.screenPadding)
        }
        .background(Theme.canvas)
        // 5-second throttle loop during market hours
        .onAppear { startVolatilityThrottle() }
        .onDisappear { stopVolatilityThrottle() }
    }

    @State private var throttleTask: Task<Void, Never>? = nil

    private func startVolatilityThrottle() {
        throttleTask?.cancel()
        throttleTask = Task {
            while !Task.isCancelled {
                let hour = Calendar.current.component(.hour, from: Date())
                // Active market hours: 9:15 AM – 3:30 PM IST
                if hour >= 9 && hour < 16 {
                    let movers = (try? await NetworkManager.shared.fetchPostResultMovers()) ?? []
                    if !Task.isCancelled { vm.postResultMovers = movers }
                }
                try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds
            }
        }
    }

    private func stopVolatilityThrottle() {
        throttleTask?.cancel()
        throttleTask = nil
    }

    private func postResultRow(_ m: PostResultMover) -> some View {
        let isPos = m.changePercent >= 0
        let rowW = UIScreen.main.bounds.width
        return HStack(spacing: Theme.Spacing.none) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(m.ticker)
                    .font(.footnote.weight(.bold).monospaced())
                    .foregroundStyle(Theme.inkPrimary)
                Text(m.companyName)
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(m.resultDate)
                .font(.caption.monospaced())
                .foregroundStyle(Theme.inkTertiary)
                .frame(minWidth: rowW * 0.20, alignment: .trailing)

            Text(IndianFormatter.price(m.ltp))
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .font(.footnote.weight(.semibold).monospaced())
                .foregroundStyle(Theme.inkPrimary)
                .frame(minWidth: rowW * 0.20, alignment: .trailing)

            HStack(spacing: Theme.Spacing.small) {
                // Directional Trend Indicator
                Image(systemName: isPos ? "arrow.up" : "arrow.down")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(isPos ? Theme.bullGreen : Theme.bearRed)
                Text(IndianFormatter.delta(m.changePercent))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(.caption.weight(.bold).monospaced())
                    .foregroundStyle(isPos ? Theme.bullGreen : Theme.bearRed)
            }
            .frame(minWidth: rowW * 0.16, alignment: .trailing)
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.medium)
    }

    private var moverRowPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.none) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.31, height: 10)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.17, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.15, height: 12).padding(.leading, Theme.Spacing.medium)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.15, height: 12).padding(.leading, Theme.Spacing.medium)
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - Helper: Table Header Text Style

extension Text {
    func tableHeaderStyle() -> some View {
        self
            .font(.caption2.weight(.bold).monospaced())
            .tracking(1.2)
            .foregroundStyle(Theme.inkTertiary)
    }
}

#Preview("Variance Card") {
    VarianceCard(estimate: EarningsEstimate(
        ticker: "RELIANCE",
        companyName: "Reliance Industries Ltd",
        revenueEstimate: 250000,
        revenueActual: 265000,
        netProfitEstimate: 18000,
        netProfitActual: 19500,
        epsEstimate: 28.5,
        epsActual: 30.2
    ))
    .padding()
    .background(Theme.canvas)
}

#Preview("Post Result Row") {
    PostResultMonitorView(vm: EarningsDashboardViewModel())
        .environmentObject(AuthManager())
}
