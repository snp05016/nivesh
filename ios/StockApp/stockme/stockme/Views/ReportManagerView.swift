import SwiftUI

struct ReportManagerView: View {
    @ObservedObject var reportManager: LocalReportManager
    @State private var confirmDeleteAll = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            if reportManager.savedReports.isEmpty {
                VStack(spacing: Theme.Spacing.standard) {
                    Spacer()
                    Image(systemName: "doc.text.magnifyingglass")
                        .font(Theme.engravedSerif(size: 48))
                        .foregroundStyle(Theme.inkTertiary)
                    Text("No saved reports")
                        .font(Theme.engravedSerif(size: 15))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                }
            } else {
                List {
                    ForEach(reportManager.savedReports, id: \.ticker) { report in
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            HStack {
                                Text(report.ticker)
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundStyle(Theme.securityGold)
                                Spacer()
                                Text(report.signal.label)
                                    .font(Theme.microLabel(size: 8))
                                    .foregroundStyle(report.signal.color)
                                    .padding(.horizontal, Theme.Spacing.tight)
                                    .padding(.vertical, 2)
                                    .background(report.signal.color.opacity(0.12))
                                    .clipShape(Capsule())
                            }
                            Text(report.companyName)
                                .font(Theme.engravedSerif(size: 12))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineLimit(1)
                            Text("Analysed: \(report.analysisDate)")
                                .font(Theme.microLabel(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .padding(.vertical, Theme.Spacing.small)
                    }
                    .onDelete { indexSet in
                        withAnimation {
                            reportManager.savedReports.remove(atOffsets: indexSet)
                        }
                    }

                    Section {
                        Button(role: .destructive) {
                            confirmDeleteAll = true
                        } label: {
                            HStack {
                                Spacer()
                                Text("DELETE ALL REPORTS")
                                    .font(Theme.officialStampFont(size: 9))
                                Spacer()
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
        }
        .navigationTitle("Saved Reports")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbar {
            if !reportManager.savedReports.isEmpty {
                EditButton()
                    .foregroundStyle(Theme.securityGold)
            }
        }
        .banknoteDialog(
            "Delete all saved reports?",
            isPresented: $confirmDeleteAll,
            message: "This permanently removes every saved report from this device.",
            buttons: [
                .init("Delete All", role: .destructive) {
                    reportManager.savedReports.removeAll()
                },
                .cancel()
            ]
        )
    }
}
