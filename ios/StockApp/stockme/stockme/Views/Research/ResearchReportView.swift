import SwiftUI

// MARK: - Stock report (spec 10.1-10.3)
//
// Every figure is the server's `display` string, shown as it arrives; the app never
// formats or recomputes a number. AI-written prose goes through `stripEmoji`. The
// copy names the reference class and horizon and never phrases anything as a call
// on the stock (ResearchCopyLexiconTests scans this folder). Colours are neutral:
// meaning is always carried by text, never by colour alone.

struct ResearchReportView: View {
    let symbol: String
    @StateObject private var model: ResearchViewModel
    @EnvironmentObject private var authManager: AuthManager

    init(symbol: String) {
        self.symbol = symbol
        _model = StateObject(wrappedValue: ResearchViewModel(symbol: symbol))
    }

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()
            switch model.state {
            case .loading:
                ResearchSkeletonView()
            case .computing:
                ResearchMessageView(icon: "gearshape.2", title: "Computing from market data",
                                    detail: "Building this stock report now. This takes about 15 seconds.",
                                    showsProgress: true)
            case .loaded(let report, let savedCopy):
                ResearchReportContent(report: report, savedCopy: savedCopy)
            case .unknownSymbol:
                ResearchMessageView(icon: "magnifyingglass", title: "Stock reports cover NSE equities only",
                                    detail: "\(symbol.uppercased()) is not an equity listed on the NSE.")
            case .signedOut:
                ResearchMessageView(icon: "person.crop.circle", title: "Sign in to see stock reports",
                                    detail: "Stock reports are free for everyone with a Nivesh account.",
                                    actionTitle: "Sign in", action: { authManager.logout() })
            case .disabled:
                ResearchMessageView(icon: "clock", title: "Stock report not available yet",
                                    detail: "Stock reports are being prepared. Check back soon.")
            case .error(let message):
                ScrollView {
                    BanknoteErrorCanvas(title: "Stock report unavailable", detail: message,
                                        retryAction: { await model.load() })
                        .padding(Theme.screenPadding)
                }
            }
        }
        .navigationTitle("Stock report")
        .task { await model.loadIfNeeded() }
    }
}

// MARK: - Loaded report

/// Sections in spec 10.1 order.
private struct ResearchReportContent: View {
    let report: ResearchReport
    let savedCopy: Bool
    @State private var showModelCard = false
    @State private var showProvenance = false

    private func narrative(_ id: ResearchNarrativeSectionID) -> String? {
        report.narrative?.sections?.first { $0.id == id }?.text
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                if savedCopy {
                    ResearchNoticeBanner(icon: "wifi.slash",
                                         text: "Saved copy. You are offline, so this is the last report this device loaded. The figures may be out of date.")
                } else if let staleness = report.staleness, staleness.state == .stale || staleness.state == .expired {
                    // A saved copy's staleness block is from when it was saved, so it is not shown as current.
                    ResearchStalenessBanner(staleness: staleness, marketDate: report.asOf.marketDate)
                }
                ResearchHeaderCard(report: report, savedCopy: savedCopy)
                if let narrativeBlock = report.narrative {
                    ResearchSummaryCard(narrative: narrativeBlock) { showProvenance = true }
                }
                ResearchOutlookSection(outlooks: report.outlooks ?? []) { showModelCard = true }
                ResearchRiskCard(risk: report.risk, narrative: narrative(.risk))
                ResearchFactorProfileCard(profile: report.factorProfile, narrative: narrative(.factorProfile))
                ResearchFundamentalsCard(fundamentals: report.fundamentals, narrative: narrative(.fundamentals))
                ResearchMethodCard(report: report,
                                   onModelCard: { showModelCard = true },
                                   onProvenance: { showProvenance = true })
                ResearchDisclaimerFooter(compliance: report.compliance)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .sheet(isPresented: $showModelCard) {
            ModelCardSheet(card: report.modelCard, outlooks: report.outlooks ?? [])
        }
        .sheet(isPresented: $showProvenance) {
            ProvenanceSheet(report: report)
        }
    }
}

// MARK: - Header and summary

private struct ResearchHeaderCard: View {
    let report: ResearchReport
    let savedCopy: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack(alignment: .firstTextBaseline) {
                Text(report.companyName ?? report.symbol)
                    .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer(minLength: Theme.Spacing.medium)
                if savedCopy {
                    ResearchChipLabel(text: "Saved copy")
                } else if let staleness = report.staleness {
                    ResearchStalenessChip(staleness: staleness)
                }
            }
            Text("\(report.symbol) · \(report.exchange ?? "NSE")")
                .font(Theme.monoTabular(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
            if let close = report.snapshot?.lastClose {
                ResearchFactValue(fact: close, size: 28)
            }
            Text("Data as of \(ResearchFormat.day(report.asOf.marketDate)) close")
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkTertiary)
            if let change = report.snapshot?.dayChangePct {
                ResearchFactRow(fact: change)
            }
            if let r12 = report.snapshot?.r12mPct {
                ResearchFactRow(fact: r12)
            }
            if let excess = report.snapshot?.excess12mVsNifty50Pp {
                ResearchFactRow(fact: excess)
            }
        }
        .researchCardStyle()
    }
}

