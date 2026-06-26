import SwiftUI
import Combine
import Foundation

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

    // Detailed financials (new)
    @Published var financialStatement: FinancialStatementResponse?
    @Published var financialsError: String?

    // Shareholding (new)
    @Published var shareholding: ShareholdingResponse?
    @Published var shareholdingError: String?

    // Corporate actions (new)
    @Published var corporateActions: CorporateActionsResponse?
    @Published var corporateActionsLoading = false

    // Valuation (new)
    @Published var valuationData: ValuationResponse?
    @Published var valuationLoading = false
    @Published var valuationError: String?

    // Risk signals (new)
    @Published var riskSignals: RiskSignalsResponse?
    @Published var riskSignalsLoading = false

    // ML Signal
    @Published var mlSignal: MLSignalResponse?
    @Published var mlSignalLoading = false

    // News / Analyst
    @Published var analystRatings: AnalystRatingsResponse?
    @Published var holdersLoading = false

    private let ticker: String
    private let exchange: String

    // MARK: - Known Bank Symbols

    private static let bankSymbols: Set<String> = [
        "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
        "BANKBARODA", "PNB", "CANBK", "INDUSINDBK", "FEDERALBNK",
        "IDFCFIRSTB", "BANDHANBNK", "AUBANK", "RBLBANK", "YESBANK",
        "IDBI", "CUB", "KARURVYSYA", "SOUTHBANK", "MAHABANK",
        "CENTRALBK", "IOB", "UCOBANK", "BANKINDIA", "UNIONBANK",
        "INDIANB", "J&KBANK", "KARNATAKABANK", "DCBBANK", "CSBBANK",
        "DHANBANK", "TMB", "EQUITASBNK", "UJJIVANSFB", "SURYODAY"
    ]

    /// Returns true when the ticker is a known bank symbol.
    var isBank: Bool {
        Self.bankSymbols.contains(ticker.uppercased())
    }

    init(ticker: String, exchange: String) {
        self.ticker = ticker
        self.exchange = exchange
    }

    func fetchOverview() async {
        guard quickInfo?.recentNews == nil else { return }
        await MainActor.run { overviewLoading = true }
        let info = await NetworkManager.shared.quickInfo(ticker: ticker, exchange: exchange)
        await MainActor.run {
            quickInfo = info
            overviewLoading = false
        }
    }

    func fetchChart(period: String = "1y") async {
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

    // MARK: - Detailed Financials

    /// Fetches the full financial statement (P&L, Balance Sheet, Cash Flow) with the given period type and consolidation.
    func fetchDetailedFinancials(periodType: String = "QUARTERLY", consolidation: String = "STANDALONE") async {
        guard financialStatement == nil else { return }
        await MainActor.run {
            financialsLoading = true
            financialsError = nil
        }
        do {
            let result = try await NetworkManager.shared.fetchFinancials(
                symbol: ticker,
                exchange: exchange,
                periodType: periodType,
                consolidation: consolidation
            )
            await MainActor.run {
                financialStatement = result
                financialsLoading = false
            }
        } catch {
            await MainActor.run {
                financialsError = error.localizedDescription
                financialsLoading = false
            }
        }
    }

    // MARK: - Shareholding

    /// Fetches the shareholding pattern including promoter, FII, DII, and public holdings.
    func fetchShareholding() async {
        guard shareholding == nil else { return }
        await MainActor.run {
            holdersLoading = true
            shareholdingError = nil
        }
        do {
            let result = try await NetworkManager.shared.fetchShareholding(
                symbol: ticker,
                exchange: exchange
            )
            await MainActor.run {
                shareholding = result
                holdersLoading = false
            }
        } catch {
            await MainActor.run {
                shareholdingError = error.localizedDescription
                holdersLoading = false
            }
        }
    }

    // MARK: - Corporate Actions

    /// Fetches corporate actions including dividends, splits, bonuses, and buybacks.
    func fetchCorporateActions() async {
        guard corporateActions == nil else { return }
        await MainActor.run {
            corporateActionsLoading = true
        }
        do {
            let result = try await NetworkManager.shared.fetchCorporateActions(
                symbol: ticker,
                exchange: exchange
            )
            await MainActor.run {
                corporateActions = result
                corporateActionsLoading = false
            }
        } catch {
            await MainActor.run {
                corporateActionsLoading = false
            }
        }
    }

    // MARK: - Valuation

    /// Fetches valuation metrics including PE, PB, EV/EBITDA, peer comparison, and PE band history.
    func fetchValuation() async {
        guard valuationData == nil else { return }
        await MainActor.run {
            valuationLoading = true
            valuationError = nil
        }
        do {
            let result = try await NetworkManager.shared.fetchValuation(
                symbol: ticker,
                exchange: exchange
            )
            await MainActor.run {
                valuationData = result
                valuationLoading = false
            }
        } catch {
            await MainActor.run {
                valuationError = error.localizedDescription
                valuationLoading = false
            }
        }
    }

    // MARK: - Risk Signals

    /// Fetches risk signals including governance, pledge, FII trend, and debt concerns.
    func fetchRiskSignals() async {
        guard riskSignals == nil else { return }
        await MainActor.run {
            riskSignalsLoading = true
        }
        do {
            let result = try await NetworkManager.shared.fetchRiskSignals(
                symbol: ticker,
                exchange: exchange
            )
            await MainActor.run {
                riskSignals = result
                riskSignalsLoading = false
            }
        } catch {
            await MainActor.run {
                riskSignalsLoading = false
            }
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
        case "max": return 3650
        default: return 365
        }
    }

    // MARK: - ML Signal

    func fetchMLSignal() async {
        await MainActor.run { mlSignalLoading = true }
        do {
            let result = try await NetworkManager.shared.fetchMLSignal(symbol: ticker)
            await MainActor.run { mlSignal = result }
        } catch {
            // Silently fail — ML signal is supplementary
        }
        await MainActor.run { mlSignalLoading = false }
    }

    func fetchStockProfile() async {
        guard stockProfile == nil else { return }
        await MainActor.run {
            chartLoading = true
            financialsLoading = true
            overviewLoading = true
            mlSignalLoading = true
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
                    peVsAvg: nil,
                    asmGsmStatus: nil,
                    promoterPledgedPct: nil,
                    governanceScore: nil,
                    governanceRedFlags: nil
                )
                if let qf = profile.quarterlyFinancials {
                    quarterlyFinancials = qf.quarters
                    promoterHistory = qf.promoterHistory ?? []
                }
                chartLoading = false
                financialsLoading = false
                overviewLoading = false
            }
            // Fetch ML signal concurrently after profile succeeds
            await fetchMLSignal()
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
