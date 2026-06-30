import SwiftUI

struct FundamentalsTabView: View {
    @ObservedObject var vm: StockProfileViewModel

    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.none) {
                ForEach(["Financials", "Shareholding"].enumerated(), id: \.offset) { idx, title in
                    Button { HapticManager.selection(); 
                        HapticManager.selection()
                        withAnimation {
                            selectedTab = idx
                        }
                    } label: {
                        Text(title.uppercased())
                            .font(Theme.officialStampFont(size: 9))
                            .tracking(1.0)
                            .foregroundStyle(selectedTab == idx ? Theme.inkPrimary : Theme.inkTertiary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.medium)
                            .background(selectedTab == idx ? Theme.canvasDeep : Color.clear)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(Theme.Spacing.small)
            .background(Theme.canvasDeep.opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            .padding(.horizontal, Theme.screenPadding)

            if selectedTab == 0 {
                if vm.financialsLoading {
                    SPSkeletonBlock(rows: 4)
                        .padding(.horizontal, Theme.screenPadding)
                } else if let statement = vm.financialStatement {
                    DetailedFinancialsTabView(financials: mapToFinancialMetrics(statement))
                        .transition(.opacity)
                } else if let err = vm.financialsError {
                    SPEmptyStateView(message: "Financials unavailable: \(err)")
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    SPEmptyStateView(message: "No financial data available")
                        .padding(.horizontal, Theme.screenPadding)
                }
            } else {
                if vm.holdersLoading {
                    SPSkeletonBlock(rows: 4)
                        .padding(.horizontal, Theme.screenPadding)
                } else if let sh = vm.shareholding {
                    ShareholdingTabView(shareholding: mapToShareholding(sh))
                        .transition(.opacity)
                } else if let err = vm.shareholdingError {
                    SPEmptyStateView(message: "Shareholding unavailable: \(err)")
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    SPEmptyStateView(message: "No shareholding data available")
                        .padding(.horizontal, Theme.screenPadding)
                }
            }
        }
        .task { await vm.fetchDetailedFinancials() }
        .task { await vm.fetchShareholding() }
    }

    private func mapToFinancialMetrics(_ response: FinancialStatementResponse) -> [FinancialMetrics] {
        let items = response.lineItems
        let revenueItem = items.first(where: {
            let l = $0.label.lowercased()
            return l.contains("revenue") || l.contains("net sales") || l.contains("total income")
        })
        let profitItem = items.first(where: {
            let l = $0.label.lowercased()
            return l == "pat" || l.contains("net profit") || l.contains("profit after tax")
        })
        let epsItem = items.first(where: {
            let l = $0.label.lowercased()
            return l.hasPrefix("eps") || l.contains("earnings per share")
        })
        let marginItem = items.first(where: {
            let l = $0.label.lowercased()
            return (l.contains("ebitda") || l.contains("operating")) && l.contains("margin")
        })
        let fcfItem = items.first(where: {
            let l = $0.label.lowercased()
            return l.contains("free cash") || l == "fcf"
        })

        return response.periods.map { period in
            let key = period.label
            let revenue = revenueItem?.values[key].map { IndianFormatter.priceCompact($0) }
            let netIncome = profitItem?.values[key].map { IndianFormatter.priceCompact($0) }
            let eps = epsItem?.values[key]
            let margin = marginItem?.values[key]
            let fcf = fcfItem?.values[key].map { IndianFormatter.priceCompact($0) }
            return FinancialMetrics(
                period: key,
                revenue: revenue,
                netIncome: netIncome,
                eps: eps,
                operatingMargin: margin,
                freeCashFlow: fcf
            )
        }
    }

    private func mapToShareholding(_ response: ShareholdingResponse) -> [Shareholding] {
        response.holdingTrend.map { q in
            Shareholding(
                quarter: q.quarter,
                promoterPct: q.promoterPct,
                fiiPct: q.fiiPct,
                diiPct: q.diiPct,
                publicPct: q.publicPct,
                pledgedPct: response.promoterPledgePct
            )
        }
    }
}

#Preview {
    FundamentalsTabView(vm: StockProfileViewModel(ticker: "RELIANCE", exchange: "NSE"))
        .padding(.vertical)
        .background(Theme.canvas)
}
