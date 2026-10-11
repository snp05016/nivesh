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
        async let accountsResult = NetworkManager.shared.fetchLinkedAccounts()
        async let summaryResult = NetworkManager.shared.fetchFinanceSummary()
        async let categoriesResult = NetworkManager.shared.fetchSpendCategories()

        // Each call fails independently; a failed part keeps its previous
        // value instead of being replaced by zeros that look like real data.
        var failedParts = 0
        do { accounts = try await accountsResult } catch { failedParts += 1 }
        do { summary = try await summaryResult } catch { failedParts += 1 }
        do { spendCategories = try await categoriesResult } catch { failedParts += 1 }

        if failedParts == 3 {
            errorMessage = "Couldn't load your finance overview. Pull to retry."
        } else if failedParts > 0 {
            errorMessage = "Some finance data couldn't load. Pull to retry."
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
