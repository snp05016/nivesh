import SwiftUI

// MARK: - Personal Finance Tracker
//
// MOCK DATA - simulated for demo purposes, not a real integration. All
// linked accounts, balances and spend categories shown here come from a
// mock backend surface (see NetworkManager+Finance.swift) — there is no
// real bank-linking OAuth/Plaid flow behind "Link Account (Demo)".

struct FinanceTrackerView: View {
    @StateObject private var vm = FinanceViewModel()
    @State private var showLinkAccountSheet = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                FinanceTrackerHeader()

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                if vm.isLoading && vm.accounts.isEmpty {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .frame(maxWidth: .infinity, minHeight: 160)
                } else if let error = vm.errorMessage, vm.accounts.isEmpty {
                    FinanceErrorState(message: error) { Task { await vm.loadAll() } }
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    if let error = vm.errorMessage {
                        FinancePartialErrorBanner(message: error)
                            .padding(.horizontal, Theme.screenPadding)
                    }

                    FinanceBalanceSummaryCard(summary: vm.summary)
                        .padding(.horizontal, Theme.screenPadding)

                    FinanceLinkedAccountsSection(accounts: vm.accounts) {
                        HapticManager.selection()
                        showLinkAccountSheet = true
                    }

                    FinanceSpendCategorySection(categories: vm.spendCategories)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Finance Tracker")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.loadAll() }
        .refreshable { await vm.loadAll() }
        .sheet(isPresented: $showLinkAccountSheet) {
            LinkAccountDemoSheet(vm: vm)
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
        }
    }
}

// MARK: - Header

struct FinanceTrackerHeader: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Finance Tracker")
                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                .foregroundColor(Theme.inkPrimary)

            Text("A single view of every linked account and where your money goes.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)

            FinanceMockBadge()
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Small badge clarifying this whole screen is demo/mock data — no real
/// bank linking happens anywhere in this feature.
struct FinanceMockBadge: View {
    var body: some View {
        Text("DEMO DATA · NO REAL BANK LINK")
            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
            .tracking(1.2)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .foregroundColor(Theme.holdAmber)
            .background(Theme.holdAmber.opacity(0.12))
            .cornerRadius(Theme.CornerRadius.badge)
    }
}

// MARK: - Balance Summary

struct FinanceBalanceSummaryCard: View {
    let summary: FinanceSummaryDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("NET BALANCE")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)

            Text(summary.totalBalanceDisplay)
                .font(Theme.dataXL())
                .foregroundColor(Theme.inkPrimary)

            GuillocheDivider()

            HStack(spacing: Theme.Spacing.large) {
                FinanceStatColumn(label: "Linked Accounts", value: "\(summary.linkedAccountCount)")
                FinanceStatColumn(label: "Monthly Income", value: summary.monthlyIncomeDisplay, valueColor: Theme.bullGreen)
                FinanceStatColumn(label: "Monthly Spend", value: summary.monthlySpendDisplay, valueColor: Theme.bearRed)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct FinanceStatColumn: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(valueColor)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Linked Accounts

struct FinanceLinkedAccountsSection: View {
    let accounts: [LinkedBankAccountDTO]
    let onLinkAccount: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            HStack {
                Text("LINKED ACCOUNTS")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Button(action: onLinkAccount) {
                    Label("Link Account (Demo)", systemImage: "plus.circle.fill")
                        .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                        .foregroundColor(Theme.securityGold)
                }
                .buttonStyle(EKPressStyle())
            }
            .padding(.horizontal, Theme.screenPadding)

            if accounts.isEmpty {
                FinanceEmptyAccountsState(onLinkAccount: onLinkAccount)
                    .padding(.horizontal, Theme.screenPadding)
            } else {
                VStack(spacing: Theme.Spacing.standard) {
                    ForEach(accounts) { account in
                        LinkedAccountRowCard(account: account)
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
}

struct LinkedAccountRowCard: View {
    let account: LinkedBankAccountDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.canvasShadow)
                .frame(width: 44, height: 44)
                .overlay(
                    Image(systemName: account.parsedAccountType.icon)
                        .foregroundColor(Theme.inkPrimary)
                )

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(account.bankName)
                    .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                Text("\(account.parsedAccountType.displayName) · \(account.maskedAccountNumber)")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.0)
                    .foregroundColor(Theme.inkSecondary)
            }

            Spacer()

            Text(account.balanceDisplay)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct FinanceEmptyAccountsState: View {
    let onLinkAccount: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text("No Accounts Linked Yet")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Text("Link a demo account to see a mock balance and spend breakdown.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
            Button(action: onLinkAccount) {
                Text("Link Account (Demo)")
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Spend Categorization (placeholder)

struct FinanceSpendCategorySection: View {
    let categories: [SpendCategoryDTO]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("SPEND BY CATEGORY")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, Theme.screenPadding)

            if categories.isEmpty {
                Text("Spend categorization will appear here once transactions sync.")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundColor(Theme.inkTertiary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity, minHeight: 100)
                    .padding(Theme.Spacing.card)
                    .banknoteCard()
                    .padding(.horizontal, Theme.screenPadding)
            } else {
                VStack(spacing: Theme.Spacing.standard) {
                    ForEach(categories) { category in
                        SpendCategoryRow(category: category)
                    }
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
}

private struct SpendCategoryRow: View {
    let category: SpendCategoryDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                Text(category.category)
                    .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .subheadline))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                Text(category.amountDisplay)
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundColor(Theme.inkSecondary)
            }
            ProgressView(value: min(max(category.percentage / 100, 0), 1))
                .tint(Theme.securityGold)
        }
    }
}

// MARK: - Error State

/// Inline banner shown above real data when only some finance calls failed,
/// so a stale or missing figure is never mistaken for a real balance.
struct FinancePartialErrorBanner: View {
    let message: String

    var body: some View {
        Label(message, systemImage: "exclamationmark.triangle.fill")
            .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
            .foregroundColor(Theme.bearRed)
            .padding(Theme.Spacing.medium)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.bearRed.opacity(0.1))
            .cornerRadius(Theme.CornerRadius.badge)
    }
}

struct FinanceErrorState: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text(message)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
                .multilineTextAlignment(.center)
            Button {
                HapticManager.selection()
                retry()
            } label: {
                Text("Retry")
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity, minHeight: 160)
    }
}

