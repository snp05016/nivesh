import SwiftUI
import Combine
import Charts

struct BacktestTrade: Decodable, Identifiable {
    let id = UUID()
    let entryDate: String
    let exitDate: String
    let entryPrice: Double
    let exitPrice: Double
    let returnPct: Double
    let holdingDays: Int
    
    enum CodingKeys: String, CodingKey {
        case entryDate = "entry_date"
        case exitDate = "exit_date"
        case entryPrice = "entry_price"
        case exitPrice = "exit_price"
        case returnPct = "return_pct"
        case holdingDays = "holding_days"
    }
}

struct EquityCurvePoint: Decodable, Identifiable {
    let id = UUID()
    let date: String
    let portfolioValue: Double
    let benchmarkValue: Double
    
    enum CodingKeys: String, CodingKey {
        case date
        case portfolioValue = "portfolio_value"
        case benchmarkValue = "benchmark_value"
    }
    
    var parsedDate: Date {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: date) ?? Date()
    }
}

struct StrategyBacktestResult: Decodable {
    let cagr: Double
    let sharpeRatio: Double
    let maxDrawdown: Double
    let winRate: Double
    let outperformance: Double
    let trades: [BacktestTrade]
    let equityCurve: [EquityCurvePoint]
    
    enum CodingKeys: String, CodingKey {
        case cagr
        case sharpeRatio = "sharpe_ratio"
        case maxDrawdown = "max_drawdown"
        case winRate = "win_rate"
        case outperformance
        case trades
        case equityCurve = "equity_curve"
    }
}

struct StrategyOption: Identifiable, Equatable {
    let id: String
    let name: String
    let icon: String
}

let STRATEGY_OPTIONS: [StrategyOption] = [
    StrategyOption(id: "rsi_oversold", name: "RSI Oversold", icon: "waveform.path.ecg"),
    StrategyOption(id: "golden_cross", name: "Golden Cross", icon: "point.topleft.down.curvedto.point.bottomright.up"),
    StrategyOption(id: "low_pe_promoter", name: "Low PE + Promoter", icon: "person.2.badge.gearshape"),
    StrategyOption(id: "momentum_roc", name: "Momentum ROC", icon: "chart.line.uptrend.xyaxis"),
    StrategyOption(id: "bollinger_reversion", name: "Bollinger Reversion", icon: "arrow.up.and.down.and.sparkles"),
    StrategyOption(id: "volume_breakout", name: "Volume Breakout", icon: "chart.bar.xaxis"),
    StrategyOption(id: "macd_signal", name: "MACD Signal", icon: "lines.measurement.horizontal"),
    StrategyOption(id: "buy_and_hold", name: "Buy & Hold", icon: "archivebox"),
    StrategyOption(id: "dividend_capture", name: "Dividend Capture", icon: "indianrupeesign.circle"),
    StrategyOption(id: "low_volatility", name: "Low Volatility", icon: "shield")
]

@MainActor
class StrategyLabViewModel: ObservableObject {
    @Published var selectedTicker: String
    @Published var selectedStrategy: StrategyOption = STRATEGY_OPTIONS[0]
    @Published var selectedYears: Int = 5
    
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var result: StrategyBacktestResult? = nil
    
    @Published var compareResult: StrategyBacktestResult? = nil
    @Published var compareStrategy: StrategyOption? = nil
    @Published var isComparing: Bool = false
    
    init() {
        self.selectedTicker = StockDatabase.all.first?.ticker ?? "RELIANCE"
    }
    
