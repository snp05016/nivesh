import Foundation

/// Portfolio X-ray (I28). Read-only; the COVID replay loads only while its flag is on and a failure
/// hides just that card.
@MainActor
final class PortfolioXRayViewModel: ObservableObject {
    enum State: Equatable {
        case loading, loaded, empty, offline
        case failed(String)
    }

    @Published private(set) var state: State = .loading
    @Published private(set) var xray: XRayResponse?
    @Published private(set) var replay: CrisisReplayResponse?

    static let emptyMessage = "Add holdings or import your funds to see an X-ray."

    private let fetchXRay: () async throws -> XRayResponse
    private let fetchReplay: () async throws -> CrisisReplayResponse
    private let replayEnabled: () -> Bool

    init(fetchXRay: @escaping () async throws -> XRayResponse = { try await NetworkManager.shared.fetchXRay() },
         fetchReplay: @escaping () async throws -> CrisisReplayResponse = { try await NetworkManager.shared.fetchCrisisReplay() },
         replayEnabled: @escaping () -> Bool = { FeatureFlags.shared.isOn(.moneyCrisisReplay) }) {
        self.fetchXRay = fetchXRay
        self.fetchReplay = fetchReplay
        self.replayEnabled = replayEnabled
    }

    func load() async {
        if xray == nil { state = .loading }
        do {
            let result = try await fetchXRay()
            xray = result
            state = result.isEmpty ? .empty : .loaded
        } catch is CancellationError {
            return
        } catch let e as URLError where e.code == .cancelled {
            return
        } catch {
            state = Self.state(for: error)
            return
        }
        await loadReplay()
    }

    private func loadReplay() async {
        guard replayEnabled(), state == .loaded else { replay = nil; return }
        do {
            replay = try await fetchReplay()
        } catch {
            replay = nil
        }
    }

    /// Transport failure (status < 0) -> offline; anything else -> failed with friendly copy.
    static func state(for error: Error) -> State {
        if case .fetchFailed(_, let status, _)? = error as? NetworkError, status < 0 { return .offline }
        return .failed((error as? NetworkError)?.errorDescription ?? error.localizedDescription)
    }
}
