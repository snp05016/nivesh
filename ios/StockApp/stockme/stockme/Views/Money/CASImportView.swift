import SwiftUI
import UniformTypeIdentifiers

/// Import mutual funds from a CAMS/KFintech CAS (I28, spec 3.5). Pushed inside PortfolioScreen's
/// NavigationStack (no stack of its own). Shown only while the money_cas_import flag is on.
struct CASImportView: View {
    @StateObject private var model: CASImportViewModel
    @Environment(\.dismiss) private var dismiss
    @AppStorage("nivesh_hidePortfolioValues") private var hideValues = false
    @State private var showImporter = false

    init(client: CASImportClient = .live) {
        _model = StateObject(wrappedValue: CASImportViewModel(client: client))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                switch model.state {
                case .idle:
                    CASIntroBlock()
                    CASConsentCard(attestsOwnStatement: $model.attestsOwnStatement, agreesToNotice: $model.agreesToNotice)
                    Button { showImporter = true } label: { CASButtonLabel(title: "Choose PDF") }
                        .buttonStyle(EKPressStyle())
                        .disabled(!model.canChooseFile)
                        .opacity(model.canChooseFile ? 1 : 0.4)
                case .fileChosen, .uploading:
                    CASPasswordBlock(model: model)
                case .preview, .committing:
                    if let preview = model.preview {
                        CASPreviewList(preview: preview, hideValues: hideValues)
                    }
                    CASPreviewActions(model: model)
                case .done(let funds):
                    CASImportResultView(funds: funds, onDone: { dismiss() })
                case .failed(_, let message):
                    CASFailureBlock(message: message, onRetry: { model.retry() })
                }
                Spacer(minLength: Theme.Spacing.sectionBreath)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Import mutual funds")
        .navigationBarTitleDisplayMode(.inline)
        .fileImporter(isPresented: $showImporter, allowedContentTypes: [.pdf]) { result in
            handlePicked(result)
        }
    }

    /// Reads the picked PDF inside its security scope; files over the cap are refused from metadata alone.
    private func handlePicked(_ result: Result<URL, Error>) {
        guard case .success(let url) = result else { model.fileReadFailed(); return }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        if let size = try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize, size > CASNotice.maxPDFBytes {
            model.fileTooLarge()
        } else if let data = try? Data(contentsOf: url) {
            model.fileChosen(data, name: url.lastPathComponent)
        } else {
            model.fileReadFailed()
        }
    }
}

private struct CASIntroBlock: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Upload your Consolidated Account Statement (CAS) from CAMS or KFintech.")
                .font(Theme.engravedSerif(size: 15, weight: .medium, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
            Text("Request a Detailed CAS for the period Since inception from the CAMS or KFintech website. It arrives by email as a password-protected PDF.")
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
        }
    }
}

private struct CASPasswordBlock: View {
    @ObservedObject var model: CASImportViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            if let name = model.fileName {
                Label(name, systemImage: "doc.fill")
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
            }
            SecureField("Statement password", text: $model.password)
                .privacySensitive()
                .textContentType(.password)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
                .padding(Theme.Spacing.standard)
                .banknoteCard()
            if model.state == .uploading {
                HStack(spacing: Theme.Spacing.medium) {
                    ProgressView().tint(Theme.securityGold)
                    Text("Reading your statement…")
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                }
            } else {
                Button { Task { await model.upload() } } label: { CASButtonLabel(title: "Read statement") }
                    .buttonStyle(EKPressStyle())
                    .disabled(!model.canUpload)
                    .opacity(model.canUpload ? 1 : 0.4)
            }
        }
    }
}

private struct CASPreviewActions: View {
    @ObservedObject var model: CASImportViewModel

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            if model.state == .committing {
                ProgressView().tint(Theme.securityGold)
            } else {
                Button { Task { await model.commit() } } label: { CASButtonLabel(title: "Add to portfolio") }
                    .buttonStyle(EKPressStyle())
                Button { Task { await model.cancel() } } label: { CASButtonLabel(title: "Cancel", filled: false) }
                    .buttonStyle(EKPressStyle())
            }
        }
    }
}

private struct CASFailureBlock: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text(message)
                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.bearRed)
                .fixedSize(horizontal: false, vertical: true)
            Button(action: onRetry) { CASButtonLabel(title: "Try again") }
                .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
