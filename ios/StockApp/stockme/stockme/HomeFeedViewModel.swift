import SwiftUI
import Combine

class HomeFeedViewModel: ObservableObject {
    @Published var feed: HomeFeedResponse? = nil
    @Published var isLoading = false
    @Published var lastFetchDate: Date? = nil
    private var fetchTask: Task<Void, Never>?

    func fetch(userId: Int, forceRefresh: Bool = false) {
        if !forceRefresh, let last = lastFetchDate, Date().timeIntervalSince(last) < 900 { return }
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
}
