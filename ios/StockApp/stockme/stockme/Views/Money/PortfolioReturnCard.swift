import SwiftUI

/// I30 (spec 3.3): the portfolio's money-weighted return next to the same cash flows in the
/// Nifty 50. Hidden on any error (404 no holdings, 503 nothing priced, transport failure)
/// until the next successful load; `reloadKey` changes whenever the portfolio reloads.
struct PortfolioReturnCard: View {
    let userId: Int
    var reloadKey = 0
    @AppStorage("nivesh_hidePortfolioValues") private var hideValues = false
    @State private var data: PortfolioReturnDTO?
    @State private var hidden = false

    var body: some View {
        // The container stays mounted while the card is hidden, so its task can bring it back.
        VStack(spacing: Theme.Spacing.none) {
            if !hidden {
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    HoldingSectionTitle(text: "YOUR RETURN")
                    if let data {
                        ReturnCopyLines(copy: MoneyReturnCopy.portfolio(data, masked: hideValues))
                    } else {
                        HStack(spacing: Theme.Spacing.medium) {
                            ProgressView().tint(Theme.securityGold)
                            Text("Working out your return…")
                                .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(Theme.Spacing.card)
                .banknoteCard()
            }
        }
        // Runs on every appearance and on each portfolio reload (first holding, trade, pull to refresh).
        .task(id: [userId, reloadKey]) { await load() }
    }

    private func load() async {
        do {
            data = try await NetworkManager.shared.fetchPortfolioReturn(userId: userId)
            hidden = false
        } catch is CancellationError {
        } catch let e as URLError where e.code == .cancelled {
        } catch {
            hidden = true
        }
    }
}
