import SwiftUI

/// "Latest results" in the Financials tab: revenue, net profit and EPS with year-on-year change,
/// the source note and a link to the filing. Hidden when the feature is off or there is no digest.
struct LatestResultsCard: View {
    let ticker: String

    private enum Phase {
        case loading
        case hidden
        case loaded(ResultsDigest)
        case failed
    }

    @State private var phase: Phase = .loading

    var body: some View {
        content
            .task(id: ticker) { await load() }
    }

    @ViewBuilder
    private var content: some View {
        switch phase {
        case .loading:
            SPSkeletonBlock(rows: 3)
        case .hidden:
            EmptyView()
        case .failed:
            LatestResultsFailure { Task { await load() } }
        case .loaded(let digest):
            LatestResultsBody(digest: digest)
        }
    }

    private func load() async {
        phase = .loading
        do {
            phase = .loaded(try await NetworkManager.shared.fetchResultsDigest(symbol: ticker))
        } catch {
            if error is CancellationError || (error as? URLError)?.code == .cancelled { return }
            phase = ResultsDigest.shouldHide(error) ? .hidden : .failed
        }
    }
}

private struct LatestResultsFailure: View {
    let retry: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text("Couldn't load latest results.")
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
            Button {
                HapticManager.selection()
                retry()
            } label: {
                Text("Retry")
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct LatestResultsBody: View {
    let digest: ResultsDigest

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("LATEST RESULTS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkTertiary)
                Text(digest.periodLabel)
                    .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                    .foregroundColor(Theme.inkPrimary)
            }

            if digest.isPending {
                Text("Figures will appear once our data source publishes them.")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundColor(Theme.inkSecondary)
            } else if !digest.isUnavailable {
                VStack(spacing: Theme.Spacing.standard) {
                    ResultsMetricRow(label: "Revenue", value: digest.revenueInr.map(IndianFormatter.formatLakhsCrores),
                                     yoy: digest.revenueYoyPct)
                    ResultsMetricRow(label: "Net profit", value: digest.netProfitInr.map(IndianFormatter.formatLakhsCrores),
                                     yoy: digest.netProfitYoyPct)
                    ResultsMetricRow(label: "EPS", value: digest.eps.map { ResultsDigest.epsText($0) },
                                     yoy: digest.epsYoyPct)
                }
            }

            Text(digest.numbersSourceText)
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                .foregroundColor(Theme.inkTertiary)

            if let url = digest.filingURL {
                Link("View filing", destination: url)
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct ResultsMetricRow: View {
    let label: String
    let value: String?
    let yoy: Double?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(value ?? "—")
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                Text(ResultsDigest.yoyText(yoy))
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundColor(Theme.inkSecondary)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(label) \(value ?? "not available"), \(ResultsDigest.yoyText(yoy))")
    }
}
