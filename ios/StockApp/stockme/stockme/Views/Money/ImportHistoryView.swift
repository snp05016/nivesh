import SwiftUI

/// "Your imports": past statement imports with an undo behind a confirmation. Pushed inside
/// PortfolioScreen's NavigationStack; shown only while money_cas_import is on.
struct ImportHistoryView: View {
    private enum Phase: Equatable { case loading, loaded, failed(String) }

    @State private var phase: Phase = .loading
    @State private var imports: [ImportBatchSummary] = []
    @State private var pendingUndo: ImportBatchSummary?
    @State private var undoing = false
    @State private var actionError: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                if let actionError {
                    Text(actionError)
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.bearRed)
                }
                switch phase {
                case .loading:
                    ProgressView().tint(Theme.securityGold).frame(maxWidth: .infinity).padding(.top, Theme.Spacing.xLarge)
                case .failed(let message):
                    BanknoteErrorCanvas(title: "Couldn't load your imports.", detail: message, retryAction: { await load() })
                case .loaded:
                    if imports.isEmpty {
                        Text("No imports yet.")
                            .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkSecondary)
                            .frame(maxWidth: .infinity)
                            .padding(.top, Theme.Spacing.xLarge)
                    } else {
                        VStack(spacing: Theme.Spacing.none) {
                            ForEach(Array(imports.enumerated()), id: \.element.id) { idx, item in
                                ImportHistoryRow(item: item, disabled: undoing, onUndo: { pendingUndo = item })
                                if idx != imports.count - 1 {
                                    GuillocheDivider().padding(.horizontal, Theme.Spacing.card)
                                }
                            }
                        }
                        .banknoteCard()
                    }
                }
                Spacer(minLength: Theme.Spacing.sectionBreath)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Your imports")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
        .confirmationDialog(
            "Undo this import? Its funds will be removed from your portfolio.",
            isPresented: Binding(get: { pendingUndo != nil }, set: { if !$0 { pendingUndo = nil } }),
            titleVisibility: .visible
        ) {
            Button("Undo import", role: .destructive) {
                if let item = pendingUndo { Task { await undo(item) } }
            }
            Button("Cancel", role: .cancel) { pendingUndo = nil }
        }
    }

    private func load() async {
        do {
            imports = try await NetworkManager.shared.listImports()
            phase = .loaded
        } catch is CancellationError {
        } catch let e as URLError where e.code == .cancelled {
        } catch {
            phase = .failed((error as? NetworkError)?.errorDescription ?? CASImportErrorCode.generic)
        }
    }

    private func undo(_ item: ImportBatchSummary) async {
        undoing = true
        actionError = nil
        defer { undoing = false; pendingUndo = nil }
        do {
            _ = try await NetworkManager.shared.undoImport(batchId: item.batchId)
            await load()
        } catch let e as CASImportError {
            actionError = CASImportErrorCode.message(for: e.code)
        } catch {
            actionError = (error as? NetworkError)?.errorDescription ?? CASImportErrorCode.generic
        }
    }
}

private struct ImportHistoryRow: View {
    let item: ImportBatchSummary
    let disabled: Bool
    let onUndo: () -> Void

    private var title: String {
        MoneyReturnCopy.day(item.statementTo).map { "Statement dated \($0)" } ?? "Statement"
    }

    private var subtitle: String {
        guard item.isCommitted else { return "Not added to your portfolio" }
        return CASPreviewCopy.done(item.schemesImported)
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(title)
                    .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                Text(subtitle)
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
            }
            Spacer()
            if item.isCommitted {
                Button("Undo", action: onUndo)
                    .font(Theme.engravedSerif(size: 13, weight: .semibold, relativeTo: .body))
                    .foregroundStyle(Theme.bearRed)
                    .disabled(disabled)
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }
}
