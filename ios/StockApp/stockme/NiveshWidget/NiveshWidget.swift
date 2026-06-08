import WidgetKit
import SwiftUI

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> SimpleEntry {
        SimpleEntry(date: Date(), portfolioValue: 1250400.0, pnL: 45000.0, niftyValue: 22450.5, niftyChange: 120.5, topHoldings: [
            HoldingEntry(ticker: "RELIANCE", value: 350000, pnl: 15000, isUp: true),
            HoldingEntry(ticker: "TCS", value: 280000, pnl: -4000, isUp: false),
            HoldingEntry(ticker: "HDFCBANK", value: 210000, pnl: 8000, isUp: true)
        ])
    }

    func getSnapshot(in context: Context, completion: @escaping (SimpleEntry) -> ()) {
        let entry = SimpleEntry(date: Date(), portfolioValue: 1250400.0, pnL: 45000.0, niftyValue: 22450.5, niftyChange: 120.5, topHoldings: [
            HoldingEntry(ticker: "RELIANCE", value: 350000, pnl: 15000, isUp: true),
            HoldingEntry(ticker: "TCS", value: 280000, pnl: -4000, isUp: false),
            HoldingEntry(ticker: "HDFCBANK", value: 210000, pnl: 8000, isUp: true)
        ])
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> ()) {
        var entries: [SimpleEntry] = []
        let currentDate = Date()
        for hourOffset in 0 ..< 5 {
            let entryDate = Calendar.current.date(byAdding: .hour, value: hourOffset, to: currentDate)!
            let entry = SimpleEntry(date: entryDate, portfolioValue: 1250400.0, pnL: 45000.0, niftyValue: 22450.5, niftyChange: 120.5, topHoldings: [
                HoldingEntry(ticker: "RELIANCE", value: 350000, pnl: 15000, isUp: true),
                HoldingEntry(ticker: "TCS", value: 280000, pnl: -4000, isUp: false),
                HoldingEntry(ticker: "HDFCBANK", value: 210000, pnl: 8000, isUp: true)
            ])
            entries.append(entry)
        }

        let timeline = Timeline(entries: entries, policy: .atEnd)
        completion(timeline)
    }
}

struct HoldingEntry: Identifiable {
    let id = UUID()
    let ticker: String
    let value: Double
    let pnl: Double
    let isUp: Bool
}

struct SimpleEntry: TimelineEntry {
    let date: Date
    let portfolioValue: Double
    let pnL: Double
    let niftyValue: Double
    let niftyChange: Double
    let topHoldings: [HoldingEntry]
}

struct NiveshWidgetEntryView : View {
    var entry: Provider.Entry
    @Environment(\.widgetFamily) var family

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            
            VStack(spacing: 0) {
                switch family {
                case .systemSmall:
                    smallWidget
                case .systemMedium:
                    mediumWidget
                default:
                    smallWidget
                }
            }
            .padding(Theme.Spacing.card)
        }
    }
    
    var smallWidget: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("P&L")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
            
            Text(IndianFormatter.price(entry.pnL))
                .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                .foregroundColor(entry.pnL >= 0 ? Theme.bullGreen : Theme.bearRed)
            
            Spacer(minLength: Theme.Spacing.standard)
            
            Text("NIFTY 50")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
            
            Text(IndianFormatter.price(entry.niftyValue))
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
                
            Text(entry.niftyChange >= 0 ? "+\(IndianFormatter.price(entry.niftyChange))" : IndianFormatter.price(entry.niftyChange))
                .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                .foregroundColor(entry.niftyChange >= 0 ? Theme.bullGreen : Theme.bearRed)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
    
    var mediumWidget: some View {
        HStack(spacing: Theme.Spacing.large) {
            smallWidget
            
            
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("TOP HOLDINGS")
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkSecondary)
                
                ForEach(entry.topHoldings.prefix(3)) { holding in
                    HStack {
                        Text(holding.ticker)
                            .font(Theme.engravedSerif(size: 12, weight: .bold, relativeTo: .caption))
                            .foregroundColor(Theme.inkPrimary)
                            .lineLimit(1)
                        
                        Spacer()
                        
                        Text(IndianFormatter.price(holding.pnl))
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundColor(holding.isUp ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

@main
struct NiveshWidget: Widget {
    let kind: String = "NiveshWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            if #available(iOS 17.0, *) {
                NiveshWidgetEntryView(entry: entry)
                    .containerBackground(Theme.canvasDeep, for: .widget)
            } else {
                NiveshWidgetEntryView(entry: entry)
                    .background(Theme.canvasDeep)
            }
        }
        .configurationDisplayName("Nivesh Portfolio")
        .description("Track your portfolio P&L and market indices.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