    func runBacktest() async {
        isLoading = true
        errorMessage = nil
        result = nil
        
        do {
            result = try await fetchBacktest(ticker: selectedTicker, strategyId: selectedStrategy.id, years: selectedYears)
            
            if isComparing, let compareStrategy = compareStrategy {
                compareResult = try await fetchBacktest(ticker: selectedTicker, strategyId: compareStrategy.id, years: selectedYears)
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func runCompareBacktest(with strategy: StrategyOption) async {
        compareStrategy = strategy
        isComparing = true
        isLoading = true
        errorMessage = nil
        
        do {
            compareResult = try await fetchBacktest(ticker: selectedTicker, strategyId: strategy.id, years: selectedYears)
            if result == nil {
                result = try await fetchBacktest(ticker: selectedTicker, strategyId: selectedStrategy.id, years: selectedYears)
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func stopCompare() {
        isComparing = false
        compareStrategy = nil
        compareResult = nil
    }
    
    private func fetchBacktest(ticker: String, strategyId: String, years: Int) async throws -> StrategyBacktestResult {
        guard let url = URL(string: "http://127.0.0.1:8000/api/v1/analysis/backtest") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "ticker": ticker,
            "strategy_id": strategyId,
            "years": years
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            struct ErrorResponse: Decodable { let detail: String }
            if let errorMsg = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw NSError(domain: "BacktestError", code: 1, userInfo: [NSLocalizedDescriptionKey: errorMsg.detail])
            }
            throw URLError(.badServerResponse)
        }
        
        return try JSONDecoder().decode(StrategyBacktestResult.self, from: data)
    }
}

struct StrategyLabScreen: View {
    @StateObject private var viewModel = StrategyLabViewModel()
    @State private var showingCompareSheet = false
    @State private var showingTradeLog = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                settingsSection
                
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                
                if viewModel.isLoading {
                    VStack(spacing: Theme.Spacing.medium) {
                        ProgressView()
                            .tint(Theme.goldPrimary)
                        Text("Running Backtest...")
                            .font(Theme.engravedSerif(size: 14))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 50)
                } else if let error = viewModel.errorMessage {
                    VStack(spacing: Theme.Spacing.medium) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(Theme.engravedSerif(size: 24))
                            .foregroundStyle(Theme.bearRed)
                        Text("API Unavailable or Insufficient Data")
                            .font(Theme.engravedSerif(size: 16, weight: .bold))
                            .foregroundStyle(Theme.bearRed)
                        Text(error)
                            .font(Theme.roundedCaption(size: 12))
                            .foregroundStyle(Theme.inkSecondary)
                            .multilineTextAlignment(.center)
                        Button(action: { HapticManager.selection(); Task { await viewModel.runBacktest() } }) {
                            Text("Retry")
                                .font(Theme.roundedSecondary(size: 14, weight: .bold))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(.horizontal, 24)
                                .padding(.vertical, 8)
                                .background(Theme.surfaceElevated)
                                .clipShape(Capsule())
                                .overlay(Capsule().stroke(Theme.borderSage, lineWidth: 1))
                        }
                        .ekPress()
                    }
                    .padding()
                    .frame(maxWidth: .infinity)
                    .banknoteCard()
                    .padding(.horizontal, Theme.screenPadding)
                } else if let result = viewModel.result {
                    resultsSection(result)
                    
                    chartSection(result)
                    
                    if viewModel.isComparing {
                        Button(action: { HapticManager.selection();  HapticManager.selection()
                            HapticManager.selection()
                            viewModel.stopCompare()
                        }) {
                            Text("Stop Comparison")
                                .font(Theme.roundedSecondary(size: 14, weight: .bold))
                                .foregroundStyle(Theme.bearRed)
                                .padding()
                                .frame(maxWidth: .infinity)
                                .background(Theme.surfaceElevated)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSage, lineWidth: 1))
                        }
                        .ekPress()
                        .padding(.horizontal, Theme.screenPadding)
                    } else {
                        Button(action: { HapticManager.selection();  HapticManager.selection()
                            HapticManager.selection()
                            showingCompareSheet = true
                        }) {
                            Text("Compare with another strategy")
                                .font(Theme.roundedSecondary(size: 14, weight: .bold))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding()
                                .frame(maxWidth: .infinity)
                                .background(Theme.surfaceElevated)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSage, lineWidth: 1))
                        }
                        .ekPress()
                        .padding(.horizontal, Theme.screenPadding)
                    }
                    
