import SwiftUI
import Combine

/// Drives FinanceTrackerView — fetches mock linked accounts, the balance
/// summary, and the spend-categorization placeholder, mirroring
/// MutualFundViewModel's fetch/error/loading shape. MOCK DATA - simulated
/// for demo purposes, not a real integration.
@MainActor
class FinanceViewModel: ObservableObject {
    @Published var accounts: [LinkedBankAccountDTO] = []
    @Published var summary: FinanceSummaryDTO = .empty
    @Published var spendCategories: [SpendCategoryDTO] = []

    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    @Published var isLinkingAccount: Bool = false
    @Published var linkAccountError: String? = nil

    func loadAll() async {
        isLoading = true
        errorMessage = nil
        async let accountsResult = try? NetworkManager.shared.fetchLinkedAccounts()
        async let summaryResult = try? NetworkManager.shared.fetchFinanceSummary()
        async let categoriesResult = try? NetworkManager.shared.fetchSpendCategories()

        accounts = await accountsResult ?? []
        summary = await summaryResult ?? .empty
        spendCategories = await categoriesResult ?? []

        if accounts.isEmpty && summary == .empty {
            errorMessage = "Couldn't load your finance overview. Pull to retry."
        }
        isLoading = false
    }

    /// "Link Account (Demo)" button action. No real bank OAuth/Plaid flow —
    /// asks the mock backend to fabricate a new demo account.
    func linkAccountDemo(bankName: String, accountType: LinkedAccountType) async {
        isLinkingAccount = true
        linkAccountError = nil
        do {
            let newAccount = try await NetworkManager.shared.linkAccountDemo(bankName: bankName, accountType: accountType)
            accounts.append(newAccount)
            if let refreshed = try? await NetworkManager.shared.fetchFinanceSummary() {
                summary = refreshed
            }
        } catch {
            linkAccountError = "Couldn't link the demo account. Please try again."
        }
        isLinkingAccount = false
    }
}
