import SwiftUI

/// Capital-gains working for listed shares (I29, spec 3.7): one financial year, with a CSV to hand to a
/// chartered accountant. Informational only; no tax-saving prompts. Pushed inside PortfolioScreen's
/// NavigationStack; shown only while money_tax_report is on.
struct TaxReportView: View {
    @StateObject private var model: TaxReportViewModel
    @AppStorage("nivesh_hidePortfolioValues") private var hideValues = false

    init(model: @autoclosure @escaping () -> TaxReportViewModel = TaxReportViewModel()) {
        _model = StateObject(wrappedValue: model())
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                TaxDisclaimerCard()
                TaxYearPicker(fy: $model.fy, options: model.options)
                switch model.state {
                case .loading:
                    ProgressView().tint(Theme.securityGold).frame(maxWidth: .infinity).padding(.top, Theme.Spacing.large)
                case .empty:
                    Text(TaxCopy.empty(fy: model.fy))
                        .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.top, Theme.Spacing.large)
                case .offline:
                    HoldingStatusBanner(text: "You're offline. Connect to see this report.")
                case .failed(let message):
                    BanknoteErrorCanvas(title: "Couldn't load this report.", detail: message, retryAction: { await model.load() })
                case .loaded:
                    if let report = model.report {
                        TaxReportBody(report: report, model: model, hideValues: hideValues)
                    }
                }
                Spacer(minLength: Theme.Spacing.sectionBreath)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Capital gains")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: model.fy) { await model.load() }
        .onDisappear { model.discardCSV() }
    }
}

private struct TaxReportBody: View {
    let report: CapitalGainsReport
    @ObservedObject var model: TaxReportViewModel
    let hideValues: Bool

    private var shortTerm: [CapitalGainsRow] { report.rows.filter { !$0.isLongTerm } }
    private var longTerm: [CapitalGainsRow] { report.rows.filter(\.isLongTerm) }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text(report.scopeNote)
                .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            TaxSummaryCard(summary: report.summary, hideValues: hideValues)
            if !report.notComputed.isEmpty { TaxNotComputedCard(items: report.notComputed) }
            if !shortTerm.isEmpty { TaxTermSection(title: "Short-term sales", rows: shortTerm, hideValues: hideValues) }
            if !longTerm.isEmpty { TaxTermSection(title: "Long-term sales", rows: longTerm, hideValues: hideValues) }
            TaxExportRow(model: model)
            Text(TaxCopy.notApplied)
                .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkTertiary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct TaxDisclaimerCard: View {
    var body: some View {
        Text(TaxCopy.disclaimer)
            .font(Theme.engravedSerif(size: 13, weight: .medium, relativeTo: .footnote))
            .foregroundStyle(Theme.inkPrimary)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(Theme.Spacing.card)
            .banknoteCard()
    }
}

struct TaxYearPicker: View {
    @Binding var fy: String
    let options: [String]

    var body: some View {
        HStack {
            Text("Financial year")
                .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            Picker("Financial year", selection: $fy) {
                ForEach(options, id: \.self) { Text("FY \($0)").tag($0) }
            }
            .pickerStyle(.menu)
            .tint(Theme.securityGold)
        }
    }
}

struct TaxSummaryCard: View {
    let summary: CapitalGainsSummary
    var hideValues = false

    private var limit: Double { summary.ltcgExemptionLimitInr }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HoldingSectionTitle(text: "SUMMARY")
            TaxAmountLine(label: TaxCopy.shortTermLabel(rate: 20), amount: summary.stcg.post, hideValues: hideValues)
            if summary.stcg.pre != 0 {
                TaxAmountLine(label: TaxCopy.shortTermLabel(rate: 15), amount: summary.stcg.pre, hideValues: hideValues)
            }
            TaxAmountLine(label: TaxCopy.longTermLabel(rate: "12.5", limit: limit), amount: summary.ltcg.post, hideValues: hideValues)
            if summary.ltcg.pre != 0 {
                TaxAmountLine(label: TaxCopy.longTermLabel(rate: "10", limit: limit), amount: summary.ltcg.pre, hideValues: hideValues)
            }
            GuillocheDivider()
            TaxAmountLine(label: "Above the exemption", amount: summary.ltcgAboveExemptionInr, hideValues: hideValues, signed: false)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct TaxAmountLine: View {
    let label: String
    let amount: Double
    var hideValues = false
    var signed = true

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.standard) {
            Text(label)
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: Theme.Spacing.medium)
            Text(hideValues ? "Rs ••••" : (signed ? TaxCopy.signedRupees(amount) : XRayCopy.rupees(amount)))
                .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote).weight(.semibold))
                .foregroundStyle(Theme.inkPrimary)
        }
    }
}

struct TaxNotComputedCard: View {
    let items: [NotComputedRow]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HoldingSectionTitle(text: "NOT COMPUTED")
            ForEach(items) { item in
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("\(item.symbol): sold \(DecimalText.editable(item.quantity, maxFractionDigits: 4)) on \(MoneyReturnCopy.day(item.soldOn) ?? item.soldOn)")
                        .font(Theme.engravedSerif(size: 13, weight: .medium, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(TaxReason.userText(item.reason))
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct TaxTermSection: View {
    let title: String
    let rows: [CapitalGainsRow]
    var hideValues = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HoldingSectionTitle(text: title.uppercased())
            VStack(spacing: Theme.Spacing.none) {
                ForEach(Array(rows.enumerated()), id: \.element.id) { idx, row in
                    TaxRowCard(row: row, hideValues: hideValues)
                    if idx != rows.count - 1 { GuillocheDivider().padding(.horizontal, Theme.Spacing.card) }
                }
            }
            .banknoteCard()
        }
    }
}

struct TaxRowCard: View {
    let row: CapitalGainsRow
    var hideValues = false

    private var dates: String {
        let sold = MoneyReturnCopy.day(row.soldOn) ?? row.soldOn
        let bought = MoneyReturnCopy.day(row.acquiredOn) ?? row.acquiredOn
        return "Sold \(sold), bought \(bought) · section \(row.section)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack(alignment: .firstTextBaseline) {
                Text("\(row.name) · \(DecimalText.editable(row.quantity, maxFractionDigits: 4)) shares")
                    .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(2)
                Spacer(minLength: Theme.Spacing.medium)
                Text(hideValues ? "Rs ••••" : TaxCopy.signedRupees(row.gainInr))
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote).weight(.semibold))
                    .foregroundStyle(Theme.inkPrimary)
            }
            Text(dates)
                .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkTertiary)
            if row.needsReview {
                Text("NEEDS REVIEW")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.securityGold)
                ForEach(row.reviewReasons, id: \.self) { reason in
                    Text("• " + TaxReason.userText(reason))
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }
}

/// "Export CSV": downloads the file, then offers it through a ShareLink.
struct TaxExportRow: View {
    @ObservedObject var model: TaxReportViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            if let url = model.csvURL {
                ShareLink(item: url) { CASButtonLabel(title: "Share CSV") }
            } else if model.exporting {
                ProgressView().tint(Theme.securityGold).frame(maxWidth: .infinity)
            } else {
                Button { Task { await model.prepareCSV() } } label: { CASButtonLabel(title: "Export CSV") }
                    .buttonStyle(EKPressStyle())
            }
            if let error = model.exportError {
                Text(error)
                    .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.bearRed)
            }
        }
    }
}
