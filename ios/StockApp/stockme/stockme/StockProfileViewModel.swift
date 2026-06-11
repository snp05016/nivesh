import SwiftUI
import Combine

class StockProfileViewModel: ObservableObject {
    // Overview
    @Published var quickInfo: QuickInfo?
    @Published var overviewLoading = false

    // Chart
    @Published var history: StockHistoryResponse?
    @Published var niftyHistory: [NiftyPricePoint] = []
    @Published var chartLoading = false

    // Financials
    @Published var quarterlyFinancials: [QuarterlyFinancial] = []
    @Published var promoterHistory: [PromoterHistoryPoint] = []
    @Published var piotroski: PiotroskiData?
    @Published var financialsLoading = false

    // News / Analyst
    @Published var analystRatings: AnalystRatingsResponse?
    @Published var holdersLoading = false

    private let ticker: String
    private let exchange: String

    init(ticker: String, exchange: String) {
        self.ticker = ticker
        self.exchange = exchange
    }

    func fetchOverview() async {
        guard quickInfo == nil else { return }
        await MainActor.run { overviewLoading = true }
        let info = await NetworkManager.shared.quickInfo(ticker: ticker, exchange: exchange)
        await MainActor.run {
            quickInfo = info
            overviewLoading = false
        }
    }

    func fetchChart(period: String = "1y") async {
        await MainActor.run { chartLoading = true }
        async let hist = NetworkManager.shared.fetchStockHistory(ticker: ticker, exchange: exchange, period: period)
        async let nifty = NetworkManager.shared.getNiftyHistory(days: periodToDays(period))
        let (h, n) = await (hist, nifty)
        await MainActor.run {
            history = h
            niftyHistory = n
            chartLoading = false
        }
    }

    func fetchFinancials() async {
        guard quarterlyFinancials.isEmpty else { return }
        await MainActor.run { financialsLoading = true }
        async let qf = NetworkManager.shared.getQuarterlyFinancialsResponse(ticker: ticker, exchange: exchange)
        async let pf = NetworkManager.shared.fetchPiotroski(ticker: ticker)
        let (q, p) = await (qf, pf)
        await MainActor.run {
            quarterlyFinancials = q?.quarters ?? []
            promoterHistory = q?.promoterHistory ?? []
            piotroski = p
            financialsLoading = false
        }
    }

    func fetchHolders() async {
        guard analystRatings == nil else { return }
        await MainActor.run { holdersLoading = true }
        let ratings = await NetworkManager.shared.getAnalystRatings(ticker: ticker, exchange: exchange)
        await MainActor.run {
            analystRatings = ratings
            holdersLoading = false
        }
    }

    private func periodToDays(_ period: String) -> Int {
        switch period {
        case "1mo": return 30
        case "3mo": return 90
        case "6mo": return 180
        case "2y": return 730
        case "5y": return 1825
        default: return 365
        }
    }
}
