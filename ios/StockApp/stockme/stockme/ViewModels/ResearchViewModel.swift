import Foundation
import Combine

/// Drives `ResearchReportView` (spec 10.2). Opening the screen only reads the stored
/// report; when the server has none it computes one on demand ("Computing from market
/// data"). Nothing here is written to the saved-reports History. The last good report
/// per symbol is kept in the Caches directory and shown as a "Saved copy" when offline.
@MainActor
final class ResearchViewModel: ObservableObject {
    enum State {
        case loading
        /// 404 NOT_COVERED: POST .../compute is running.
        case computing
        case loaded(ResearchReport, savedCopy: Bool)
        case unknownSymbol
        case signedOut
        case disabled
        case error(String)
    }

    @Published private(set) var state: State = .loading
    let symbol: String
    private var started = false

    init(symbol: String) {
        self.symbol = symbol
    }

    /// First appearance only; navigating back to the screen keeps what is shown.
    func loadIfNeeded() async {
        guard !started else { return }
        started = true
        await load()
    }

    func load() async {
        state = .loading
        do {
            let result = try await NetworkManager.shared.fetchResearchReport(symbol: symbol)
            if case .notCovered(let computeAvailable) = result {
                guard computeAvailable else { state = .disabled; return }
                state = .computing
                apply(try await NetworkManager.shared.computeResearchReport(symbol: symbol))
            } else {
                apply(result)
            }
        } catch let error where Self.isCancellation(error) {
            // The view went away mid-request (push, tab switch). Nothing failed, so let
            // the next `.task` load again instead of showing an error or a stuck spinner.
            started = false
            return
        } catch NetworkError.connectionFailed {
            if let saved = ResearchReportCache.load(symbol: symbol) {
                state = .loaded(saved, savedCopy: true)
            } else {
                state = .error(NetworkError.connectionFailed.errorDescription ?? Self.genericError)
            }
        } catch {
            state = .error((error as? NetworkError)?.errorDescription ?? Self.genericError)
        }
    }

    private func apply(_ result: ResearchFetchResult) {
        switch result {
        case .report(let report):
            ResearchReportCache.save(report, symbol: symbol)
            state = .loaded(report, savedCopy: false)
        case .notCovered:
            // Still no report after an on-demand compute.
            state = .disabled
        case .unknownSymbol:
            state = .unknownSymbol
        case .signedOut:
            state = .signedOut
        case .disabled:
            state = .disabled
        }
    }

    /// `researchCall` rethrows URLError(.cancelled) unmapped; Swift tasks throw CancellationError.
    static func isCancellation(_ error: Error) -> Bool {
        error is CancellationError || (error as? URLError)?.code == .cancelled
    }

    private static let genericError = "Something went wrong. Please try again."
}

/// One JSON file per symbol under Caches/research_reports. Public market data only;
/// the OS may purge it at any time, which simply means no "Saved copy" offline.
enum ResearchReportCache {
    private static var directory: URL? {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("research_reports", isDirectory: true)
    }

    /// Upper-cased, .NS/.BO removed, restricted to the server's symbol alphabet.
    static func fileName(for symbol: String) -> String {
        var key = symbol.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        for suffix in [".NS", ".BO"] where key.hasSuffix(suffix) {
            key.removeLast(suffix.count)
        }
        let allowed = Set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789&-")
        return String(key.filter { allowed.contains($0) }) + ".json"
    }

    static func save(_ report: ResearchReport, symbol: String) {
        guard let dir = directory, let data = try? JSONEncoder().encode(report) else { return }
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try? data.write(to: dir.appendingPathComponent(fileName(for: symbol)), options: .atomic)
    }

    static func load(symbol: String) -> ResearchReport? {
        guard let dir = directory,
              let data = try? Data(contentsOf: dir.appendingPathComponent(fileName(for: symbol))) else { return nil }
        return try? NetworkManager.researchDecoder().decode(ResearchReport.self, from: data)
    }
}
