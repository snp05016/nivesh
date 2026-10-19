import SwiftUI

/// Up to three plain risk facts for a held stock, each with its source and date.
/// Renders nothing while loading, on error, offline, with the flags off, or with no flags.
struct RiskFlagsCard: View {
    let ticker: String
    @State private var flags: [RiskFlagDTO] = []
    @State private var selected: RiskFlagDTO?

    var body: some View {
        Group {
            if !flags.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Text("RISK FLAGS")
                        .font(Theme.sectionCapsLabel())
                        .foregroundStyle(Theme.inkTertiary)
                    ForEach(flags) { flag in
                        Button { selected = flag } label: { RiskFlagRow(flag: flag) }
                            .buttonStyle(.plain)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .banknoteCard()
            }
        }
        .task(id: ticker) {
            flags = (try? await NetworkManager.shared.fetchRiskFlags(symbol: ticker))?.flags ?? []
        }
        .sheet(item: $selected) { flag in
            RiskFlagDetailSheet(flag: flag)
        }
    }
}

struct RiskFlagRow: View {
    let flag: RiskFlagDTO

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Image(systemName: "exclamationmark.triangle")
                .foregroundStyle(Theme.holdAmber)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(stripEmoji(flag.title))
                    .font(Theme.engravedSerif(size: 14, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)
                Text(stripEmoji(flag.text))
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(2)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(Theme.inkTertiary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityHint("Shows the source and date")
    }
}

struct RiskFlagDetailSheet: View {
    let flag: RiskFlagDTO
    @Environment(\.dismiss) private var dismiss

    private var asOfText: String? {
        guard let raw = flag.asOf else { return nil }
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.dateFormat = "yyyy-MM-dd"
        guard let date = parser.date(from: raw) else { return nil }
        let display = DateFormatter()
        display.locale = Locale(identifier: "en_US_POSIX")
        display.dateFormat = "d MMM yyyy"
        return display.string(from: date)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                Text(stripEmoji(flag.title))
                    .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .title3))
                    .foregroundStyle(Theme.inkPrimary)
                Text(stripEmoji(flag.text))
                    .font(Theme.engravedSerif(size: 14))
                    .foregroundStyle(Theme.inkSecondary)
                Text("Source: \(flag.source)")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
                if let asOfText {
                    Text("As of \(asOfText)")
                        .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                        .foregroundStyle(Theme.inkTertiary)
                }
                if SafeURL.web(flag.sourceUrl) != nil {
                    Button("Open the NSE page") { SafeURL.open(flag.sourceUrl) }
                        .foregroundStyle(Theme.securityGold)
                        .frame(minHeight: 44)
                }
                Button("Done") { dismiss() }
                    .foregroundStyle(Theme.securityGold)
                    .frame(minHeight: 44)
            }
            .padding(Theme.screenPadding)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .presentationDetents([.medium, .large])
    }
}
