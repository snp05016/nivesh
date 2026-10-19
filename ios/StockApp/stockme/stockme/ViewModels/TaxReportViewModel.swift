import Foundation

/// Owns the downloaded CSV so it is deleted when the screen goes away, whichever way that happens.
final class TempCSVFile {
    private(set) var url: URL?

    func set(_ new: URL) {
        clear()
        url = new
    }

    func clear() {
        if let url { try? FileManager.default.removeItem(at: url) }
        url = nil
    }

    deinit { clear() }
}

/// FY capital-gains working (I29). Read-only: figures come from the server; nothing here advises.
@MainActor
final class TaxReportViewModel: ObservableObject {
    enum State: Equatable {
        case loading, loaded, empty, offline
        case failed(String)
    }

    @Published private(set) var state: State = .loading
    @Published private(set) var report: CapitalGainsReport?
    @Published private(set) var csvURL: URL?
    @Published private(set) var exporting = false
    @Published private(set) var exportError: String?
    @Published var fy: String

    let options: [String]

    private let fetch: (String) async throws -> CapitalGainsReport
    private let download: (String) async throws -> URL
    private let file = TempCSVFile()

    init(now: Date = Date(),
         fetch: @escaping (String) async throws -> CapitalGainsReport = { try await NetworkManager.shared.fetchCapitalGains(fy: $0) },
         download: @escaping (String) async throws -> URL = { try await NetworkManager.shared.downloadCapitalGainsCSV(fy: $0) }) {
        self.options = TaxFY.options(now)
        self.fy = TaxFY.defaultFY(now)
        self.fetch = fetch
        self.download = download
    }

    func load() async {
        let wanted = fy
        state = .loading
        report = nil
        discardCSV()
        do {
            let result = try await fetch(wanted)
            guard wanted == fy else { return }   // the picker moved on while this was loading
            report = result
            state = result.rows.isEmpty && result.notComputed.isEmpty ? .empty : .loaded
        } catch is CancellationError {
        } catch let e as URLError where e.code == .cancelled {
        } catch {
            guard wanted == fy else { return }
            state = Self.state(for: error)
        }
    }

    /// Downloads the CSV for the loaded FY; `csvURL` then feeds a ShareLink.
    func prepareCSV() async {
        guard report != nil, !exporting else { return }
        exporting = true
        exportError = nil
        defer { exporting = false }
        do {
            let url = try await download(fy)
            file.set(url)
            csvURL = url
        } catch is CancellationError {
        } catch {
            exportError = (error as? NetworkError)?.errorDescription ?? "Couldn't prepare the file. Please try again."
        }
    }

    /// Deletes the temporary CSV (the screen disappeared, or the year changed).
    func discardCSV() {
        file.clear()
        csvURL = nil
        exportError = nil
    }

    static func state(for error: Error) -> State {
        if case .fetchFailed(_, let status, _)? = error as? NetworkError, status < 0 { return .offline }
        return .failed((error as? NetworkError)?.errorDescription ?? error.localizedDescription)
    }
}
