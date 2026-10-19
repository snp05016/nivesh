import SwiftUI

// Shared building blocks for the Lab screens. Copy rule for every Lab string:
// educational, never advice ("score", "hypothesis", "evidence"; never "signal",
// "target", "recommendation", "guaranteed").

// MARK: - Formatting

enum LabFormat {
    /// Fraction -> signed percent ("+4.20%"). nil -> em dash.
    static func pct(_ fraction: Double?) -> String {
        guard let fraction, fraction.isFinite else { return "—" }
        return IndianFormatter.delta(fraction * 100)
    }

    /// Fraction -> unsigned percent ("42.0%").
    static func share(_ fraction: Double?) -> String {
        guard let fraction, fraction.isFinite else { return "—" }
        return String(format: "%.1f%%", fraction * 100)
    }

    static func money(_ value: Double?) -> String {
        guard let value, value.isFinite else { return "—" }
        return IndianFormatter.formatLakhsCrores(value)
    }

    static func price(_ value: Double?) -> String {
        guard let value, value.isFinite else { return "—" }
        return IndianFormatter.price(value)
    }

    static func num(_ value: Double?, digits: Int = 2) -> String {
        guard let value, value.isFinite else { return "—" }
        return String(format: "%.\(digits)f", value)
    }

    static func qty(_ value: Double?) -> String {
        guard let value, value.isFinite else { return "—" }
        return IndianFormatter.count(value)
    }

    /// "2020-03-02" -> "02 Mar 2020"; anything unparseable is shown as sent.
    static func day(_ iso: String?) -> String {
        guard let iso else { return "—" }
        guard let d = WireDate.dayFormatter.date(from: String(iso.prefix(10))) else { return iso }
        return displayDay.string(from: d)
    }

    private static let displayDay: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_IN")
        f.dateFormat = "dd MMM yyyy"
        return f
    }()

    /// "tradesPerWeek" / "trades_per_week" -> "trades per week".
    static func humanize(_ key: String) -> String {
        var out = ""
        for ch in key {
            if ch == "_" { out.append(" ") }
            else if ch.isUppercase { out.append(" "); out.append(Character(ch.lowercased())) }
            else { out.append(ch) }
        }
        return out.trimmingCharacters(in: .whitespaces)
    }

    /// Readable names for the report's built-in baselines (keys arrive camel-cased).
    static func baselineName(_ key: String) -> String {
        switch key {
        case "baseMom20": return "20-day momentum"
        case "baseRev5": return "5-day reversal"
        case "baseLowvol20": return "20-day low volatility"
        default: return humanize(key)
        }
    }

    /// Light LaTeX -> plain text for the monospace formula block.
    static func plainFormula(_ latex: String) -> String {
        var s = latex
        let rules: [(String, String)] = [
            (#"\\(?:text|mathrm|operatorname|mathbf)\{([^{}]*)\}"#, "$1"),
            (#"\\frac\{([^{}]*)\}\{([^{}]*)\}"#, "($1) / ($2)"),
            (#"\\sqrt\{([^{}]*)\}"#, "√($1)"),
            (#"\\(left|right)"#, ""),
        ]
        for (pattern, template) in rules {
            s = s.replacingOccurrences(of: pattern, with: template, options: .regularExpression)
        }
        let symbols: [String: String] = [
            "\\times": "×", "\\cdot": "·", "\\sigma": "σ", "\\mu": "μ", "\\sum": "Σ", "\\Delta": "Δ",
            "\\le": "≤", "\\ge": "≥", "\\approx": "≈", "\\%": "%", "{,}": ",", "\\,": " ", "\\ ": " ",
        ]
        for (k, v) in symbols.sorted(by: { $0.key.count > $1.key.count }) { s = s.replacingOccurrences(of: k, with: v) }
        return s.replacingOccurrences(of: "{", with: "").replacingOccurrences(of: "}", with: "")
    }

    /// Markdown body text; falls back to the raw string.
    static func markdown(_ md: String?) -> AttributedString {
        let options = AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        return (try? AttributedString(markdown: md ?? "", options: options)) ?? AttributedString(md ?? "")
    }

    static func tint(_ value: Double?) -> Color {
        guard let value else { return Theme.inkSecondary }
        return value >= 0 ? Theme.bullGreen : Theme.bearRed
    }
}

// MARK: - Layout

/// Wrapping row for chips.
struct LabFlowLayout: Layout {
    var spacing: CGFloat = Theme.Spacing.small

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(width: proposal.width ?? .infinity, subviews: subviews)
        return CGSize(width: proposal.width ?? rows.width, height: rows.height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = arrange(width: bounds.width, subviews: subviews)
        for (index, point) in rows.points.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + point.x, y: bounds.minY + point.y), proposal: .unspecified)
        }
    }

    private func arrange(width: CGFloat, subviews: Subviews) -> (points: [CGPoint], width: CGFloat, height: CGFloat) {
        var points: [CGPoint] = []
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0, maxX: CGFloat = 0
        for sub in subviews {
            let size = sub.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            points.append(CGPoint(x: x, y: y))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
            maxX = max(maxX, x)
        }
        return (points, maxX, y + rowHeight)
    }
}

