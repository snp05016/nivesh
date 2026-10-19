import SwiftUI
import Combine

/// Drives the Holdings corporate-action banner and review sheet.
///
/// A 404 FEATURE_DISABLED (flag off for this user) hides everything; any other load failure is
/// silent. NOT_FOUND or INVALID_STATE on a decision means the list is stale, so it reloads.
@MainActor
final class CorporateActionsViewModel: ObservableObject {
    @Published private(set) var items: [CorporateActionItem]
    @Published private(set) var isHidden = false
    @Published private(set) var isWorking = false
    @Published var errorMessage: String? = nil

    /// Called after a decision changed a holding, so the screen reloads its holdings.
    var onHoldingsChanged: (() -> Void)? = nil

    init(items: [CorporateActionItem] = []) {
        self.items = items
    }

    /// Only pending items need the user; decided ones stay visible in the sheet for Undo.
    var pendingCount: Int { items.filter { $0.isPending }.count }

    static func isFeatureDisabled(_ error: Error) -> Bool {
        if case NetworkError.fetchFailed(_, let status, let body) = error {
            return status == 404 && body.contains("FEATURE_DISABLED")
        }
        return false
    }

    private static func isStale(_ error: Error) -> Bool {
        if case NetworkError.fetchFailed(_, let status, let body) = error {
            return (status == 404 && body.contains("NOT_FOUND")) || (status == 409 && body.contains("INVALID_STATE"))
        }
        return false
    }

    func load() async {
        do {
            items = try await NetworkManager.shared.fetchCorporateActions()
            isHidden = false
        } catch {
            if Self.isFeatureDisabled(error) {
                items = []
                isHidden = true
            }
        }
    }

    func apply(_ item: CorporateActionItem) async { await mutate(item, .apply) }
    func dismiss(_ item: CorporateActionItem) async { await mutate(item, .dismiss) }
    func undo(_ item: CorporateActionItem) async { await mutate(item, .undo) }

    private func mutate(_ item: CorporateActionItem, _ action: CorporateActionMutation) async {
        guard !isWorking else { return }
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            let response = try await NetworkManager.shared.mutateCorporateAction(id: item.id, action: action)
            if let index = items.firstIndex(where: { $0.id == response.item.id }) {
                items[index] = response.item
            }
            if response.holding != nil { onHoldingsChanged?() }
        } catch {
            if Self.isFeatureDisabled(error) {
                items = []
                isHidden = true
                return
            }
            errorMessage = "Couldn't update this holding. Try again."
            if Self.isStale(error) { await load() }
        }
    }
}
