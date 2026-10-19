import SwiftUI
import Charts

/// One lesson: text/example as Markdown, formulas as a monospace block, interactive
/// widgets inline, then the quiz.
struct LessonView: View {
    @StateObject private var vm: LabLoadViewModel<LabLesson>

    init(lessonId: String) {
        _vm = StateObject(wrappedValue: LabLoadViewModel(isEmpty: { ($0.body ?? []).isEmpty }) {
            try await NetworkManager.shared.labLesson(id: lessonId)
        })
    }

    var body: some View {
        LabScreen(title: vm.value?.title ?? "Lesson") {
            StateCard(title: "this lesson", phase: vm.phase, emptyMessage: "This lesson has no content yet.", onRetry: vm.load) {
                if let lesson = vm.value { LabLessonContent(lesson: lesson) }
            }
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
    }
}

private struct LabLessonContent: View {
    let lesson: LabLesson

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text(lesson.title ?? "")
                .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title2))
                .foregroundStyle(Theme.inkPrimary)
            HStack(spacing: Theme.Spacing.small) {
                if let t = lesson.track { LabChip(text: t) }
                LabChip(text: "\(lesson.minutes ?? 0) min", tint: Theme.inkSecondary, icon: "clock")
            }
            ForEach(Array((lesson.body ?? []).enumerated()), id: \.offset) { _, section in
                LabLessonSectionView(section: section)
            }
            if let quiz = lesson.quiz, !quiz.isEmpty {
                GuillocheDivider()
                QuizView(lessonId: lesson.id, questions: quiz)
            }
        }
    }
}

private struct LabLessonSectionView: View {
    let section: LabLessonSection

    var body: some View {
        switch section.kindValue {
        case .text:
            LabMarkdownBlock(md: section.md)
        case .example:
            LabCard {
                LabCardTitle(title: "Worked example", icon: "lightbulb")
                LabMarkdownBlock(md: section.md)
            }
        case .formula:
            LabFormulaBlock(latex: section.latex, md: section.md)
        case .interactive:
            LabWidgetView(widget: section.widget ?? "", md: section.md)
        case .unknown:
            if section.md != nil { LabMarkdownBlock(md: section.md) }
        }
    }
}

/// Paragraph-aware Markdown: one Text per paragraph so lists and breaks survive.
private struct LabMarkdownBlock: View {
    let md: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            ForEach(Array((md ?? "").components(separatedBy: "\n\n").enumerated()), id: \.offset) { _, para in
                Text(LabFormat.markdown(para))
                    .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct LabFormulaBlock: View {
    let latex: String?
    let md: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            if let latex {
                Text(LabFormat.plainFormula(latex))
                    .font(Theme.monoTabular(size: 14))
                    .foregroundStyle(Theme.securityGold)
                    .padding(Theme.Spacing.standard)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(Theme.canvas.opacity(0.05)))
                    .textSelection(.enabled)
                    .accessibilityLabel("Formula: \(LabFormat.plainFormula(latex))")
            }
            if md != nil { LabMarkdownBlock(md: md) }
        }
    }
}

private struct LabWidgetView: View {
    let widget: String
    let md: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            if md != nil { LabMarkdownBlock(md: md) }
            switch widget {
            case "cost_calculator": LabCostCalculator()
            case "compounding": LabCompoundingWidget()
            default:
                LabCard {
                    StateMessage(icon: "hammer", message: "Interactive \(LabFormat.humanize(widget)) coming soon.")
                }
            }
        }
    }
}

// MARK: - Widgets

private struct LabCostCalculator: View {
    @State private var buyText = "100000"
    @State private var sellText = "105000"

    private var buy: LabCostEstimate.Breakdown { LabCostEstimate.charges(value: Double(buyText) ?? 0, buy: true) }
    private var sell: LabCostEstimate.Breakdown { LabCostEstimate.charges(value: Double(sellText) ?? 0, buy: false) }

