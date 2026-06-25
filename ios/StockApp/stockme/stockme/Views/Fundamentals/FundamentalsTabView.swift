import SwiftUI

struct FundamentalsTabView: View {
    let financials: [FinancialMetrics]
    let shareholding: [Shareholding]
    
    @State private var selectedTab = 0
    
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            // Segmented Control
            HStack(spacing: Theme.Spacing.none) {
                ForEach(["Financials", "Shareholding"].enumerated(), id: \.offset) { idx, title in
                    Button {
    HapticManager.selection()
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
            
            // Tab Content
            if selectedTab == 0 {
                DetailedFinancialsTabView(financials: financials)
                    .transition(.opacity)
            } else {
                ShareholdingTabView(shareholding: shareholding)
                    .transition(.opacity)
            }
        }
    }
}

#Preview {
    FundamentalsTabView(
        financials: MockFundamentals.mockFinancials,
        shareholding: MockFundamentals.mockShareholding
    )
    .padding(.vertical)
    .background(Theme.canvas)
}