// MARK: - Pieces

struct LabCardTitle: View {
    let title: String
    var icon: String? = nil

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            if let icon {
                Image(systemName: icon).foregroundStyle(Theme.securityGold).accessibilityHidden(true)
            }
            Text(title.uppercased())
                .font(Theme.sectionCapsLabel())
                .tracking(1.2)
                .foregroundStyle(Theme.inkSecondary)
        }
        .accessibilityAddTraits(.isHeader)
    }
}

struct LabChip: View {
    let text: String
    var tint: Color = Theme.securityGold
    var icon: String? = nil

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            if let icon { Image(systemName: icon).accessibilityHidden(true) }
            Text(text)
        }
        .font(Theme.labelStyle)
        .foregroundStyle(tint)
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.small)
        .background(Capsule().fill(tint.opacity(0.13)))
    }
}

struct LabStatTile: View {
    let label: String
    let value: String
    var caption: String? = nil
    var tint: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.microLabel())
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.monoTabular(size: 15, relativeTo: .headline))
                .foregroundStyle(tint)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            if let caption {
                Text(caption)
                    .font(Theme.microLabel())
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.medium)
        .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(Theme.canvas.opacity(0.04)))
        .accessibilityElement(children: .combine)
    }
}

/// 0-100 ring for process scores.
struct LabScoreRing: View {
    let score: Double
    let label: String

    private var tint: Color { score >= 70 ? Theme.bullGreen : score >= 40 ? Theme.holdAmber : Theme.bearRed }

    var body: some View {
        ZStack {
            Circle().stroke(Theme.inkTertiary.opacity(0.2), lineWidth: 8)
            Circle()
                .trim(from: 0, to: min(max(score, 0), 100) / 100)
                .stroke(tint, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(Int(score.rounded()))")
                    .font(Theme.dataLarge(size: 24))
                    .foregroundStyle(Theme.inkPrimary)
                Text("of 100").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
        }
        .frame(width: 88, height: 88)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(Int(score.rounded())) out of 100")
    }
}

/// Dataset caveat: shown whenever `provenance.warnings` is non-empty.
struct LabCaveatBanner: View {
    let warnings: [String]

    var body: some View {
        if !warnings.isEmpty {
            HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(Theme.holdAmber)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("Dataset caveat")
                        .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .subheadline))
                        .foregroundStyle(Theme.holdAmber)
                    ForEach(warnings, id: \.self) { w in
                        Text(w)
                            .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(Theme.Spacing.standard)
            .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(Theme.holdAmber.opacity(0.12)))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.holdAmber.opacity(0.4), lineWidth: 0.5))
            .accessibilityElement(children: .combine)
        }
    }
}

/// Gold capsule used for primary Lab actions. Apply with `.buttonStyle(EKPressStyle())`.
struct LabPrimaryLabel: View {
    let title: String
    var icon: String? = nil
    var busy = false
    var enabled = true

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            if busy { ProgressView().tint(Theme.onAccent) }
            else if let icon { Image(systemName: icon).accessibilityHidden(true) }
            Text(title)
        }
        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
        .foregroundStyle(Theme.onAccent)
        .frame(maxWidth: .infinity, minHeight: 44)
        .background(Capsule().fill(enabled ? Theme.securityGold : Theme.inkTertiary.opacity(0.4)))
    }
}

/// Inline error line (icon + text, never colour alone).
struct LabInlineError: View {
    let message: String

    var body: some View {
        Label(message, systemImage: "exclamationmark.circle")
            .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
            .foregroundStyle(Theme.bearRed)
            .fixedSize(horizontal: false, vertical: true)
    }
}

/// Wraps a screen body: canvas background, LazyVStack inside a ScrollView.
struct LabScreen<Content: View>: View {
    let title: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: Theme.Spacing.card) {
                content()
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

/// Card shell: padding + banknoteCard.
struct LabCard<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            content()
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
    }
}

/// Label/value row for dense tables.
struct LabKeyValueRow: View {
    let key: String
    let value: String
    var tint: Color = Theme.inkPrimary

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(key)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            Spacer(minLength: Theme.Spacing.medium)
            Text(value)
                .font(Theme.monoTabular(size: 13, relativeTo: .footnote))
                .foregroundStyle(tint)
                .multilineTextAlignment(.trailing)
        }
        .accessibilityElement(children: .combine)
    }
}
