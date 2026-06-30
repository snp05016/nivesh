import SwiftUI

struct HomeDashboardView: View {
    @StateObject private var viewModel = HomeDashboardViewModel()
    
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: Theme.Spacing.xLarge) {
                        MarketTickerComponent()
                        
                        UniversalSearchView()
                        
                        VStack(spacing: Theme.Spacing.standard) {
                            HStack {
                                Text("Market Pulse")
                                    .font(.headline)
                                    .fontDesign(.serif)
                                    .foregroundColor(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            
                            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                                HStack {
                                    Text("PORTFOLIO VALUE")
                                        .font(.caption.bold())
                                        .foregroundColor(Theme.inkSecondary)
                                    Spacer()
                                    Image(systemName: "lock.shield")
                                        .foregroundColor(Theme.securityGold)
                                }
                                
                                Text(viewModel.portfolioSummary)
                                    .font(.title2.monospaced())
                                    .foregroundColor(Theme.inkPrimary)
                                
                                GuillocheDivider()
                                
                                HStack {
                                    Text("Day's Gain")
                                        .font(.subheadline)
                                        .fontDesign(.serif)
                                        .foregroundColor(Theme.inkSecondary)
                                    Spacer()
                                    Text(viewModel.daysGain)
                                        .font(.subheadline.monospaced())
                                        .foregroundColor(viewModel.daysGain.hasPrefix("-") ? Theme.bearRed : Theme.bullGreen)
                                }
                            }
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)
                        }
                    }
                    .padding(.vertical, Theme.Spacing.standard)
                }
            }
            .navigationTitle("Nivesh")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct HomeDashboardView_Previews: PreviewProvider {
    static var previews: some View {
        HomeDashboardView()
    }
}
