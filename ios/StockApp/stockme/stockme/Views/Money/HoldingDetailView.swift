import SwiftUI

/// "My position" (C11, spec 3.2): pushed from the portfolio list instead of auto-running a
/// paid analysis. Shows the list row as a seed while loading or offline; every other section
/// renders only with data. Pushed inside PortfolioScreen's NavigationStack (no stack of its own).
struct HoldingDetailView: View {
    let ticker: String
    let seed: PortfolioHolding?
    /// The portfolio screen's model, so a recorded trade also refreshes the list.
    var portfolio: PortfolioScreenViewModel? = nil

    @EnvironmentObject private var authManager: AuthManager
    @StateObject private var model: HoldingDetailViewModel
    @AppStorage("nivesh_hidePortfolioValues") private var hideValues = false
    @State private var showAlertSheet = false
    @State private var showTradeSheet = false

    init(ticker: String, seed: PortfolioHolding?, portfolio: PortfolioScreenViewModel? = nil) {
        self.ticker = ticker
        self.seed = seed
        self.portfolio = portfolio
        _model = StateObject(wrappedValue: HoldingDetailViewModel(ticker: ticker))
    }

    private var name: String {
        if let n = model.detail?.name, !n.isEmpty { return n }
        if let n = seed?.stock.companyName, !n.isEmpty { return n }
        return ticker
    }

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                if model.state == .notHeld {
                    Text("This holding is no longer in your portfolio.")
                        .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                        .padding(.top, Theme.Spacing.xLarge)
                } else {
                    if model.state == .offline {
                        HoldingStatusBanner(text: "You're offline. Showing your last loaded values.")
                    }
                    if let d = model.detail {
                        HoldingPositionCard(position: d.position, notes: d.notes, targetPrice: d.targetPrice, hideValues: hideValues)
                        if let copy = MoneyReturnCopy.holding(d.returns, masked: hideValues) {
                            HoldingReturnCard(copy: copy)
                        }
                        if d.isEquity {
                            HoldingActionsBar(ticker: d.ticker, showReport: d.stockReportAvailable,
                                              onAlert: { showAlertSheet = true }, onTrade: { showTradeSheet = true })
                        }
                        if !d.transactions.isEmpty {
                            HoldingTransactionsCard(transactions: d.transactions, hideValues: hideValues)
                        }
                        if let div = d.dividends, div.count > 0 {
                            HoldingDividendsRow(dividends: div, hideValues: hideValues)
                        }
                        if !d.journal.isEmpty {
                            HoldingJournalCard(entries: d.journal)
                        }
                    } else if case .failed(let message) = model.state {
                        BanknoteErrorCanvas(title: "Couldn't load this holding.", detail: message,
                                            retryAction: { await model.load() })
                    } else {
                        if let seed {
                            HoldingPositionCard(position: HoldingPosition(seed: seed), notes: seed.notes,
                                                targetPrice: seed.targetPrice, hideValues: hideValues)
                        }
                        if model.state == .loading {
                            ProgressView().tint(Theme.securityGold).padding(.top, Theme.Spacing.standard)
                        }
                    }
                }
                Spacer(minLength: Theme.Spacing.sectionBreath)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle(name)
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.load() }
        .refreshable { await model.load() }
        .sheet(isPresented: $showAlertSheet) {
            AddAlertSheet(authManager: authManager, onAdded: {}, prefilledTicker: ticker, prefilledCompany: name)
        }
        .sheet(isPresented: $showTradeSheet) {
            AddHoldingSheet(viewModel: portfolio ?? PortfolioScreenViewModel(), authManager: authManager,
                            prefilledEntry: StockDatabase.search(ticker).first { $0.ticker == ticker }
                                ?? StockEntry(ticker: ticker, companyName: name, exchange: "NSE", sector: ""),
                            onSaved: { Task { await model.load() } })
        }
    }
}
