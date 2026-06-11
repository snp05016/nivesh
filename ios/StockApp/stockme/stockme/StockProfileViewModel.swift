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
    @Published var chartError: String? = nil

    // Unified stock profile
    @Published var stockProfile: StockProfileResponse?
    @Published var stockProfileError: String?

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
        guard history == nil else { return }
        await MainActor.run {
            chartLoading = true
            chartError = nil
        }
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

    func fetchStockProfile() async {
        guard stockProfile == nil else { return }
        await MainActor.run {
            chartLoading = true
            financialsLoading = true
            overviewLoading = true
            stockProfileError = nil
        }
        do {
            let profile = try await NetworkManager.shared.fetchStockProfile(ticker: ticker, exchange: exchange)
            await MainActor.run {
                stockProfile = profile
                if let ph = profile.priceHistory, !ph.prices.isEmpty {
                    history = StockHistoryResponse(
                        ticker: profile.ticker,
                        exchange: profile.exchange,
                        period: "1y",
                        prices: ph.prices
                    )
                }
                quickInfo = QuickInfo(
                    ticker: profile.ticker,
                    price: profile.currentPrice,
                    change: nil,
                    changePercent: profile.dayChangePct,
                    signal: nil,
                    sector: profile.sector,
                    industry: nil,
                    description: profile.description,
                    officers: nil,
                    website: nil,
                    recentNews: nil,
                    sparkline30d: nil,
                    week52High: profile.week52High,
                    week52Low: profile.week52Low,
                    peRatio: profile.peRatio,
                    debtToEquity: profile.debtToEquity,
                    promoterHoldingPct: profile.promoterHoldingPct,
                    fiiHoldingPct: profile.fiiHoldingPct,
                    diiHoldingPct: profile.diiHoldingPct,
                    ebitdaMarginPct: profile.ebitdaMarginPct,
                    roePct: profile.roePct,
                    rocePct: profile.rocePct,
                    volume: nil,
                    avgVolume: nil,
                    priceHistory90d: nil,
                    peVsAvg: nil
                )
                if let qf = profile.quarterlyFinancials {
                    quarterlyFinancials = qf.quarters
                    promoterHistory = qf.promoterHistory ?? []
                }
                chartLoading = false
                financialsLoading = false
                overviewLoading = false
            }
        } catch {
            await MainActor.run {
                stockProfileError = error.localizedDescription
                chartLoading = false
                financialsLoading = false
                overviewLoading = false
            }
        }
    }
}
