import SwiftUI
import Charts

/// One Time Machine session: clock, book, watchlist, wire and advance controls.
/// Everything shown is as of the simulated clock; hindsight appears only after the end.
struct TimeMachineSessionView: View {
    @StateObject private var vm: LabSessionViewModel
    @State private var ticket: LabTicketRequest?

    init(sessionId: String) {
        _vm = StateObject(wrappedValue: LabSessionViewModel(sessionId: sessionId))
    }

    var body: some View {
        LabScreen(title: vm.session?.title ?? "Time Machine") {
            StateCard(title: "this session", phase: vm.phase, onRetry: vm.load) {
                if let state = vm.state {
                    LabSessionContent(vm: vm, state: state, onTrade: { symbol, side in
                        HapticManager.selection()
                        ticket = LabTicketRequest(symbol: symbol, side: side)
                    })
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink(value: LabRoute.mentor(sessionId: vm.sessionId, orderId: nil)) {
                    Image(systemName: "bubble.left.and.text.bubble.right")
                }
                .accessibilityLabel("Ask the mentor about this session")
            }
        }
        .sheet(item: $ticket) { req in
            OrderTicketView(request: req, lastClose: vm.session?.watchlist?.first { $0.symbol == req.symbol }?.close,
                            onSubmit: { draft in await vm.send(.order(draft)) })
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
    }
}

struct LabTicketRequest: Identifiable, Hashable {
    let symbol: String
    let side: String
    var id: String { symbol + side }
}

/// Sections below the header. Split into structs (AGENTS.md §6.6).
private struct LabSessionContent: View {
    @ObservedObject var vm: LabSessionViewModel
    let state: LabSimState
    let onTrade: (String, String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            LabCaveatBanner(warnings: vm.warnings)
            LabSessionHeader(state: state, performance: vm.session?.performance)
            if let err = vm.actionError { LabInlineError(message: err) }
            if !vm.isFinished {
                LabAdvanceBar(busy: vm.isSending, onAdvance: { days in Task { await vm.advance(days: days) } })
            }
            LabEquityChart(points: state.equityCurve ?? [], benchmark: vm.session?.benchmark)
            if vm.isFinished { LabFinishedSection(vm: vm) }
            LabWatchlistCard(sessionId: vm.sessionId, rows: vm.session?.watchlist ?? [], finished: vm.isFinished, onTrade: onTrade)
            LabPositionsCard(positions: state.positions ?? [], finished: vm.isFinished, onTrade: onTrade)
            LabOrdersCard(orders: (state.orders ?? []).filter { $0.statusKind.isWorking }, busy: vm.isSending,
                          onCancel: { id in Task { await vm.cancelOrder(id) } })
            LabClosedTradesCard(sessionId: vm.sessionId, trades: state.trades ?? [])
            LabNewsWire(items: vm.session?.news ?? [])
            if let assumptions = state.assumptions, !assumptions.isEmpty { LabAssumptions(items: assumptions) }
        }
    }
}

private struct LabSessionHeader: View {
    let state: LabSimState
    let performance: LabPerformance?

    private var progress: Double {
        guard let i = state.dayIndex, let n = state.daysTotal, n > 0 else { return 0 }
        return min(Double(i) / Double(n), 1)
    }

