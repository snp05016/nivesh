import Foundation
import Combine

/// Drives TimeMachineSessionView: the replayed session plus append-only actions.
/// Loads cancel on disappear; an action in flight is never cancelled (the backend
/// is idempotent on `client_action_id`, and a cancelled POST could leave the screen stale).
@MainActor
final class LabSessionViewModel: ObservableObject {
    @Published private(set) var session: LabSession?
    @Published private(set) var isLoading = false
    @Published private(set) var loadError: String?
    @Published private(set) var isSending = false
    /// Last rejected action, shown inline (422 detail is user-safe by contract).
    @Published var actionError: String?
    /// Hindsight material, fetched only once the session has finished.
    @Published private(set) var debrief: LabScenario?
    @Published private(set) var review: LabAutopsyReport?

    let sessionId: String
    private var loadTask: Task<Void, Never>?
    private var reviewLoaded = false

    init(sessionId: String) {
        self.sessionId = sessionId
    }

    var phase: LoadPhase {
        LoadPhase.resolve(isLoading: isLoading, hasLoaded: session != nil, isEmpty: false,
                          error: loadError, isOnline: ConnectivityMonitor.shared.isOnline)
    }

    var state: LabSimState? { session?.state }
    var isFinished: Bool { state?.finished == true }
    var warnings: [String] { session?.provenance?.warnings ?? [] }

    func loadIfNeeded() {
        guard session == nil, !isLoading else { return }
        load()
    }

    func load() {
        loadTask?.cancel()
        isLoading = true
        loadTask = Task { [weak self] in await self?.runLoad() }
    }

    func cancel() {
        loadTask?.cancel()
        loadTask = nil
        isLoading = false
    }

    private func runLoad() async {
        do {
            let fresh = try await NetworkManager.shared.labSession(id: sessionId)
            guard !Task.isCancelled else { return }
            apply(fresh)
            loadError = nil
        } catch where LabErrors.isCancellation(error) {
            return
        } catch {
            loadError = LabErrors.message(error)
        }
        isLoading = false
    }

    /// Sends one action; returns true when the replay accepted it.
    @discardableResult
    func send(_ action: LabAction) async -> Bool {
        guard !isSending else { return false }
        isSending = true
        actionError = nil
        defer { isSending = false }
        do {
            let reply = try await NetworkManager.shared.labPostAction(sessionId: sessionId, action: action,
                                                                      clientActionId: UUID().uuidString)
            let fresh: LabSession
            if let reply { fresh = reply } else { fresh = try await NetworkManager.shared.labSession(id: sessionId) }
            apply(fresh)
            HapticManager.success()
            return true
        } catch {
            actionError = LabErrors.message(error)
            HapticManager.warning()
            return false
        }
    }

    func advance(days: Int) async { await send(.advance(days: days)) }
    func cancelOrder(_ id: String) async { await send(.cancel(orderId: id)) }

    private func apply(_ fresh: LabSession) {
        session = fresh
        if fresh.state?.finished == true, !reviewLoaded {
            reviewLoaded = true
            Task { await loadReview(scenarioId: fresh.scenarioId) }
        }
    }

    /// Debrief (scenario hindsight) and whole-session behaviour review. Best effort:
    /// a failure leaves those sections out rather than failing the session screen.
    private func loadReview(scenarioId: String?) async {
        if let scenarioId, let catalog = try? await NetworkManager.shared.labScenarios() {
            debrief = catalog.scenarios?.first { $0.id == scenarioId }
        }
        review = try? await NetworkManager.shared.labAutopsy(sessionId: sessionId, orderId: nil)
    }
}

/// One mentor exchange.
struct LabMentorExchange: Identifiable, Hashable {
    let id = UUID()
    let question: String
    var reply: LabMentorReply?
    var error: String?
}

@MainActor
final class LabMentorViewModel: ObservableObject {
    @Published private(set) var exchanges: [LabMentorExchange] = []
    @Published private(set) var isAsking = false
    @Published var draft = ""

    let sessionId: String
    let orderId: String?

    init(sessionId: String, orderId: String?) {
        self.sessionId = sessionId
        self.orderId = orderId
    }

    var canAsk: Bool { !isAsking && draft.trimmingCharacters(in: .whitespacesAndNewlines).count >= 3 }

    func ask() async {
        let question = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard canAsk else { return }
        draft = ""
        isAsking = true
        defer { isAsking = false }
        var exchange = LabMentorExchange(question: question)
        do {
            exchange.reply = try await NetworkManager.shared.labMentor(sessionId: sessionId, question: question, orderId: orderId)
        } catch where LabErrors.isCancellation(error) {
            draft = question
            return
        } catch {
            exchange.error = LabErrors.message(error)
        }
        exchanges.append(exchange)
    }
}
