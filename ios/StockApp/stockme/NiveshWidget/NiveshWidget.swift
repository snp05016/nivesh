import WidgetKit
import SwiftUI

struct Provider: TimelineProvider {
    /// App Group shared with the app. Keys mirror WidgetSnapshotStore in the app target.
    static let suite = "group.saumypatel.stockme"

    func placeholder(in context: Context) -> SimpleEntry {
        placeholderEntry()
    }

    func getSnapshot(in context: Context, completion: @escaping (SimpleEntry) -> ()) {
        completion(loadEntry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> ()) {
        let now = Date()
        completion(Timeline(entries: [loadEntry()], policy: .after(now.addingTimeInterval(30 * 60))))
    }

    /// Reads the snapshot the app wrote after its last portfolio load.
    /// No snapshot (fresh install, logged out) yields nil values, never demo numbers.
    func loadEntry() -> SimpleEntry {
        guard let defaults = UserDefaults(suiteName: Self.suite),
              let updated = defaults.object(forKey: "w_updated_at") as? Double else {
            return placeholderEntry()
        }
        var top: [HoldingEntry] = []
        if let data = defaults.data(forKey: "w_top"),
           let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] {
            top = rows.compactMap { row in
                guard let ticker = row["ticker"] as? String, let pnl = row["pnl"] as? Double else { return nil }
                return HoldingEntry(ticker: ticker, pnl: pnl)
            }
        }
        return SimpleEntry(
            date: Date(),
            portfolioValue: defaults.double(forKey: "w_portfolio_value"),
            pnL: defaults.double(forKey: "w_pnl"),
            updatedAt: Date(timeIntervalSince1970: updated),
            topHoldings: top
        )
    }

    private func placeholderEntry() -> SimpleEntry {
        SimpleEntry(date: Date(), portfolioValue: nil, pnL: nil, updatedAt: nil, topHoldings: [])
    }
}

struct HoldingEntry: Identifiable {
    let id = UUID()
    let ticker: String
    let pnl: Double
}

struct SimpleEntry: TimelineEntry {
    let date: Date
    let portfolioValue: Double?
    let pnL: Double?
    let updatedAt: Date?
    let topHoldings: [HoldingEntry]
}

struct NiveshWidgetEntryView : View {
    var entry: Provider.Entry
    @Environment(\.widgetFamily) var family

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            
            VStack(spacing: Theme.Spacing.none) {
                if entry.portfolioValue == nil {
                    Text("Open Nivesh to sync")
                        .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                } else {
                    switch family {
                    case .systemMedium:
                        mediumWidget
                    default:
                        smallWidget
                    }
                }
            }
            .padding(Theme.Spacing.card)
        }
    }
    
    private var pnl: Double { entry.pnL ?? 0 }

    var smallWidget: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("PORTFOLIO")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                .tracking(1.5)
                .foregroundStyle(Theme.inkSecondary)
            
            Text(IndianFormatter.formatLakhsCrores(entry.portfolioValue ?? 0))
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                .foregroundStyle(Theme.inkPrimary)
            
            Spacer(minLength: Theme.Spacing.standard)
            
            Text("P&L")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                .tracking(1.5)
                .foregroundStyle(Theme.inkSecondary)
            
            Text((pnl < 0 ? "" : "+") + IndianFormatter.formatLakhsCrores(pnl))
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundStyle(pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
                
            if let updatedAt = entry.updatedAt {
                Text("as of \(updatedAt.formatted(date: .omitted, time: .shortened))")
                    .font(Theme.serialNumberFont(size: 10, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkTertiary)
            }
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
                    .foregroundStyle(Theme.inkSecondary)
                
                ForEach(entry.topHoldings.prefix(3)) { holding in
                    HStack {
                        Text(holding.ticker)
                            .font(Theme.engravedSerif(size: 12, weight: .bold, relativeTo: .caption))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineLimit(1)
                        
                        Spacer()
                        
                        Text(IndianFormatter.formatLakhsCrores(holding.pnl))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundStyle(holding.pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
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
        .description("Track your portfolio P&L.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}
