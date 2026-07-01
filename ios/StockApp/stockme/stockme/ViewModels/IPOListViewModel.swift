import SwiftUI
import Combine

/// Drives IPOHubView — fetches and tab-filters the IPO list, and polls the
/// open-tab list periodically so subscription figures stay live during market hours.
@MainActor
class IPOListViewModel: ObservableObject {
    @Published var allIPOs: [IPOListing] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    private var pollTimer: AnyCancellable?

    init() {
        fetchIPOs()
    }

    deinit {
        pollTimer?.cancel()
    }

    func ipos(for status: IPOStatus) -> [IPOListing] {
        allIPOs.filter { $0.status == status }
    }

    func fetchIPOs(isBackground: Bool = false) {
        if !isBackground { isLoading = true }
        errorMessage = nil

        Task {
            do {
                let ipos = try await NetworkManager.shared.getIPOList()
                self.allIPOs = ipos
                if !isBackground { self.isLoading = false }
            } catch {
                if !isBackground {
                    self.errorMessage = "Couldn't load IPOs. Pull to retry."
                    self.isLoading = false
                }
            }
        }
    }

    /// Polls the list every 30s so "times subscribed" figures on open IPOs stay fresh.
    func startLiveUpdates() {
        pollTimer?.cancel()
        pollTimer = Timer.publish(every: 30.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.fetchIPOs(isBackground: true)
            }
    }

    func stopLiveUpdates() {
        pollTimer?.cancel()
        pollTimer = nil
    }
}