    var body: some View {
        LabCard {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("SIMULATED DATE").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
                    Text(LabFormat.day(state.clock))
                        .font(Theme.dataLarge(size: 24))
                        .foregroundStyle(Theme.securityGold)
                }
                Spacer()
                if state.finished == true { LabChip(text: "Finished", tint: Theme.bullGreen, icon: "flag.checkered") }
            }
            .accessibilityElement(children: .combine)
            ProgressView(value: progress)
                .tint(Theme.securityGold)
                .accessibilityLabel("Day \(state.dayIndex ?? 0) of \(state.daysTotal ?? 0)")
            Text("Day \(state.dayIndex ?? 0) of \(state.daysTotal ?? 0)")
                .font(Theme.microLabel())
                .foregroundStyle(Theme.inkSecondary)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                LabStatTile(label: "Equity", value: LabFormat.money(state.equity))
                LabStatTile(label: "Cash", value: LabFormat.money(state.cash))
                LabStatTile(label: "Return", value: LabFormat.pct(performance?.totalReturn), tint: LabFormat.tint(performance?.totalReturn))
                LabStatTile(label: "Benchmark", value: LabFormat.pct(performance?.benchmarkReturn), tint: LabFormat.tint(performance?.benchmarkReturn))
                LabStatTile(label: "Costs paid", value: LabFormat.money(performance?.costsInr))
                LabStatTile(label: "Max drawdown", value: LabFormat.pct(performance?.maxDrawdown.map { -abs($0) }), tint: Theme.bearRed)
            }
        }
    }
}

private struct LabAdvanceBar: View {
    let busy: Bool
    let onAdvance: (Int) -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            ForEach([1, 5, 20], id: \.self) { days in
                Button {
                    HapticManager.selection()
                    onAdvance(days)
                } label: {
                    Text("+\(days) \(days == 1 ? "day" : "days")")
                        .font(Theme.monoTabular(size: 14, relativeTo: .subheadline))
                        .foregroundStyle(Theme.onAccent)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(Capsule().fill(busy ? Theme.inkTertiary.opacity(0.4) : Theme.securityGold))
                }
                .buttonStyle(EKPressStyle())
                .disabled(busy)
                .accessibilityLabel("Advance the clock by \(days) trading \(days == 1 ? "day" : "days")")
            }
        }
    }
}

/// Equity vs benchmark, both rebased to 100 at the first point.
private struct LabEquityChart: View {
    private struct Point: Identifiable {
        let id: String
        let date: Date
        let series: String
        let value: Double
    }

    let points: [LabEquityPoint]
    let benchmark: String?

    private var rebased: [Point] {
        let dated = points.compactMap { p -> (Date, LabEquityPoint)? in
            guard let d = p.d, let date = WireDate.dayFormatter.date(from: d) else { return nil }
            return (date, p)
        }
        guard let e0 = dated.first?.1.equity, e0 > 0 else { return [] }
        let b0 = dated.first { ($0.1.benchmark ?? 0) > 0 }?.1.benchmark
        var out: [Point] = []
        for (date, p) in dated {
            if let e = p.equity { out.append(Point(id: "e\(date)", date: date, series: "You", value: e / e0 * 100)) }
            if let b = p.benchmark, let b0, b0 > 0 { out.append(Point(id: "b\(date)", date: date, series: "Benchmark", value: b / b0 * 100)) }
        }
        return out
    }

    var body: some View {
        LabCard {
            LabCardTitle(title: "Growth of ₹100", icon: "chart.xyaxis.line")
            let data = rebased
            if data.count < 2 {
                Text("Advance the clock to draw your equity curve.")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkTertiary)
            } else {
                Chart(data) { p in
                    LineMark(x: .value("Date", p.date), y: .value("Value (₹)", p.value))
                        .foregroundStyle(by: .value("Series", p.series))
                        .interpolationMethod(.monotone)
                }
                .chartForegroundStyleScale(["You": Theme.securityGold, "Benchmark": Theme.inkTertiary])
                .chartYScale(domain: .automatic(includesZero: false))
                .chartYAxisLabel("₹ (start = 100)")
                .chartXAxisLabel("Simulated date")
                .frame(height: UIScreen.main.bounds.height * 0.25)
                .accessibilityLabel("Equity versus \(benchmark ?? "benchmark"), rebased to 100. Latest: \(LabFormat.num(data.last { $0.series == "You" }?.value, digits: 1)).")
            }
        }
    }
}

private struct LabWatchlistCard: View {
    let sessionId: String
    let rows: [LabWatchRow]
    let finished: Bool
    let onTrade: (String, String) -> Void

