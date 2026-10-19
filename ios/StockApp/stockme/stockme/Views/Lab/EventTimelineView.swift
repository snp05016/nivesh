import SwiftUI
import Charts

/// Market event reconstruction for one symbol: close-price line with a marker per
/// detected item, and a list labelling what each item rests on (prices, exchange
/// filings or a cited source).
struct EventTimelineView: View {
    @State private var symbol = ""
    @State private var start = Calendar.current.date(byAdding: .year, value: -2, to: Date()) ?? Date()
    @State private var end = Calendar.current.date(byAdding: .day, value: -31, to: Date()) ?? Date()
    @State private var timeline: LabEventTimeline?
    @State private var loading = false
    @State private var error: String?
    @State private var task: Task<Void, Never>?

    private var canLoad: Bool { !symbol.trimmingCharacters(in: .whitespaces).isEmpty && end > start && !loading }

    var body: some View {
        LabScreen(title: "Event Explorer") {
            LabEventQueryCard(symbol: $symbol, start: $start, end: $end, busy: loading, enabled: canLoad, onLoad: load)
            if let error { LabInlineError(message: error) }
            if loading { StateSkeleton(lines: 4).accessibilityLabel("Loading events") }
            if let t = timeline, !loading { LabEventResults(timeline: t) }
        }
        .onDisappear { task?.cancel() }
    }

    private func load() {
        HapticManager.selection()
        task?.cancel()
        loading = true
        error = nil
        let sym = symbol.trimmingCharacters(in: .whitespaces).uppercased()
        let s = WireDate.dayFormatter.string(from: start), e = WireDate.dayFormatter.string(from: end)
        task = Task {
            do {
                timeline = try await NetworkManager.shared.labEventTimeline(symbol: sym, start: s, end: e)
            } catch where LabErrors.isCancellation(error) {
            } catch {
                self.error = ConnectivityMonitor.shared.isOnline ? LabErrors.message(error)
                    : "You're offline. Connect to the internet to load events."
            }
            loading = false
        }
    }
}

private struct LabEventQueryCard: View {
    @Binding var symbol: String
    @Binding var start: Date
    @Binding var end: Date
    let busy: Bool
    let enabled: Bool
    let onLoad: () -> Void
    @FocusState private var symbolFocused: Bool

    var body: some View {
        LabCard {
            TextField("NSE symbol, e.g. RELIANCE", text: $symbol)
                .focused($symbolFocused)
                .submitLabel(.search)
                .onSubmit { if enabled { load() } }
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .font(Theme.monoTabular(size: 15))
                .frame(minHeight: 44)
            DatePicker("From", selection: $start, displayedComponents: .date)
            DatePicker("To", selection: $end, in: start..., displayedComponents: .date)
            Button(action: load) { LabPrimaryLabel(title: "Reconstruct events", icon: "waveform.path.ecg", busy: busy, enabled: enabled) }
                .buttonStyle(EKPressStyle())
                .disabled(!enabled)
        }
        .font(Theme.engravedSerif(size: 14, relativeTo: .body))
        .tint(Theme.securityGold)
    }

    private func load() {
        symbolFocused = false
        onLoad()
    }
}

extension LabEventKind {
    var title: String {
        switch self {
        case .priceAnomaly: return "Price anomaly"
        case .volumeAnomaly: return "Volume anomaly"
        case .corporateAction: return "Corporate action"
        case .sourcedEvent: return "Sourced event"
        case .unknown: return "Other"
        }
    }

    var icon: String {
        switch self {
        case .priceAnomaly: return "arrow.up.arrow.down"
        case .volumeAnomaly: return "chart.bar.fill"
        case .corporateAction: return "building.columns"
        case .sourcedEvent: return "newspaper"
        case .unknown: return "circle"
        }
    }