private struct FinanceAccountTypeChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            Text(label)
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .tracking(1.0)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.small)
                .background(isSelected ? Theme.inkPrimary : Color.clear)
                .foregroundColor(isSelected ? Theme.canvas : Theme.inkSecondary)
                .cornerRadius(Theme.CornerRadius.badge)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.badge)
                        .stroke(Theme.borderFine, lineWidth: isSelected ? 0 : 1)
                )
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - Link Account (Demo) Sheet

struct LinkAccountDemoSheet: View {
    @ObservedObject var vm: FinanceViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var bankName: String = "Nivesh Demo Bank"
    @State private var accountType: LinkedAccountType = .savings

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    FinanceMockBadge()

                    Text("This creates a fabricated demo account with a randomly-generated mock balance. No real bank credentials, OAuth, or Plaid-style linking is involved.")
                        .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                        .foregroundColor(Theme.inkSecondary)

                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("DEMO BANK NAME")
                            .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                            .tracking(1.5)
                            .foregroundColor(Theme.inkSecondary)
                        TextField("Bank name", text: $bankName)
                            .font(Theme.serialNumberFont(size: 14))
                            .foregroundColor(Theme.inkPrimary)
                            .padding(Theme.Spacing.standard)
                            .banknoteCard()
                    }

                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("ACCOUNT TYPE")
                            .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                            .tracking(1.5)
                            .foregroundColor(Theme.inkSecondary)
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: Theme.Spacing.standard) {
                                ForEach(LinkedAccountType.allCases, id: \.self) { type in
                                    FinanceAccountTypeChip(label: type.displayName, isSelected: accountType == type) {
                                        accountType = type
                                    }
                                }
                            }
                        }
                    }

                    if let error = vm.linkAccountError {
                        Text(error)
                            .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                            .foregroundColor(Theme.bearRed)
                    }

                    Button {
                        HapticManager.selection()
                        Task {
                            await vm.linkAccountDemo(bankName: bankName, accountType: accountType)
                            if vm.linkAccountError == nil { dismiss() }
                        }
                    } label: {
                        HStack {
                            Spacer()
                            if vm.isLinkingAccount {
                                ProgressView().tint(Theme.canvas)
                            } else {
                                Text("Link Account (Demo)")
                                    .font(Theme.labelStyle)
                            }
                            Spacer()
                        }
                        .padding(Theme.Spacing.card)
                        .background(Theme.securityGold)
                        .foregroundColor(Theme.canvas)
                        .cornerRadius(Theme.CornerRadius.medium)
                    }
                    .buttonStyle(EKPressStyle())
                    .disabled(vm.isLinkingAccount || bankName.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Link Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
    }
}