                    tradeLogSection(result)
                } else {
                    VStack {
                        Image(systemName: "flask")
                            .font(Theme.engravedSerif(size: 32))
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(.bottom, 8)
                        Text("Select a strategy to begin")
                            .font(Theme.engravedSerif(size: 16))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    .padding(.top, 50)
                }
            }
            .padding(.vertical, Theme.Spacing.screen)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .onChange(of: viewModel.selectedTicker) { _ in Task { await viewModel.runBacktest() } }
        .onChange(of: viewModel.selectedStrategy) { _ in Task { await viewModel.runBacktest() } }
        .onChange(of: viewModel.selectedYears) { _ in Task { await viewModel.runBacktest() } }
        .sheet(isPresented: $showingCompareSheet) {
            NavigationStack {
                List(STRATEGY_OPTIONS) { strategy in
                    Button(action: { HapticManager.selection();  HapticManager.selection()
                        showingCompareSheet = false
                        Task { await viewModel.runCompareBacktest(with: strategy) }
                    }) {
                        HStack(spacing: Theme.Spacing.standard) {
                            Image(systemName: strategy.icon)
                                .foregroundStyle(Theme.goldPrimary)
                                .frame(width: 24)
                            Text(strategy.name)
                                .font(Theme.engravedSerif(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                    }
                    .listRowBackground(Theme.canvasDeep)
                }
                .scrollContentBackground(.hidden)
                .background(Theme.canvas)
                .navigationTitle("Compare Strategy")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { showingCompareSheet = false }.buttonStyle(EKPressStyle())
                            .foregroundStyle(Theme.goldPrimary)
                    }
                }
            }
            .presentationDetents([.medium, .large])
        }
        .task {
            if viewModel.result == nil && !viewModel.isLoading {
                await viewModel.runBacktest()
            }
        }
    }
    
    private var settingsSection: some View {
        VStack(spacing: Theme.Spacing.card) {
            // Stock picker
            HStack {
                Text("Stock")
                    .font(Theme.officialStampFont(size: 12))
                    .foregroundStyle(Theme.inkSecondary)
                Spacer()
                Picker("Stock", selection: $viewModel.selectedTicker) {
                    ForEach(StockDatabase.all.prefix(100)) { stock in
                        Text(stock.ticker).tag(stock.ticker)
                    }
                }
                .tint(Theme.goldPrimary)
            }
            .padding(.horizontal, Theme.screenPadding)
            
            // Date range
            HStack(spacing: Theme.Spacing.standard) {
                ForEach([1, 3, 5, 10], id: \.self) { years in
                    let label = years == 10 ? "ALL" : "\(years)Y"
                    Button(action: { HapticManager.selection();  HapticManager.selection()
                        HapticManager.selection()
                        viewModel.selectedYears = years
                    }) {
                        Text(label)
                            .font(Theme.serialNumberFont(size: 12))
                            .foregroundStyle(viewModel.selectedYears == years ? Theme.canvas : Theme.inkSecondary)
                            .padding(.horizontal, Theme.Spacing.standard)
                            .padding(.vertical, Theme.Spacing.small)
                            .background(viewModel.selectedYears == years ? Theme.securityGold : Theme.canvasDeep)
                            .clipShape(Capsule())
                            .overlay(Capsule().stroke(viewModel.selectedYears == years ? Theme.securityGold : Theme.borderSage, lineWidth: 0.5))
                    }
                    .ekPress()
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, Theme.screenPadding)
            
            // Strategy picker
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    ForEach(STRATEGY_OPTIONS) { strategy in
                        Button(action: { HapticManager.selection();  HapticManager.selection()
                            HapticManager.selection()
                            viewModel.selectedStrategy = strategy
                        }) {
                            HStack(spacing: Theme.Spacing.small) {
                                Image(systemName: strategy.icon)
                                    .font(.caption)
                                Text(strategy.name)
                                    .font(Theme.engravedSerif(size: 14))
                            }
                            .foregroundStyle(viewModel.selectedStrategy == strategy ? Theme.canvas : Theme.inkPrimary)
                            .padding(.horizontal, Theme.Spacing.card)
                            .padding(.vertical, Theme.Spacing.medium)
                            .background(viewModel.selectedStrategy == strategy ? Theme.securityGold : Theme.canvasDeep)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(viewModel.selectedStrategy == strategy ? Theme.securityGold : Theme.borderSage, lineWidth: 0.5))
                        }
                        .ekPress()
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
    
    private func resultsSection(_ result: StrategyBacktestResult) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            let isPositive = result.cagr >= 0
            let cagrColor = isPositive ? Theme.bullGreen : Theme.bearRed
            let cagrSign = isPositive ? "+" : ""
            
            HStack(alignment: .lastTextBaseline, spacing: Theme.Spacing.xSmall) {
                Text("\(cagrSign)\(String(format: "%.1f", result.cagr))%")
                    .font(Theme.dataLarge(size: 32))
                    .foregroundStyle(cagrColor)
                Text("CAGR")
                    .font(Theme.officialStampFont(size: 12))
                    .foregroundStyle(Theme.inkSecondary)
            }
            
            HStack(spacing: Theme.Spacing.large) {
                metricView(title: "SHARPE", value: String(format: "%.2f", result.sharpeRatio), color: Theme.securityGold)
                metricView(title: "MAX DD", value: "\(String(format: "%.1f", result.maxDrawdown))%", color: Theme.bearRed)
                metricView(title: "WIN RATE", value: "\(String(format: "%.1f", result.winRate))%", color: Theme.inkPrimary)
            }
            .padding(.top, Theme.Spacing.small)
            
            let outPerfColor = result.outperformance >= 0 ? Theme.bullGreen : Theme.bearRed
            let outPerfSign = result.outperformance >= 0 ? "+" : ""
            Text("vs Buy & Hold: \(outPerfSign)\(String(format: "%.1f", result.outperformance))% outperformance")
                .font(Theme.roundedCaption(size: 12))
                .foregroundStyle(outPerfColor)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.small)
                .background(outPerfColor.opacity(0.1))
                .clipShape(Capsule())
                .padding(.top, Theme.Spacing.small)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
    
    private func metricView(title: String, value: String, color: Color) -> some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(title)
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.inkSecondary)
            Text(value)
                .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                .foregroundStyle(color)
        }
    }
    
    private func chartSection(_ result: StrategyBacktestResult) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("EQUITY CURVE")
                .font(Theme.sectionCapsLabel())
                .tracking(1.2)
                .foregroundStyle(Theme.inkPrimary)
            
            Chart {
                ForEach(result.equityCurve) { point in
                    LineMark(
                        x: .value("Date", point.parsedDate),
                        y: .value("Benchmark", point.benchmarkValue)
                    )
                    .foregroundStyle(Theme.inkTertiary)
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 5]))
                    
                    LineMark(
                        x: .value("Date", point.parsedDate),
                        y: .value("Strategy", point.portfolioValue)
                    )
                    .foregroundStyle(Theme.avatarBlue)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    
                    if point.portfolioValue > point.benchmarkValue {
                        AreaMark(
                            x: .value("Date", point.parsedDate),
                            yStart: .value("Benchmark", point.benchmarkValue),
                            yEnd: .value("Strategy", point.portfolioValue)
                        )
                        .foregroundStyle(LinearGradient(colors: [Theme.avatarBlue.opacity(0.3), Theme.avatarBlue.opacity(0.0)], startPoint: .top, endPoint: .bottom))
                    }
                }
                
                if let compare = viewModel.compareResult {
                    ForEach(compare.equityCurve) { point in
                        LineMark(
                            x: .value("Date", point.parsedDate),
                            y: .value("Compare Strategy", point.portfolioValue)
                        )
                        .foregroundStyle(Theme.securityGold)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                    }
                }
            }
            .chartYScale(domain: .automatic(includesZero: false))
            .chartXAxis {
                AxisMarks(values: .stride(by: .year)) { _ in
                    AxisValueLabel(format: .dateTime.year())
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
            .frame(height: 250)
            
            HStack(spacing: Theme.Spacing.large) {
                legendItem(name: viewModel.selectedStrategy.name, color: Theme.avatarBlue, dashed: false)
                if let compare = viewModel.compareStrategy {
                    legendItem(name: compare.name, color: Theme.securityGold, dashed: false)
                } else {
                    legendItem(name: "Buy & Hold", color: Theme.inkTertiary, dashed: true)
                }
            }
            .font(Theme.roundedCaption(size: 11))
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
    
    private func legendItem(name: String, color: Color, dashed: Bool) -> some View {
        HStack(spacing: Theme.Spacing.tight) {
            if dashed {
                Rectangle()
                    .fill(Color.clear)
                    .frame(width: 12, height: 2)
                    .overlay(
                        Rectangle()
                            .stroke(color, style: StrokeStyle(lineWidth: 2, dash: [3, 2]))
                    )
            } else {
                Rectangle()
                    .fill(color)
                    .frame(width: 12, height: 2)
            }
            Text(name)
                .foregroundStyle(Theme.inkSecondary)
        }
    }
    
    private func tradeLogSection(_ result: StrategyBacktestResult) -> some View {
        VStack(spacing: Theme.Spacing.none) {
            Button(action: { HapticManager.selection();  HapticManager.selection()
                HapticManager.selection()
                withAnimation { showingTradeLog.toggle() }
            }) {
                HStack {
                    Text("TRADE LOG (\(result.trades.count))")
                        .font(Theme.sectionCapsLabel())
                        .tracking(1.2)
                        .foregroundStyle(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: showingTradeLog ? "chevron.up" : "chevron.down")
                        .foregroundStyle(Theme.inkSecondary)
                }
                .padding(Theme.Spacing.card)
                .background(Theme.canvasDeep)
            }
            .ekPress()
            
            if showingTradeLog {
                if result.trades.isEmpty {
                    Text("No trades executed.")
                        .font(Theme.engravedSerif(size: 14))
                        .foregroundStyle(Theme.inkSecondary)
                        .padding()
                } else {
                    VStack(spacing: Theme.Spacing.none) {
                        ForEach(result.trades) { trade in
                            let isProfit = trade.returnPct >= 0
                            let color = isProfit ? Theme.bullGreen : Theme.bearRed
                            let sign = isProfit ? "+" : ""
                            
                            HStack {
                                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                    Text("\(trade.entryDate) → \(trade.exitDate)")
                                        .font(Theme.monoTabular(size: 12))
                                        .foregroundStyle(Theme.inkSecondary)
                                    Text("₹\(IndianFormatter.priceWithoutSymbol(trade.entryPrice)) → ₹\(IndianFormatter.priceWithoutSymbol(trade.exitPrice))")
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkPrimary)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: Theme.Spacing.tight) {
                                    Text("\(sign)\(String(format: "%.2f", trade.returnPct))%")
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(color)
                                    Text("\(trade.holdingDays) days")
                                        .font(Theme.monoTabular(size: 12))
                                        .foregroundStyle(Theme.inkTertiary)
                                }
                            }
                            .padding(Theme.Spacing.card)
                            
                            if trade.id != result.trades.last?.id {
                                GuillocheDivider()
                            }
                        }
                    }
                }
            }
        }
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}
