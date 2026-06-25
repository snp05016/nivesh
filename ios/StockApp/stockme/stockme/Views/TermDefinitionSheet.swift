import SwiftUI

struct TermDefinitionSheet: View {
    let entry: FinanceTerm
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    Text(entry.term.uppercased())
                        .font(Theme.officialStampFont(size: 14, relativeTo: .title3))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)

                    Text(entry.definition)
                        .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(5)

                    GuillocheDivider()

                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text("EXAMPLE")
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .tracking(1.2)
                            .foregroundStyle(Theme.inkTertiary)
                        Text(entry.example)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .lineSpacing(4)
                    }

                    if !entry.relatedTerms.isEmpty {
                        GuillocheDivider()

                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text("RELATED")
                                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                .tracking(1.2)
                                .foregroundStyle(Theme.inkTertiary)
                            FlowLayout(spacing: Theme.Spacing.small) {
                                ForEach(Array(entry.relatedTerms.enumerated()), id: \.offset) { _, related in
                                    if let relEntry = FinanceTerms.shared.lookup(related) {
                                        NavigationLink {
                                            TermDefinitionSheet(entry: relEntry)
                                        } label: {
                                            Text(related)
                                                .font(Theme.labelStyle)
                                                .foregroundStyle(Theme.securityGold)
                                                .padding(.horizontal, Theme.Spacing.standard)
                                                .padding(.vertical, Theme.Spacing.tight)
                                                .background(Theme.securityGold.opacity(0.1))
                                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                                        }
                                        .buttonStyle(EKPressStyle())
                                    }
                                }
                            }
                        }
                    }

                    Spacer(minLength: Theme.Spacing.xLarge)
                }
                .padding(Theme.Spacing.card)
            }
            .background(Theme.canvas)
            .navigationTitle(entry.term.capitalized)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
    HapticManager.selection()
                        HapticManager.selection()
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title3)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    .buttonStyle(EKPressStyle())
                    .accessibilityLabel("Close definition")
                }
            }
        }
    }
}

private struct FlowLayout: Layout {
    let spacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? UIScreen.main.bounds.width - 2 * Theme.screenPadding
        let rows = arrange(width, subviews)
        let height = rows.reduce(0.0) { sum, row in
            let rowH = row.map(\.maxY).max() ?? 0
            return sum + rowH + (sum > 0 ? spacing : 0)
        }
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = arrange(bounds.width, subviews)
        var yOffset: CGFloat = 0
        for row in rows {
            for item in row {
                subviews[item.index].place(
                    at: CGPoint(x: bounds.minX + item.x, y: bounds.minY + yOffset),
                    proposal: .unspecified
                )
            }
            if let first = row.first {
                yOffset += first.size.height + spacing
            }
        }
    }

    private func arrange(_ width: CGFloat, _ subviews: Subviews) -> [[(index: Int, x: CGFloat, size: CGSize, maxY: CGFloat)]] {
        var rows: [[(index: Int, x: CGFloat, size: CGSize, maxY: CGFloat)]] = [[]]
        var currentX: CGFloat = 0
        for (idx, subview) in subviews.enumerated() {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > width, !rows[rows.count - 1].isEmpty {
                rows.append([])
                currentX = 0
            }
            rows[rows.count - 1].append((index: idx, x: currentX, size: size, maxY: size.height))
            currentX += size.width + spacing
        }
        return rows
    }
}