private struct ResearchSummaryCard: View {
    let narrative: ResearchNarrative
    let onTap: () -> Void

    private var caption: String {
        narrative.status == .llmValidated
            ? "Written by an AI language model from the computed figures, then checked automatically. Tap to see where the figures come from."
            : "Built from a fixed template using the computed figures. Tap to see where the figures come from."
    }

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                ResearchSectionTitle(title: "Summary")
                Text(stripEmoji(narrative.summary ?? ""))
                    .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Text(caption)
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .researchCardStyle()
        }
        .buttonStyle(EKPressStyle())
        .accessibilityHint("Opens where the figures come from")
    }
}

private struct ResearchOutlookSection: View {
    let outlooks: [ResearchOutlook]
    let onModelCard: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            ResearchSectionTitle(title: "What testing found")
            if outlooks.isEmpty {
                ResearchUnavailableText(reason: nil)
            }
            ForEach(Array(outlooks.enumerated()), id: \.offset) { _, outlook in
                ResearchOutlookCard(outlook: outlook, onModelCard: onModelCard)
            }
        }
    }
}

// MARK: - Data and method, disclaimer

private struct ResearchMethodCard: View {
    let report: ResearchReport
    let onModelCard: () -> Void
    let onProvenance: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            ResearchSectionTitle(title: "Data and method")
            ForEach(Array((report.provenance?.sources ?? []).enumerated()), id: \.offset) { _, source in
                ResearchKeyValueRow(key: ResearchFormat.sourceName(source.id),
                                    value: ResearchFormat.sourceStatus(source))
            }
            ResearchKeyValueRow(key: "Engine version", value: report.engineVersion ?? "Not recorded")
            ResearchKeyValueRow(key: "Report id", value: String((report.reportId ?? "Not recorded").prefix(8)))
            ResearchLinkButton(title: "What we tested", action: onModelCard)
            ResearchLinkButton(title: "Where the figures come from", action: onProvenance)
        }
        .researchCardStyle()
    }
}

private struct ResearchDisclaimerFooter: View {
    let compliance: ResearchCompliance?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(compliance?.disclaimerText
                 ?? "This stock report is general, educational information computed from public market data. It is not investment advice.")
            if let disclosure = compliance?.aiDisclosure {
                Text(disclosure)
            }
        }
        .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
        .foregroundStyle(Theme.inkTertiary)
        .fixedSize(horizontal: false, vertical: true)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, Theme.Spacing.medium)
    }
}

// MARK: - Staleness

private struct ResearchStalenessChip: View {
    let staleness: ResearchStaleness

    private var text: String {
        switch staleness.state {
        case .fresh: return "Up to date"
        case .stale:
            let days = staleness.sessionsOld ?? 1
            return days == 1 ? "1 trading day old" : "\(days) trading days old"
        case .expired: return "Out of date"
        default: return "Age unknown"
        }
    }

    var body: some View {
        ResearchChipLabel(text: text)
    }
}

private struct ResearchChipLabel: View {
    let text: String

    var body: some View {
        Text(text)
            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
            .foregroundStyle(Theme.inkSecondary)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .overlay(Capsule().stroke(Theme.borderSage, lineWidth: 1))
    }
}

private struct ResearchStalenessBanner: View {
    let staleness: ResearchStaleness
    let marketDate: String

    private var text: String {
        if staleness.state == .expired {
            return "This report describes the \(ResearchFormat.day(marketDate)) close and is out of date, so outlooks are not shown. A newer report appears after the next nightly update."
        }
        return "This report describes the \(ResearchFormat.day(marketDate)) close. The nightly update has not run since then."
    }

    var body: some View {
        ResearchNoticeBanner(icon: "exclamationmark.triangle", text: text)
    }
}

// MARK: - States

private struct ResearchSkeletonView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                ForEach([96, 140, 180, 220, 200], id: \.self) { height in
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                        .fill(Theme.canvasDeep)
                        .frame(height: CGFloat(height))
                }
            }
            .padding(Theme.screenPadding)
        }
        .scrollDisabled(true)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Loading the stock report")
    }
}

private struct ResearchMessageView: View {
    let icon: String
    let title: String
    let detail: String
    var showsProgress = false
    var actionTitle: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            if showsProgress {
                ProgressView().tint(Theme.securityGold)
            } else {
                Image(systemName: icon)
                    .font(.largeTitle)
                    .foregroundStyle(Theme.securityGold)
                    .accessibilityHidden(true)
            }
            Text(title)
                .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                .foregroundStyle(Theme.inkPrimary)
            Text(detail)
                .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkSecondary)
            if let actionTitle, let action {
                Button(actionTitle, action: action)
                    .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .body))
                    .foregroundStyle(Theme.onAccent)
                    .padding(.horizontal, Theme.Spacing.large)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.securityGold, in: Capsule())
                    .buttonStyle(EKPressStyle())
            }
        }
        .multilineTextAlignment(.center)
        .padding(Theme.screenPadding)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Shared building blocks (used by every Research card)

