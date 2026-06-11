import SwiftUI

struct HistoryScreen: View {
    @EnvironmentObject var reportManager: LocalReportManager

    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .hundred)

                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    HStack {
                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text("पुरालेख")
                                .font(Theme.hindiFont(size: 11, relativeTo: .caption))
                                .foregroundStyle(Theme.inkSecondary)
                            Text("REPORT HISTORY")
                                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        Spacer()
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, 12)

                    SectionDivider().padding(.horizontal, Theme.screenPadding)

                    if reportManager.savedReports.isEmpty {
                        Spacer()
                        VStack(spacing: Theme.Spacing.card) {
                            BanknoteSignalBadge(text: "NO RECORDS", color: Theme.inkTertiary, rotation: -4)
                            Text("No official reports have been filed.")
                                .font(.subheadline)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        .frame(maxWidth: .infinity)
                        Spacer()
                    } else {
                        ScrollView {
                            VStack(spacing: Theme.Spacing.standard) {
                                ForEach(reportManager.savedReports, id: \.ticker) { report in
                                    NavigationLink(destination: AnalysisScreen(ticker: report.ticker, forceCached: true)) {
                                        ReportHistoryNoteRow(report: report)
                                    }
                                    .ekPress()
                                    .contextMenu {
                                        Button(role: .destructive) {
                                            withAnimation {
                                                reportManager.deleteReport(ticker: report.ticker)
                                            }
                                        } label: {
                                            Label("Void Record", systemImage: "trash")
                                        }
                                    }
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.bottom, 100)
                        }
                    }
                }
            }
        }
    }
}

private struct ReportHistoryNoteRow: View {
    let report: StockAnalysis

    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            Rectangle()
                .fill(report.signal.color.opacity(0.3))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: report.ticker, signal: report.signal)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(report.companyName.uppercased())
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("RECORD DATE: \(report.analysisDate)")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkSecondary)
                }

                Spacer()

                BanknoteSignalBadge(signal: report.signal)
                    .stampAppear()
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .banknoteCard()
    }
}