    var body: some View {
        LabCard {
            LabCardTitle(title: "Watchlist", icon: "list.bullet")
            if rows.isEmpty {
                Text("No symbols in this session.").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
            ForEach(rows) { row in
                LabWatchRowView(sessionId: sessionId, row: row, finished: finished, onTrade: onTrade)
            }
        }
    }
}

private struct LabWatchRowView: View {
    let sessionId: String
    let row: LabWatchRow
    let finished: Bool
    let onTrade: (String, String) -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            NavigationLink(value: LabRoute.chart(sessionId: sessionId, symbol: row.symbol)) {
                LabWatchRowLabel(row: row)
            }
            .buttonStyle(EKPressStyle())
            .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
            if !finished, row.listed != false {
                Button { onTrade(row.symbol, "BUY") } label: {
                    Text("Trade")
                        .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                        .foregroundStyle(Theme.securityGold)
                        .frame(minWidth: 44, minHeight: 44)
                }
                .buttonStyle(EKPressStyle())
                .accessibilityLabel("Open an order ticket for \(row.symbol)")
            }
        }
    }
}

private struct LabWatchRowLabel: View {
    let row: LabWatchRow

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(row.symbol)
                    .font(Theme.monoTabular(size: 14, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
                if row.listed == false {
                    Text("Not listed yet").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
                } else if row.stale == true {
                    LabChip(text: "Stale: \(LabFormat.day(row.date))", tint: Theme.holdAmber, icon: "clock.badge.exclamationmark")
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(LabFormat.price(row.close)).font(Theme.monoTabular(size: 14)).foregroundStyle(Theme.inkPrimary)
                HStack(spacing: Theme.Spacing.small) {
                    Text("1d \(LabFormat.pct(row.chg1d))").foregroundStyle(LabFormat.tint(row.chg1d))
                    Text("20d \(LabFormat.pct(row.chg20d))").foregroundStyle(LabFormat.tint(row.chg20d))
                }
                .font(Theme.microLabel())
            }
        }
        .frame(minHeight: 44)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the price chart up to the simulated date")
    }
}

private struct LabPositionsCard: View {
    let positions: [LabPosition]
    let finished: Bool
    let onTrade: (String, String) -> Void

    var body: some View {
        LabCard {
            LabCardTitle(title: "Positions", icon: "briefcase")
            if positions.isEmpty {
                Text("No open positions.").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
            ForEach(positions, id: \.self) { p in
                LabPositionRow(position: p, finished: finished, onSell: { onTrade(p.symbol ?? "", "SELL") })
            }
        }
    }
}

private struct LabPositionRow: View {
    let position: LabPosition
    let finished: Bool
    let onSell: () -> Void

    var body: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(position.symbol ?? "—").font(Theme.monoTabular(size: 14)).foregroundStyle(Theme.inkPrimary)
                Text("\(LabFormat.qty(position.qty)) @ \(LabFormat.price(position.avgCost)) · last \(LabFormat.price(position.last))")
                    .font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(LabFormat.money(position.value)).font(Theme.monoTabular(size: 14)).foregroundStyle(Theme.inkPrimary)
                Text(position.unrealised.map { IndianFormatter.signedPrice($0) } ?? "—")
                    .font(Theme.microLabel()).foregroundStyle(LabFormat.tint(position.unrealised))
            }
            if !finished {
                Button(action: onSell) {
                    Text("Sell").font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                        .foregroundStyle(Theme.bearRed).frame(minWidth: 44, minHeight: 44)
                }
                .buttonStyle(EKPressStyle())
                .accessibilityLabel("Open a sell ticket for \(position.symbol ?? "this position")")
            }
        }
        .accessibilityElement(children: .contain)
    }
}

private struct LabOrdersCard: View {
    let orders: [LabOrder]
    let busy: Bool
    let onCancel: (String) -> Void

