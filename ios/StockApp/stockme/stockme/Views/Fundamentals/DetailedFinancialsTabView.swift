import SwiftUI

struct DetailedFinancialsTabView: View {
    let financials: [FinancialMetrics]
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            LazyHStack(spacing: Theme.Spacing.standard) {
                ForEach(financials, id: \.period) { fin in
                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        Text(fin.period)
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(Theme.inkPrimary)
                        
                        GuillocheDivider()
                        
                        HStack {
                            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                Text("REVENUE").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                                Text(fin.revenue ?? "—")
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                                Text("NET INCOME").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                                Text(fin.netIncome ?? "—")
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                        }
                        
                        HStack {
                            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                Text("EPS").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                                if let eps = fin.eps {
                                    Text(IndianFormatter.price(eps))
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkPrimary)
                                } else {
                                    Text("—")
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkPrimary)
                                }
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                                Text("OP. MARGIN").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                                if let margin = fin.operatingMargin {
                                    Text("\(String(format: "%.1f", margin))%")
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkPrimary)
                                } else {
                                    Text("—")
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkPrimary)
                                }
                            }
                        }
                        
                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text("FREE CASH FLOW").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                            Text(fin.freeCashFlow ?? "—")
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                    }
                    .padding(Theme.Spacing.card)
                    .frame(width: UIScreen.main.bounds.width * 0.75)
                    .banknoteCard()
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

#Preview {
    DetailedFinancialsTabView(financials: MockFundamentals.mockFinancials)
        .padding(.vertical)
        .background(Theme.canvasDeep)
}
