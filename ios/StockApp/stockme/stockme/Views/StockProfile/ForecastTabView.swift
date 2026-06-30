import SwiftUI

struct ForecastTabView: View {
    let ticker: String
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Text("ANALYST FORECASTS")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    
                    SPEmptyStateView(message: "Forecast data unavailable")
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
    }
}
