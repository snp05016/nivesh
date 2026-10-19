import SwiftUI

/// Flag-gated money rows under the portfolio hero (spec 2.6). Later money packages
/// (tax) append their rows here; each row hides itself when off.
struct PortfolioMoneySection: View {
    let userId: Int
    /// Bumped by PortfolioScreen after each portfolio load so money rows re-fetch.
    var reloadKey = 0
    @ObservedObject private var flags = FeatureFlags.shared

    var body: some View {
        if flags.isOn(.moneyXirrCard) {
            PortfolioReturnCard(userId: userId, reloadKey: reloadKey)
        }
        if flags.isOn(.moneyCasImport) {
            CASImportRows()
        }
        if flags.isOn(.moneyXray) {
            XRayRow()
        }
    }
}

/// "Import mutual funds (CAS)" and "Your imports". Exists only while money_cas_import is on, and
/// opens the import once when onboarding left UserDefaults `nivesh_openCASImport` set.
private struct CASImportRows: View {
    @State private var showImport = false
    @State private var showHistory = false

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            MoneyLinkRow(icon: "square.and.arrow.down", title: "Import mutual funds (CAS)") { showImport = true }
            GuillocheDivider().padding(.horizontal, Theme.Spacing.card)
            MoneyLinkRow(icon: "clock.arrow.circlepath", title: "Your imports") { showHistory = true }
        }
        .banknoteCard()
        .navigationDestination(isPresented: $showImport) { CASImportView() }
        .navigationDestination(isPresented: $showHistory) { ImportHistoryView() }
        .onAppear {
            if CASNotice.consumeOpenOnce(flagOn: FeatureFlags.shared.isOn(.moneyCasImport)) { showImport = true }
        }
    }
}

/// "Portfolio X-ray". Exists only while money_xray is on.
private struct XRayRow: View {
    @State private var showXRay = false

    var body: some View {
        MoneyLinkRow(icon: "chart.bar.doc.horizontal", title: "Portfolio X-ray") { showXRay = true }
            .banknoteCard()
            .navigationDestination(isPresented: $showXRay) { PortfolioXRayView() }
    }
}
