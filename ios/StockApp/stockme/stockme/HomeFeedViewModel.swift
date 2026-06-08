import SwiftUI
import Combine

class HomeFeedViewModel: ObservableObject {
    @Published var feed: HomeFeedResponse? = nil
    @Published var isLoading = false
    @Published var lastFetchDate: Date? = nil
    private var fetchTask: Task<Void, Never>?
    private var backgroundTimer: Timer?

    func fetch(userId: Int, forceRefresh: Bool = false) {
        if !forceRefresh, let last = lastFetchDate, Date().timeIntervalSince(last) < 900 { return }
        // Fix 3.2: Minimum 10-second debounce between refreshes
        if forceRefresh, let last = lastFetchDate, Date().timeIntervalSince(last) < 10 { return }
        fetchTask?.cancel()
        isLoading = true

        fetchTask = Task {
            do {
                let response = try await HomeFeedService.shared.fetchFeed(userId: userId)
                guard !Task.isCancelled else { return }
                await MainActor.run {
                    self.feed = response
                    self.isLoading = false
                    self.lastFetchDate = Date()
                }
            } catch {
                guard !Task.isCancelled else { return }
                await MainActor.run { self.isLoading = false }
            }
        }
    }

    /// Fix 3.18: Suspend all background polling timers and tasks.
    func suspendAllPolling() {
        backgroundTimer?.invalidate()
        backgroundTimer = nil
        fetchTask?.cancel()
        fetchTask = nil
    }

    func resumePolling(userId: Int) {
        fetch(userId: userId, forceRefresh: true)
    }
}
