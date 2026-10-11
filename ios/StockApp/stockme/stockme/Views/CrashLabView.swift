import SwiftUI

struct CrashLabView: View {
    @State private var crashes: [CrashReport] = []
    @State private var lintOutput: String = ""
    @State private var lintRunning = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)

            if crashes.isEmpty {
                VStack(spacing: Theme.Spacing.standard) {
                    Spacer()
                    Image(systemName: "checkmark.shield.fill")
                        .font(Theme.engravedSerif(size: 48))
                        .foregroundStyle(Theme.bullGreen.opacity(0.6))
                    Text("No crashes recorded")
                        .font(Theme.engravedSerif(size: 16, weight: .medium, relativeTo: .headline))
                        .foregroundStyle(Theme.inkSecondary)
                    Text("सब ठीक है / All Clear")
                        .font(Theme.hindiFont(size: 12, relativeTo: .caption))
                        .foregroundStyle(Theme.inkTertiary)
                    Spacer()
                }
            } else {
                List {
                    ForEach(crashes) { crash in
                        CrashCardView(report: crash)
                    }
                    .onDelete { indexSet in
                        for i in indexSet {
                            CrashLog.shared.delete(id: crashes[i].id)
                        }
                        crashes = CrashLog.shared.all()
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
        }
        .navigationTitle("Crash Lab")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbar {
            if !crashes.isEmpty {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Clear All") { HapticManager.selection()
                        CrashLog.shared.clearAll()
                        crashes = []
                    }
                    .foregroundStyle(Theme.bearRed)
                }
            }
        }
        .onAppear {
            crashes = CrashLog.shared.all()
            UserDefaults.standard.set(crashes.count, forKey: "nivesh_crashCountSeen")
        }
    }
}

private struct CrashCardView: View {
    let report: CrashReport
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                Circle().fill(Theme.bearRed).frame(width: 10, height: 10)
                Text("FATAL CRASH")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.2).foregroundStyle(Theme.bearRed)
                Spacer()
                Text(report.timestamp.prefix(16).replacingOccurrences(of: "T", with: " "))
                    .font(Theme.serialNumberFont(size: 9)).foregroundStyle(Theme.inkTertiary)
                Text(report.signalName ?? report.exceptionName ?? "?")
                    .font(Theme.serialNumberFont(size: 9)).foregroundStyle(Theme.bearRed)
            }

            if let file = report.swiftFile {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text("FILE:").font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                    Text("\(file)\(report.approxLine.map { ":\($0)" } ?? "")")
                        .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.securityGold)
                }
            }

            if let viewPath = report.viewPath {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text("VIEW:").font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                    Text(viewPath)
                        .font(Theme.engravedSerif(size: 10, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary).lineLimit(2)
                }
            }

            Text(report.classification)
                .font(Theme.engravedSerif(size: 11, weight: .semibold))
                .foregroundStyle(Theme.inkPrimary)

            Button {
                HapticManager.selection()
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { expanded.toggle() }
            } label: {
                HStack {
                    Text(expanded ? "HIDE STACK TRACE" : "SHOW STACK TRACE")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                    Image(systemName: expanded ? "chevron.up" : "chevron.down").font(.caption2)
                }
                .foregroundStyle(Theme.inkTertiary)
            }
            .buttonStyle(EKPressStyle())

            if expanded {
                ScrollView(.horizontal) {
                    Text(report.stackTrace)
                        .font(Theme.microLabel(size: 9))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .padding(Theme.Spacing.small)
                .background(Theme.surfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }

            HStack(spacing: Theme.Spacing.standard) {
                Button {
                    HapticManager.selection()
                    let json = (try? JSONEncoder().encode(report)).flatMap { String(data: $0, encoding: .utf8) } ?? ""
                    UIPasteboard.general.string = json
                } label: {
                    Text("COPY DIAGNOSTIC")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.standard).padding(.vertical, Theme.Spacing.tight)
                        .background(Theme.securityGold.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }
                .buttonStyle(EKPressStyle())

                Button(role: .destructive) { HapticManager.selection()
                    CrashLog.shared.delete(id: report.id)
                } label: {
                    Text("DELETE").font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .foregroundStyle(Theme.bearRed)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
