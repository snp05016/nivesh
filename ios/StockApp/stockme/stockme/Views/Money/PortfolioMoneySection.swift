import SwiftUI

/// Flag-gated money rows under the portfolio hero (spec 2.6). Later money packages
/// (CAS import, X-ray, tax) append their rows here; each row hides itself when off.
struct PortfolioMoneySection: View {
    let userId: Int
    /// Bumped by PortfolioScreen after each portfolio load so money rows re-fetch.
    var reloadKey = 0
    @ObservedObject private var flags = FeatureFlags.shared

    var body: some View {
        if flags.isOn(.moneyXirrCard) {
            PortfolioReturnCard(userId: userId, reloadKey: reloadKey)
        }
    }
}
