import Foundation
import Combine

/// User copy for Lab failures. 403/404 on a Lab route means the `research_lab`
/// flag is off server-side (or the route is not deployed yet).
enum LabErrors {
    static let disabled = "The Lab isn't available on your account yet."

    static func isCancellation(_ error: Error) -> Bool {
        error is CancellationError || (error as? URLError)?.code == .cancelled
    }

    static func message(_ error: Error) -> String {
        if case NetworkError.serverError(let status, _) = error, status == 403 || status == 404 { return disabled }
        return (error as? NetworkError)?.errorDescription ?? "Something went wrong. Please try again."
    }
}

/// One read-only screen load: LoadPhase-driven, cancellable on disappear, retryable.
/// Views: `.onAppear { vm.loadIfNeeded() }`, `.onDisappear { vm.cancel() }`, StateCard(onRetry: vm.load).
@MainActor
final class LabLoadViewModel<Value>: ObservableObject {
    @Published private(set) var value: Value?
    @Published private(set) var isLoading = false
    @Published private(set) var error: String?

    private let fetch: () async throws -> Value
    private let isEmpty: (Value) -> Bool
    private var task: Task<Void, Never>?

    init(initial: Value? = nil, isEmpty: @escaping (Value) -> Bool = { _ in false },
         fetch: @escaping () async throws -> Value) {
        self.value = initial
        self.fetch = fetch
        self.isEmpty = isEmpty
    }

    var phase: LoadPhase {
        LoadPhase.resolve(isLoading: isLoading, hasLoaded: value != nil, isEmpty: value.map(isEmpty) ?? false,
                          error: error, isOnline: ConnectivityMonitor.shared.isOnline)
    }

    func loadIfNeeded() {
        guard value == nil, !isLoading else { return }
        load()
    }

    func load() {
        task?.cancel()
        isLoading = true
        task = Task { [weak self] in await self?.run() }
    }

    func cancel() {
        task?.cancel()
        task = nil
        isLoading = false
    }

    private func run() async {
        do {
            let fresh = try await fetch()
            guard !Task.isCancelled else { return }
            value = fresh
            error = nil
        } catch where LabErrors.isCancellation(error) {
            return
        } catch {
            self.error = LabErrors.message(error)
        }
        isLoading = false
    }
}
