import Foundation
import Combine

/// One holding's detail page (C11). Read-only: nothing here starts an analysis or calls an LLM.
@MainActor
final class HoldingDetailViewModel: ObservableObject {
    enum State: Equatable {
        case loading, loaded, notHeld, offline
        case failed(String)
    }

    @Published private(set) var state: State = .loading
    /// Last good payload; kept through an offline or failed refresh, dropped when not held.
    @Published private(set) var detail: HoldingDetailResponse?

    let ticker: String
    private let fetch: (String) async throws -> HoldingDetailResponse

    init(ticker: String,
         fetch: @escaping (String) async throws -> HoldingDetailResponse = { try await NetworkManager.shared.fetchHoldingDetail(ticker: $0) }) {
        self.ticker = ticker
        self.fetch = fetch
    }

    func load() async {
        if detail == nil { state = .loading }
        do {
            detail = try await fetch(ticker)
            state = .loaded
        } catch is CancellationError {
        } catch let e as URLError where e.code == .cancelled {
        } catch {
            let next = Self.state(for: error)
            if next == .notHeld { detail = nil }
            if Self.isFeatureDisabled(error) {
                // A stale cached flag routed here; refresh so the next tap uses the old screen.
                Task { await FeatureFlags.shared.refresh(force: true) }
            }
            state = next
        }
    }

    /// 404 NOT_HELD -> notHeld, transport failure (status < 0) -> offline, anything else -> failed.
    static func state(for error: Error) -> State {
        if case .fetchFailed(_, let status, _)? = error as? NetworkError {
            if status == 404 && !isFeatureDisabled(error) { return .notHeld }
            if status < 0 { return .offline }
        }
        return .failed((error as? NetworkError)?.errorDescription ?? error.localizedDescription)
    }

    static func isFeatureDisabled(_ error: Error) -> Bool {
        guard case .fetchFailed(_, 404, let body)? = error as? NetworkError else { return false }
        return body.contains("FEATURE_DISABLED")
    }
}
