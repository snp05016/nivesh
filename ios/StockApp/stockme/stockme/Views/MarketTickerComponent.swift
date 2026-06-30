import SwiftUI

struct MarketTickerComponent: View {
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Spacing.standard) {
                TickerItemView(name: "NIFTY 50", value: "24,500.00", change: "+120.50", isUp: true)
                TickerItemView(name: "SENSEX", value: "80,100.00", change: "-50.20", isUp: false)
                TickerItemView(name: "BANKNIFTY", value: "52,300.00", change: "+300.10", isUp: true)
                TickerItemView(name: "MIDCAP", value: "38,200.00", change: "+45.80", isUp: true)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.standard)
        }
        .background(Theme.canvasDeep)
        .overlay(
            VStack {
                GuillocheDivider()
                Spacer()
                GuillocheDivider()
            }
        )
    }
}

struct TickerItemView: View {
    let name: String
    let value: String
    let change: String
    let isUp: Bool
    
    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(name)
                    .font(.caption.bold())
                    .foregroundColor(Theme.inkSecondary)
                
                Text(value)
                    .font(.subheadline.monospaced())
                    .foregroundColor(Theme.inkPrimary)
            }
            
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Image(systemName: isUp ? "arrow.up.right" : "arrow.down.right")
                    .foregroundColor(isUp ? Theme.bullGreen : Theme.bearRed)
                    .font(.caption2.bold())
                
                Text(change)
                    .font(.caption.monospaced())
                    .foregroundColor(isUp ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.tight)
        .background(Theme.canvas)
        .cornerRadius(Theme.CornerRadius.small)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .stroke(Theme.borderFine, lineWidth: 1)
        )
    }
}

struct MarketTickerComponent_Previews: PreviewProvider {
    static var previews: some View {
        MarketTickerComponent()
    }
}