    var body: some View {
        LabCard {
            LabCardTitle(title: "Delivery cost calculator", icon: "indianrupeesign.circle")
            LabMoneyField(label: "Buy value (₹)", text: $buyText)
            LabMoneyField(label: "Sell value (₹)", text: $sellText)
            LabKeyValueRow(key: "Brokerage", value: LabFormat.price(buy.brokerage + sell.brokerage))
            LabKeyValueRow(key: "STT (0.1% each side)", value: LabFormat.price(buy.stt + sell.stt))
            LabKeyValueRow(key: "Exchange charges", value: LabFormat.price(buy.exchange + sell.exchange))
            LabKeyValueRow(key: "SEBI fee", value: LabFormat.price(buy.sebi + sell.sebi))
            LabKeyValueRow(key: "Stamp duty (buy)", value: LabFormat.price(buy.stamp))
            LabKeyValueRow(key: "GST (18%)", value: LabFormat.price(buy.gst + sell.gst))
            LabKeyValueRow(key: "Total charges", value: LabFormat.price(buy.total + sell.total), tint: Theme.bearRed)
            LabRoundTripNote(buyValue: Double(buyText) ?? 0, sellValue: Double(sellText) ?? 0, charges: buy.total + sell.total)
        }
    }
}

private struct LabRoundTripNote: View {
    let buyValue: Double
    let sellValue: Double
    let charges: Double

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            let gross = sellValue - buyValue
            LabKeyValueRow(key: "Gross gain", value: IndianFormatter.signedPrice(gross), tint: LabFormat.tint(gross))
            LabKeyValueRow(key: "Net of charges", value: IndianFormatter.signedPrice(gross - charges), tint: LabFormat.tint(gross - charges))
            Text("Approximation using fixed delivery rates (NSE, brokerage min ₹20 or 0.03%). DP charges and exact rounding vary by broker.")
                .font(Theme.microLabel())
                .foregroundStyle(Theme.inkTertiary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct LabMoneyField: View {
    let label: String
    @Binding var text: String

    var body: some View {
        HStack {
            Text(label).font(Theme.engravedSerif(size: 13, relativeTo: .footnote)).foregroundStyle(Theme.inkSecondary)
            Spacer()
            TextField("0", text: $text)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.trailing)
                .font(Theme.monoTabular(size: 14))
                .accessibilityLabel(label)
        }
        .frame(minHeight: 44)
    }
}

private struct LabCompoundingWidget: View {
    private struct YearPoint: Identifiable {
        let id: Int
        let value: Double
    }

    @State private var principalText = "100000"
    @State private var rate = 12.0
    @State private var years = 15.0

    private var points: [YearPoint] {
        LabCostEstimate.compound(principal: Double(principalText) ?? 0, rate: rate / 100, years: Int(years))
            .enumerated().map { YearPoint(id: $0.offset, value: $0.element) }
    }

    var body: some View {
        LabCard {
            LabCardTitle(title: "Compounding", icon: "chart.line.uptrend.xyaxis")
            LabMoneyField(label: "Starting amount (₹)", text: $principalText)
            LabSliderRow(label: "Return per year", value: $rate, range: 0...30, step: 0.5, suffix: "%")
            LabSliderRow(label: "Years", value: $years, range: 1...40, step: 1, suffix: " yrs")
            Chart(points) { p in
                AreaMark(x: .value("Year", p.id), y: .value("Value (₹)", p.value))
                    .foregroundStyle(Theme.bullGreen.opacity(0.2))
                LineMark(x: .value("Year", p.id), y: .value("Value (₹)", p.value))
                    .foregroundStyle(Theme.bullGreen)
            }
            .chartXAxisLabel("Years")
            .chartYAxisLabel("Value (₹)")
            .frame(height: UIScreen.main.bounds.height * 0.22)
            .accessibilityLabel("Value grows to \(LabFormat.money(points.last?.value)) after \(Int(years)) years")
            LabKeyValueRow(key: "Final value", value: LabFormat.money(points.last?.value), tint: Theme.bullGreen)
            Text("Illustration of the arithmetic only. Real returns vary year to year and are never assured.")
                .font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
        }
    }
}

private struct LabSliderRow: View {
    let label: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let suffix: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack {
                Text(label).font(Theme.engravedSerif(size: 13, relativeTo: .footnote)).foregroundStyle(Theme.inkSecondary)
                Spacer()
                Text("\(LabFormat.num(value, digits: step < 1 ? 1 : 0))\(suffix)").font(Theme.monoTabular(size: 13)).foregroundStyle(Theme.inkPrimary)
            }
            Slider(value: $value, in: range, step: step)
                .tint(Theme.securityGold)
                .accessibilityLabel(label)
                .accessibilityValue("\(LabFormat.num(value, digits: step < 1 ? 1 : 0))\(suffix)")
        }
    }
}
