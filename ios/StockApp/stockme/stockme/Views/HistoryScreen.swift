import SwiftUI

struct HistoryScreen: View {
    @EnvironmentObject var reportManager: LocalReportManager

    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .hundred)

                VStack(alignment: .leading, spacing: 16) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("पुरालेख")
                                .font(Theme.hindiFont(size: 11))
                                .foregroundColor(Theme.inkSecondary)
                            Text("REPORT HISTORY")
                                .font(Theme.engravedSerif(size: 28, weight: .bold))
                                .foregroundColor(Theme.inkPrimary)
                        }
                        Spacer()
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, 12)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    if reportManager.savedReports.isEmpty {
                        Spacer()
                        VStack(spacing: 16) {
                            BanknoteSignalBadge(text: "NO RECORDS", color: Theme.inkTertiary, rotation: -4)
                            Text("No official reports have been filed.")
                                .font(.subheadline)
                                .foregroundColor(Theme.inkSecondary)
                        }
                        .frame(maxWidth: .infinity)
                        Spacer()
                    } else {
                        ScrollView {
                            VStack(spacing: 12) {
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
        HStack(spacing: 0) {
            Rectangle()
                .fill(report.signal.color.opacity(0.3))
                .frame(width: 1)
                .padding(.vertical, 12)

            HStack(spacing: 16) {
                StockIcon(ticker: report.ticker, signal: report.signal)

                VStack(alignment: .leading, spacing: 2) {
                    Text(report.companyName.uppercased())
                        .font(Theme.engravedSerif(size: 16, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                    Text("RECORD DATE: \(report.analysisDate)")
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundColor(Theme.inkSecondary)
                }

                Spacer()

                BanknoteSignalBadge(signal: report.signal)
                    .stampAppear()
            }
            .padding(.vertical, 14)
            .padding(.leading, 12)
            .padding(.trailing, 16)
        }
        .banknoteCard()
    }
}
