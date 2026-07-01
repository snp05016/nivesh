import SwiftUI
import Combine

/// Drives the per-IPO detail screen — fetches full IPO detail plus a live-polled
/// subscription snapshot (QIB / NII / Retail times subscribed).
@MainActor
class IPODetailViewModel: ObservableObject {
    @Published var listing: IPOListing?
    @Published var subscription: IPOSubscriptionDetail?
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    private let ipoId: String
    private var pollTimer: AnyCancellable?

    init(ipoId: String, seed: IPOListing? = nil) {
        self.ipoId = ipoId
        self.listing = seed
        self.subscription = nil
    }

    deinit {
        pollTimer?.cancel()
    }

    /// Fetches the IPO detail and its subscription snapshot together. `IPOListing` (the
    /// detail response) carries no subscription fields — those live only on the dedicated
    /// `/subscription-status` endpoint — so both calls are issued concurrently here.
    func fetchDetail() {
        isLoading = listing == nil
        errorMessage = nil

        Task {
            do {
                async let detailTask = NetworkManager.shared.getIPODetail(id: ipoId)
                async let subscriptionTask: IPOSubscriptionDetail? = try? NetworkManager.shared.getIPOSubscription(id: ipoId)
                let detail = try await detailTask
                self.listing = detail
                self.subscription = await subscriptionTask
                self.isLoading = false
            } catch {
                self.errorMessage = "Couldn't load IPO details. Pull to retry."
                self.isLoading = false
            }
        }
    }

    /// Live-polls subscription figures every 20s — only meaningful while the IPO is open.
    func startLiveSubscriptionUpdates() {
        guard listing?.status == .open else { return }
        pollTimer?.cancel()
        pollTimer = Timer.publish(every: 20.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.refreshSubscription()
            }
    }

    func stopLiveSubscriptionUpdates() {
        pollTimer?.cancel()
        pollTimer = nil
    }

    private func refreshSubscription() {
        Task {
            if let updated = try? await NetworkManager.shared.getIPOSubscription(id: ipoId) {
                self.subscription = updated
            }
        }
    }
}