    var tint: Color {
        switch self {
        case .priceAnomaly: return Theme.bearRed
        case .volumeAnomaly: return Theme.holdAmber
        case .corporateAction: return Theme.bullGreen
        case .sourcedEvent: return Theme.securityGold
        case .unknown: return Theme.inkSecondary
        }
    }
}

private struct LabEventResults: View {
    let timeline: LabEventTimeline

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            LabCaveatBanner(warnings: timeline.provenance?.warnings ?? [])
            LabEventChart(bars: timeline.bars ?? [], items: timeline.items ?? [])
            LabCard {
                LabCardTitle(title: "\(timeline.items?.count ?? 0) items", icon: "list.bullet")
                if (timeline.items ?? []).isEmpty {
                    Text("Nothing unusual detected in this window.").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
                }
                ForEach(timeline.items ?? [], id: \.self) { item in LabEventRow(item: item) }
                if let note = timeline.note {
                    Text(note).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }
}

private struct LabEventChart: View {
    private struct Marker: Identifiable {
        let id: Int
        let date: Date
        let close: Double
        let kind: LabEventKind
    }

    let bars: [LabCloseBar]
    let items: [LabEventItem]

    /// Each item is pinned to the close on its date (or the nearest earlier bar).
    private var markers: [Marker] {
        items.enumerated().compactMap { i, item in
            guard let day = item.day, let bar = bars.last(where: { $0.date <= day }) ?? bars.first else { return nil }
            return Marker(id: i, date: day, close: bar.c, kind: item.kindValue)
        }
    }

    var body: some View {
        LabCard {
            LabCardTitle(title: "Close price with events", icon: "chart.xyaxis.line")
            if bars.count < 2 {
                Text("No price history in this window.").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            } else {
                Chart {
                    ForEach(bars, id: \.d) { b in
                        LineMark(x: .value("Date", b.date), y: .value("Close (₹)", b.c)).foregroundStyle(Theme.inkSecondary)
                    }
                    ForEach(markers) { m in
                        PointMark(x: .value("Date", m.date), y: .value("Close (₹)", m.close))
                            .foregroundStyle(by: .value("Kind", m.kind.title))
                            .symbolSize(60)
                    }
                }
                .chartForegroundStyleScale(["Price anomaly": Theme.bearRed, "Volume anomaly": Theme.holdAmber,
                                            "Corporate action": Theme.bullGreen, "Sourced event": Theme.securityGold,
                                            "Other": Theme.inkSecondary])
                .chartYScale(domain: .automatic(includesZero: false))
                .chartYAxisLabel("Close (₹)")
                .chartXAxisLabel("Date")
                .frame(height: UIScreen.main.bounds.height * 0.3)
                .accessibilityLabel("Close price over \(bars.count) sessions with \(markers.count) event markers")
            }
        }
    }
}

private struct LabEventRow: View {
    let item: LabEventItem

    private var evidenceLabel: String {
        switch item.evidence {
        case "prices": return "Evidence: price data"
        case "exchange": return "Evidence: exchange record"
        case "source": return "Evidence: cited source"
        default: return "Evidence: \(item.evidence ?? "unspecified")"
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Image(systemName: item.kindValue.icon).foregroundStyle(item.kindValue.tint).frame(minWidth: 24).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                HStack(spacing: Theme.Spacing.small) {
                    Text(LabFormat.day(item.date)).font(Theme.microLabel()).foregroundStyle(Theme.securityGold)
                    Text(item.kindValue.title).font(Theme.microLabel()).foregroundStyle(item.kindValue.tint)
                }
                Text(item.text ?? "").font(Theme.engravedSerif(size: 13, relativeTo: .footnote)).foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: Theme.Spacing.small) {
                    Text(evidenceLabel).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
                    if let raw = item.sourceUrl, let url = URL(string: raw), url.scheme == "https" {
                        Link("Source", destination: url).font(Theme.microLabel()).foregroundStyle(Theme.securityGold)
                    }
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}
