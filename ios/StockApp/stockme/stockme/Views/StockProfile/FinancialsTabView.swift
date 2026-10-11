import SwiftUI

struct FinancialsTabView: View {
    let isLoading: Bool
    let quarterlyFinancials: [QuarterlyFinancial]
    let piotroski: PiotroskiData?
    let fetchFinancials: () async -> Void

    var body: some View {
        LazyVStack(spacing: Theme.sectionSpacing) {
            if isLoading {
                SPSkeletonBlock(rows: 8)
            } else {
                if !quarterlyFinancials.isEmpty {
                    FinancialsTableView(quarters: quarterlyFinancials)
                }
                if let piotroski = piotroski {
                    PiotroskiCardView(data: piotroski)
                }
                if quarterlyFinancials.isEmpty && piotroski == nil {
                    SPEmptyStateView(message: "Financial data unavailable")
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.card)
        .task { await fetchFinancials() }
    }
}

struct FinancialsTableView: View {
    let quarters: [QuarterlyFinancial]

    var body: some View {
        let shown = Array(quarters.prefix(8))
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("QUARTERLY FINANCIALS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.none) {
                Text("QTR").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.28, alignment: .leading)
                Text("REVENUE").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.36, alignment: .trailing)
                Text("PAT").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.36, alignment: .trailing)
            }
            .padding(.horizontal, Theme.Spacing.medium)
            .explainableTerm("PAT")

            ForEach(shown) { q in
                HStack(spacing: Theme.Spacing.none) {
                    Text(q.label)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: colW * 0.28, alignment: .leading)
                    Text(IndianFormatter.priceCompact(q.revenue))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: colW * 0.36, alignment: .trailing)
                    let profitUp = q.netProfit >= 0
                    Text(IndianFormatter.priceCompact(q.netProfit))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(profitUp ? Theme.bullGreen : Theme.bearRed)
                        .frame(width: colW * 0.36, alignment: .trailing)
                }
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .overlay(Rectangle().fill(Theme.borderFine).frame(height: 0.5), alignment: .bottom)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct PiotroskiCardView: View {
    let data: PiotroskiData

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("PIOTROSKI F-SCORE")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    if let fScore = data.fScore {
                        let maxScore = data.maxPossible ?? 9
                        Text("\(fScore) / \(maxScore)")
                            .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                            .foregroundStyle(fScore >= 7 ? Theme.bullGreen : fScore >= 4 ? Theme.holdAmber : Theme.bearRed)
                    }
                }
                .explainableTerm("Piotroski Score")
                Spacer()
                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    if let grade = data.grade {
                        let gradeColor: Color = {
                            switch grade {
                            case "STRONG": return Theme.bullGreen
                            case "GOOD": return Theme.bullGreenLight
                            case "DISTRESS": return Theme.bearRed
                            case "WEAK": return Theme.bearRedLight
                            default: return Theme.holdAmber
                            }
                        }()
                        BanknoteSignalBadge(text: grade, color: gradeColor, rotation: -2)
                    }
                    if let confidence = data.confidence {
                        Text(confidence)
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(0.8)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
            }

            if let checks = data.checks, !checks.isEmpty {
                GuillocheDivider()

                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.tight) {
                    ForEach(Array(checks.keys.sorted()), id: \.self) { key in
                        let pass = checks[key] == "PASS"
                        // Shape (check / cross) carries pass/fail, not colour alone.
                        HStack(spacing: Theme.Spacing.small) {
                            Image(systemName: pass ? "checkmark.circle.fill" : "xmark.circle.fill")
                                .font(.caption2)
                                .foregroundStyle(pass ? Theme.bullGreen : Theme.bearRed)
                            Text(formatCheckLabel(key))
                                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineLimit(1)
                            Spacer()
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(formatCheckLabel(key)): \(pass ? "pass" : "fail")")
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func formatCheckLabel(_ key: String) -> String {
        key.replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { $0.prefix(1).uppercased() + $0.dropFirst().lowercased() }
            .joined(separator: " ")
    }
}
