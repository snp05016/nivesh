import SwiftUI
import Charts

struct ShareholdingTabView: View {
    let shareholding: [Shareholding]
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            LazyHStack(spacing: Theme.Spacing.standard) {
                ForEach(shareholding, id: \.quarter) { sh in
                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        Text(sh.quarter)
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(Theme.inkPrimary)
                        
                        GuillocheDivider()
                        
                        // Proportional Bar Comparison using Chart
                        Chart {
                            if let promoter = sh.promoterPct {
                                BarMark(
                                    x: .value("Percent", promoter),
                                    y: .value("Category", "Promoter")
                                )
                                .foregroundStyle(Theme.securityGold)
                            }
                            if let fii = sh.fiiPct {
                                BarMark(
                                    x: .value("Percent", fii),
                                    y: .value("Category", "FII")
                                )
                                .foregroundStyle(Theme.bullGreen)
                            }
                            if let dii = sh.diiPct {
                                BarMark(
                                    x: .value("Percent", dii),
                                    y: .value("Category", "DII")
                                )
                                .foregroundStyle(Theme.holdAmber)
                            }
                            if let pub = sh.publicPct {
                                BarMark(
                                    x: .value("Percent", pub),
                                    y: .value("Category", "Public")
                                )
                                .foregroundStyle(Theme.inkSecondary)
                            }
                        }
                        .chartXAxis(.hidden)
                        .chartYAxis {
                            AxisMarks(position: .leading) { val in
                                AxisValueLabel {
                                    if let str = val.as(String.self) {
                                        Text(str)
                                            .font(Theme.officialStampFont(size: 8))
                                            .foregroundStyle(Theme.inkTertiary)
                                    }
                                }
                            }
                        }
                        .frame(height: 140)
                        
                        if let pledged = sh.pledgedPct {
                            HStack {
                                Text("PLEDGED")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundStyle(Theme.inkTertiary)
                                Spacer()
                                Text("\(String(format: "%.1f", pledged))%")
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundStyle(pledged > 0 ? Theme.bearRed : Theme.bullGreen)
                            }
                            .padding(.top, Theme.Spacing.small)
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
