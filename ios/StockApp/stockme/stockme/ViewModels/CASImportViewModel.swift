import Foundation

/// The network calls the import flow makes, injectable so tests never touch the network.
struct CASImportClient {
    var preview: (Data, String) async throws -> CASPreview
    var commit: (Int) async throws -> CASCommitResult
    var cancel: (Int) async throws -> Void

    static let live = CASImportClient(
        preview: { try await NetworkManager.shared.previewCAS(pdf: $0, password: $1) },
        commit: { try await NetworkManager.shared.commitImport(batchId: $0) },
        cancel: { try await NetworkManager.shared.cancelImport(batchId: $0) }
    )
}

/// CAS import flow (I28): consent -> file chosen -> uploading -> preview -> committing -> done | failed.
/// The PDF and its password live only here, in memory; the password is cleared after every upload.
@MainActor
final class CASImportViewModel: ObservableObject {
    enum State: Equatable {
        case idle
        case fileChosen
        case uploading
        case preview
        case committing
        case done(funds: Int)
        case failed(code: String, message: String)
    }

    @Published private(set) var state: State = .idle
    @Published private(set) var preview: CASPreview?
    @Published private(set) var fileName: String?
    @Published var attestsOwnStatement = false
    @Published var agreesToNotice = false
    @Published var password = ""

    private var pdf: Data?
    private let client: CASImportClient

    init(client: CASImportClient = .live) {
        self.client = client
    }

    /// Both notice toggles must be on before a file can be chosen.
    var canChooseFile: Bool { attestsOwnStatement && agreesToNotice }
    var canUpload: Bool { state == .fileChosen && !password.isEmpty }

    /// Takes the chosen PDF's bytes. Over 10 MB is refused here, before any upload.
    func fileChosen(_ data: Data, name: String?) {
        guard data.count <= CASNotice.maxPDFBytes else {
            pdf = nil
            fail(code: CASImportErrorCode.fileTooLarge.rawValue)
            return
        }
        pdf = data
        fileName = name
        password = ""
        state = .fileChosen
    }

    /// The picked file's size was read from its metadata and is over the cap; nothing was loaded.
    func fileTooLarge() {
        pdf = nil
        fail(code: CASImportErrorCode.fileTooLarge.rawValue)
    }

    func fileReadFailed() {
        pdf = nil
        fail(code: CASImportErrorCode.notAPdf.rawValue)
    }

    func upload() async {
        guard let pdf, canUpload else { return }
        let typed = password
        state = .uploading
        defer { password = "" }
        do {
            let result = try await client.preview(pdf, typed)
            preview = result
            state = .preview
        } catch is CancellationError {
            state = .fileChosen
        } catch {
            fail(error)
        }
    }

    func commit() async {
        guard state == .preview, let batchId = preview?.batchId else { return }
        state = .committing
        do {
            let result = try await client.commit(batchId)
            clearFile()
            state = .done(funds: result.schemesImported)
        } catch {
            fail(error)
        }
    }

    /// Cancels the previewed batch on the server (best effort) and starts over.
    func cancel() async {
        if let batchId = preview?.batchId, state == .preview {
            try? await client.cancel(batchId)
        }
        reset()
    }

    /// After a failure: a wrong password or a busy server goes back to the password field with the
    /// same file; anything else starts over.
    func retry() {
        if case .failed(let code, _) = state, CASImportErrorCode(rawValue: code)?.isRetryable == true, pdf != nil {
            password = ""
            state = .fileChosen
        } else {
            reset()
        }
    }

    func reset() {
        clearFile()
        attestsOwnStatement = false
        agreesToNotice = false
        state = .idle
    }

    private func clearFile() {
        pdf = nil
        fileName = nil
        preview = nil
        password = ""
    }

    private func fail(_ error: Error) {
        if let e = error as? CASImportError {
            fail(code: e.code)
        } else {
            state = .failed(code: "", message: (error as? NetworkError)?.errorDescription ?? error.localizedDescription)
        }
    }

    private func fail(code: String) {
        state = .failed(code: code, message: CASImportErrorCode.message(for: code))
    }
}