struct ResearchSectionTitle: View {
    let title: String

    var body: some View {
        Text(title.uppercased())
            .font(Theme.sectionCapsLabel())
            .tracking(1.2)
            .foregroundStyle(Theme.inkPrimary)
            .accessibilityAddTraits(.isHeader)
    }
}

struct ResearchNoticeBanner: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Image(systemName: icon)
                .foregroundStyle(Theme.securityGold)
                .accessibilityHidden(true)
            Text(text)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.standard)
        .background(Theme.securityGoldLight, in: RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderStrong, lineWidth: 1))
    }
}

/// A server `display` string. Long-press opens its label, as-of date, source, method
/// and status.
struct ResearchFactValue: View {
    let fact: ResearchFact
    var size: CGFloat = 15
    /// False when an enclosing row already opens the detail sheet.
    var inspectable = true

    var body: some View {
        let text = Text(fact.display ?? "Not available")
            .font(Theme.serialNumberFont(size: size, relativeTo: size > 20 ? .title : .body))
            .foregroundStyle(fact.display == nil ? Theme.inkTertiary : Theme.inkPrimary)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
        if inspectable {
            text.researchFactDetail(fact)
        } else {
            text
        }
    }
}

/// Server label on the left, server display on the right; unavailable facts say why.
struct ResearchFactRow: View {
    let fact: ResearchFact
    var label: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
                Text(label ?? fact.label ?? "")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: Theme.Spacing.medium)
                if fact.display != nil {
                    ResearchFactValue(fact: fact, inspectable: false)
                }
            }
            if fact.display == nil {
                ResearchUnavailableText(reason: fact.reason)
            } else if fact.status == .stale {
                Text("Source data is out of date")
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .accessibilityElement(children: .combine)
        .researchFactDetail(fact)
    }
}

struct ResearchUnavailableText: View {
    let reason: ResearchReasonCode?

    var body: some View {
        Text("Not available: \(ResearchFormat.reason(reason))")
            .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
            .foregroundStyle(Theme.inkTertiary)
            .fixedSize(horizontal: false, vertical: true)
    }
}

struct ResearchKeyValueRow: View {
    let key: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
            Text(key)
                .foregroundStyle(Theme.inkSecondary)
            Spacer(minLength: Theme.Spacing.medium)
            Text(value)
                .foregroundStyle(Theme.inkPrimary)
                .multilineTextAlignment(.trailing)
        }
        .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
        .accessibilityElement(children: .combine)
    }
}

struct ResearchLinkButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.small) {
                Text(title)
                Image(systemName: "chevron.right").font(.caption)
            }
            .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .subheadline))
            .foregroundStyle(Theme.securityGold)
        }
        .buttonStyle(EKPressStyle())
    }
}

/// Server prose for one section (validated AI text or a fixed template).
struct ResearchNarrativeText: View {
    let text: String?

    var body: some View {
        if let text, !text.isEmpty {
            Text(stripEmoji(text))
                .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

extension View {
    func researchCardStyle() -> some View {
        padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
    }
}

/// Plain-words text for server codes. Never formats a number.
enum ResearchFormat {
    private static let dayOut: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_IN")
        f.dateFormat = "d MMM yyyy"
        return f
    }()

    /// "2026-10-09" or an ISO timestamp → "9 Oct 2026"; unparsable input is returned as is.
    static func day(_ wire: String?) -> String {
        guard let wire, !wire.isEmpty else { return "an unknown date" }
        guard let date = WireDate.day(String(wire.prefix(10))) else { return wire }
        return dayOut.string(from: date)
    }

    static func reason(_ code: ResearchReasonCode?) -> String {
        switch code {
        case .sourceUnavailable: return "the data source returned nothing"
        case .staleSource: return "the data source is out of date"
        case .insufficientHistory: return "not enough trading history yet"
        case .dataQualityFlag: return "a data quality check failed"
        case .notApplicableFinancials: return "not applicable to banks, NBFCs and insurers"
        case .sourceNotIntegrated: return "this data source is not connected yet"
        case .notInUniverse: return "computed only for the 200 most-traded NSE stocks"
        case .backtestFailed: return "the loss model failed its backtest for this stock"
        case .policyHidden: return "not shown in this version of the app"
        case .unknown, nil: return "unavailable for this report"
        }
    }

    static func sourceName(_ source: ResearchSource?) -> String {
        switch source {
        case .nseBhavcopy: return "NSE daily price file"
        case .yfinance: return "Yahoo Finance"
        case .computed: return "Computed by Nivesh"
        case .model: return "Statistical model"
        case .unknown, nil: return "Other source"
        }
    }

    static func sourceStatus(_ source: ResearchSourceStatus) -> String {
        let state: String
        switch source.status {
        case .ok: state = "Working"
        case .fallback: state = "Backup source used"
        case .failed: state = "Failed"
        default: state = "Unknown"
        }
        guard let last = source.lastSuccess else { return state }
        return "\(state), last updated \(day(last))"
    }
}
