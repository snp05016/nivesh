import Foundation
import Network
import Combine

/// IOSCORE-06: device reachability, so screens can say "offline" instead of rendering
/// a failed load as an empty or zero state. Drives the global offline banner (ContentView).
@MainActor
final class ConnectivityMonitor: ObservableObject {
    static let shared = ConnectivityMonitor()

    @Published private(set) var isOnline = true

    private let monitor = NWPathMonitor()

    private init() {
        monitor.pathUpdateHandler = { @Sendable [weak self] path in
            let online = path.status == .satisfied
            Task { @MainActor in self?.isOnline = online }
        }
        monitor.start(queue: DispatchQueue(label: "nivesh.connectivity", qos: .utility))
    }
}