    var body: some View {
        LabCard {
            LabCardTitle(title: "Open orders", icon: "tray.full")
            if orders.isEmpty {
                Text("No working orders. Orders placed today can fill from the next session.")
                    .font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
            ForEach(orders) { o in
                LabOrderRow(order: o, busy: busy, onCancel: { onCancel(o.id) })
            }
        }
    }
}

private struct LabOrderRow: View {
    let order: LabOrder
    let busy: Bool
    let onCancel: () -> Void

    private var priceText: String {
        switch order.orderType {
        case "LIMIT": return "limit \(LabFormat.price(order.limit))"
        case "STOP": return "stop \(LabFormat.price(order.stop))"
        default: return "market"
        }
    }

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("\(order.side ?? "") \(LabFormat.qty(order.qty)) \(order.symbol ?? "")")
                    .font(Theme.monoTabular(size: 13))
                    .foregroundStyle(order.side == "SELL" ? Theme.bearRed : Theme.bullGreen)
                Text("\(order.id) · \(priceText) · \(order.tif ?? "DAY") · \(order.status ?? "")")
                    .font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
            }
            Spacer()
            Button {
                HapticManager.selection()
                onCancel()
            } label: {
                Text("Cancel").font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                    .foregroundStyle(Theme.bearRed).frame(minWidth: 44, minHeight: 44)
            }
            .buttonStyle(EKPressStyle())
            .disabled(busy)
            .accessibilityLabel("Cancel order \(order.id)")
        }
    }
}

private struct LabClosedTradesCard: View {
    let sessionId: String
    let trades: [LabTrade]

    var body: some View {
        if !trades.isEmpty {
            LabCard {
                LabCardTitle(title: "Closed trades", icon: "checkmark.rectangle.stack")
                ForEach(trades, id: \.self) { t in
                    if let oid = t.entryOrderId {
                        NavigationLink(value: LabRoute.autopsy(sessionId: sessionId, orderId: oid)) { LabTradeRow(trade: t) }
                            .buttonStyle(EKPressStyle())
                            .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
                    } else {
                        LabTradeRow(trade: t)
                    }
                }
            }
        }
    }
}

private struct LabTradeRow: View {
    let trade: LabTrade

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("\(trade.symbol ?? "—") × \(LabFormat.qty(trade.qty))").font(Theme.monoTabular(size: 13)).foregroundStyle(Theme.inkPrimary)
                Text("\(LabFormat.day(trade.entryDate)) → \(LabFormat.day(trade.exitDate))").font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(trade.pnl.map { IndianFormatter.signedPrice($0) } ?? "—").font(Theme.monoTabular(size: 13)).foregroundStyle(LabFormat.tint(trade.pnl))
                Text("Autopsy").font(Theme.microLabel()).foregroundStyle(Theme.securityGold)
            }
        }
        .frame(minHeight: 44)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the trade autopsy")
    }
}

/// Sourced headlines dated on or before the clock, newest first.
private struct LabNewsWire: View {
    let items: [LabNewsItem]

