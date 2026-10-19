import SwiftUI
import Charts

/// Daily candles for one symbol, ending at the session clock (the backend supplies
/// `asof`, so no bar after the simulated date can appear).
struct SimChartView: View {
    let symbol: String
    @StateObject private var vm: LabLoadViewModel<LabHistory>

    init(sessionId: String, symbol: String) {
        self.symbol = symbol
        _vm = StateObject(wrappedValue: LabLoadViewModel(isEmpty: { ($0.bars ?? []).isEmpty }) {
            try await NetworkManager.shared.labHistory(sessionId: sessionId, symbol: symbol, bars: 120)
        })
    }

    var body: some View {
        LabScreen(title: symbol) {
            StateCard(title: "price history", phase: vm.phase,
                      emptyMessage: "No trading history up to the simulated date yet.", onRetry: vm.load) {
                LabCandleCard(symbol: symbol, history: vm.value)
            }
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
    }
}

private struct LabCandleCard: View {
    let symbol: String
    let history: LabHistory?

    private var bars: [LabBar] { history?.bars ?? [] }

    var body: some View {
        LabCard {
            HStack {
                LabCardTitle(title: "Daily candles", icon: "chart.bar.xaxis")
                Spacer()
                Text("as of \(LabFormat.day(history?.asof))").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
            LabCandleChart(bars: bars)
            if let last = bars.last, let first = bars.first {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                    LabStatTile(label: "Last close", value: LabFormat.price(last.c))
                    LabStatTile(label: "Window change", value: LabFormat.pct(first.c > 0 ? last.c / first.c - 1 : nil),
                                tint: LabFormat.tint(last.c - first.c))
                    LabStatTile(label: "Volume", value: LabFormat.qty(last.v))
                }
            }
        }
    }
}

private struct LabCandleChart: View {
    let bars: [LabBar]

    var body: some View {
        Chart {
            ForEach(bars) { b in
                RectangleMark(x: .value("Date", b.date, unit: .day), yStart: .value("Low", b.l), yEnd: .value("High", b.h), width: 1)
                    .foregroundStyle(b.c >= b.o ? Theme.bullGreen : Theme.bearRed)
            }
            ForEach(bars) { b in
                RectangleMark(x: .value("Date", b.date, unit: .day),
                              yStart: .value("Open", min(b.o, b.c)), yEnd: .value("Close", max(b.o, b.c)),
                              width: .fixed(CGFloat(max(2, 280 / max(1, bars.count)))))
                    .foregroundStyle(b.c >= b.o ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .chartYScale(domain: .automatic(includesZero: false))
        .chartYAxisLabel("Price (₹)")
        .chartXAxisLabel("Date")
        .frame(height: UIScreen.main.bounds.height * 0.4)
        .accessibilityLabel("Candlestick chart of \(bars.count) sessions, last close \(LabFormat.price(bars.last?.c))")
    }
}
