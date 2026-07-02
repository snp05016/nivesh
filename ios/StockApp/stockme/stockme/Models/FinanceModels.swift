import Foundation

// MARK: - Personal Finance Tracker Domain Models
//
// MOCK DATA - simulated for demo purposes, not a real integration.
// No real NBFC / bank / credit-bureau APIs are wired here. All linked
// accounts, balances and spend categories below are produced by a mock
// backend endpoint (POST /api/finance/accounts/link-demo) that fabricates
// plausible-looking data — there is no OAuth/Plaid-style bank-linking flow
// and no real account numbers are ever collected or stored (only a
// last-4-digit masked display string).
//
// Mirrors the (mock) backend/routers/finance.py FinanceAccountResponse /
// FinanceSummaryResponse shapes — see NetworkManager+Finance.swift for the
// exact endpoints these are decoded from.

/// Broad account categories a demo "linked" account can fall under.
enum LinkedAccountType: String, Codable, CaseIterable {
    case savings = "savings"
    case current = "current"
    case creditCard = "credit_card"
    case wallet = "wallet"

    var displayName: String {
        switch self {
        case .savings: return "Savings"
        case .current: return "Current"
        case .creditCard: return "Credit Card"
        case .wallet: return "Wallet"
        }
    }

    var icon: String {
        switch self {
        case .savings: return "banknote.fill"
        case .current: return "building.columns.fill"
        case .creditCard: return "creditcard.fill"
        case .wallet: return "wallet.pass.fill"
        }
    }
}

/// A single mock "linked" bank account row.
/// MOCK DATA - simulated for demo purposes, not a real integration.
struct LinkedBankAccountDTO: Codable, Identifiable, Equatable {
    let id: Int
    let bankName: String
    let accountType: String
    let maskedAccountNumber: String
    let balance: Double
    let lastSyncedAt: String?
    let isMock: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case bankName = "bank_name"
        case accountType = "account_type"
        case maskedAccountNumber = "masked_account_number"
        case balance
        case lastSyncedAt = "last_synced_at"
        case isMock = "is_mock"
    }

    var parsedAccountType: LinkedAccountType {
        LinkedAccountType(rawValue: accountType) ?? .savings
    }

    var balanceDisplay: String {
        IndianFormatter.formatLakhsCrores(balance)
    }
}

/// Aggregate balance summary across every linked (mock) account.
/// Mirrors GET /api/finance/summary.
struct FinanceSummaryDTO: Codable, Equatable {
    let totalBalance: Double
    let linkedAccountCount: Int
    let monthlyIncome: Double
    let monthlySpend: Double

    enum CodingKeys: String, CodingKey {
        case totalBalance = "total_balance"
        case linkedAccountCount = "linked_account_count"
        case monthlyIncome = "monthly_income"
        case monthlySpend = "monthly_spend"
    }

    var totalBalanceDisplay: String { IndianFormatter.formatLakhsCrores(totalBalance) }
    var monthlyIncomeDisplay: String { IndianFormatter.formatLakhsCrores(monthlyIncome) }
    var monthlySpendDisplay: String { IndianFormatter.formatLakhsCrores(monthlySpend) }

    static let empty = FinanceSummaryDTO(totalBalance: 0, linkedAccountCount: 0, monthlyIncome: 0, monthlySpend: 0)
}

/// A single spend-categorization slice (placeholder — not backed by real
/// transaction categorization ML, just a mock proportional breakdown).
/// Mirrors GET /api/finance/spend-categories.
struct SpendCategoryDTO: Codable, Identifiable, Equatable {
    var id: String { category }
    let category: String
    let amount: Double
    let percentage: Double

    enum CodingKeys: String, CodingKey {
        case category
        case amount
        case percentage
    }

    var amountDisplay: String { IndianFormatter.formatLakhsCrores(amount) }
}

/// Request body for POST /api/finance/accounts/link-demo — the "Link Account
/// (Demo)" button. No real bank credentials are ever collected; this simply
/// asks the mock backend to fabricate a new demo account of the chosen type.
/// MOCK DATA - simulated for demo purposes, not a real integration.
struct LinkAccountDemoRequest: Codable {
    let bankName: String
    let accountType: String

    enum CodingKeys: String, CodingKey {
        case bankName = "bank_name"
        case accountType = "account_type"
    }
}