    var body: some View {
        LabCard {
            LabCardTitle(title: "Market wire", icon: "newspaper")
            if items.isEmpty {
                Text("No sourced headlines up to this date.").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
            ForEach(items.prefix(12), id: \.self) { item in
                LabNewsRow(item: item)
            }
        }
    }
}

private struct LabNewsRow: View {
    let item: LabNewsItem

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack(spacing: Theme.Spacing.small) {
                Text(LabFormat.day(item.date)).font(Theme.microLabel()).foregroundStyle(Theme.securityGold)
                if let s = item.symbol { Text(s).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary) }
            }
            Text(item.title ?? "")
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
            if let src = item.source {
                if let raw = item.url, let url = URL(string: raw), url.scheme == "https" {
                    Link(src, destination: url).font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
                } else {
                    Text(src).font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

private struct LabAssumptions: View {
    let items: [String]

    var body: some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                ForEach(items, id: \.self) { a in
                    Text("• \(a)").font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        } label: {
            LabCardTitle(title: "Simulation assumptions", icon: "info.circle")
        }
        .tint(Theme.securityGold)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

/// After the last session: performance, scenario debrief (hindsight) and behaviour review.
private struct LabFinishedSection: View {
    @ObservedObject var vm: LabSessionViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            if let perf = vm.session?.performance { LabPerformanceCard(perf: perf) }
            if let sc = vm.debrief { LabDebriefCard(scenario: sc) }
            if let flags = vm.review?.behaviour, !flags.isEmpty { LabBehaviourCard(flags: flags) }
            NavigationLink(value: LabRoute.mentor(sessionId: vm.sessionId, orderId: nil)) {
                LabPrimaryLabel(title: "Talk it through with the mentor", icon: "bubble.left.and.text.bubble.right")
            }
            .buttonStyle(EKPressStyle())
            .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
        }
    }
}

private struct LabPerformanceCard: View {
    let perf: LabPerformance

    var body: some View {
        LabCard {
            LabCardTitle(title: "How it went", icon: "chart.bar.doc.horizontal")
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                LabStatTile(label: "Final equity", value: LabFormat.money(perf.finalEquity))
                LabStatTile(label: "Excess vs benchmark", value: LabFormat.pct(perf.excessReturn), tint: LabFormat.tint(perf.excessReturn))
                LabStatTile(label: "Sharpe (ann.)", value: LabFormat.num(perf.sharpe))
                LabStatTile(label: "Hit rate", value: LabFormat.share(perf.hitRate))
                LabStatTile(label: "Turnover", value: "\(LabFormat.num(perf.turnoverX, digits: 1))×")
                LabStatTile(label: "Cost drag", value: LabFormat.pct(perf.costDrag.map { -abs($0) }), tint: Theme.bearRed)
                LabStatTile(label: "Trades", value: "\(perf.trades ?? 0)")
                LabStatTile(label: "Avg hold", value: "\(LabFormat.num(perf.avgHoldDays, digits: 1)) days")
            }
        }
    }
}

private struct LabDebriefCard: View {
    let scenario: LabScenario

    var body: some View {
        LabCard {
            LabCardTitle(title: "Debrief (hindsight)", icon: "eye")
            Text(scenario.debrief ?? "")
                .font(Theme.engravedSerif(size: 13, relativeTo: .body))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(scenario.timeline ?? [], id: \.self) { ev in
                HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                    Text(LabFormat.day(ev.date)).font(Theme.microLabel()).foregroundStyle(Theme.securityGold)
                    Text(ev.event ?? "").font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

struct LabBehaviourCard: View {
    let flags: [LabFlag]

    var body: some View {
        LabCard {
            LabCardTitle(title: "Behaviour patterns", icon: "person.crop.circle.badge.exclamationmark")
            Text("Recurring patterns with the measured evidence behind each. Not a diagnosis.")
                .font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            ForEach(flags, id: \.self) { f in LabFlagRow(flag: f) }
        }
    }
}

private struct LabFlagRow: View {
    let flag: LabFlag

    private var tint: Color {
        switch flag.severityKind {
        case .high: return Theme.bearRed
        case .medium: return Theme.holdAmber
        default: return Theme.inkSecondary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                Text(LabFormat.humanize(flag.id ?? "pattern").capitalized)
                    .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                LabChip(text: flag.severity ?? "—", tint: tint, icon: "gauge.medium")
            }
            Text(flag.text ?? "").font(Theme.engravedSerif(size: 13, relativeTo: .footnote)).foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            ForEach((flag.evidence ?? [:]).keys.sorted(), id: \.self) { k in
                LabKeyValueRow(key: LabFormat.humanize(k), value: flag.evidence?[k]?.display ?? "—")
            }
        }
        .accessibilityElement(children: .combine)
    }
}
