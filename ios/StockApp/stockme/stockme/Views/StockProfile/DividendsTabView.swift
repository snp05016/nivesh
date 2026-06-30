import SwiftUI

// MARK: - Dividend Models

struct DividendData: Codable {
    let ticker: String?
    let next_ex_date: String?
    let dividends: [DividendEntry]?
}

struct DividendEntry: Codable, Identifiable {
    var id: String { date ?? UUID().uuidString }
    let date: String?
    let amount: Double?
    let yield_pct: Double?
}

// MARK: - Dividends Tab

struct DividendsTabView: View {
    let ticker: String
    @State private var dividendData: DividendData?
    @State private var isLoading = true
    @State private var loadError: String?

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.card) {
                Text("DIVIDEND HISTORY")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, Theme.Spacing.small)

                if isLoading {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .frame(maxWidth: .infinity)
                        .padding(Theme.Spacing.xLarge)
                        .banknoteCard()
                } else if let error = loadError {
                    SPEmptyStateView(message: error)
                } else if let data = dividendData {
                    if let nextDate = data.next_ex_date {
                        NextDividendCardView(nextExDate: nextDate)
                    }

                    if let entries = data.dividends, !entries.isEmpty {
                        DividendHistoryListView(entries: entries)
                    } else {
                        SPEmptyStateView(message: "No dividend history available")
                    }
                } else {
                    SPEmptyStateView(message: "No dividend history available")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task {
            isLoading = true
            loadError = nil
            do {
                dividendData = try await NetworkManager.shared.fetchDividends(ticker: ticker)
            } catch {
                loadError = "Could not load dividend data"
            }
            isLoading = false
        }
    }
}

// MARK: - Next Ex-Dividend Card

struct NextDividendCardView: View {
    let nextExDate: String

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("NEXT EX-DIVIDEND DATE")
                .font(Theme.officialStampFont(size: 8))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: "calendar.badge.clock")
                    .font(.title2)
                    .foregroundStyle(Theme.bullGreen)

                Text(formatDate(nextExDate))
                    .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                    .foregroundStyle(Theme.bullGreen)
            }

            Text("Buy before this date to be eligible for the upcoming dividend")
                .font(Theme.engravedSerif(size: 10, weight: .regular, relativeTo: .caption2))
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
                .lineSpacing(2)
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func formatDate(_ dateStr: String) -> String {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        if let date = iso.date(from: dateStr) {
            let df = DateFormatter()
            df.dateFormat = "dd MMM yyyy"
            return df.string(from: date)
        }
        let fallback = DateFormatter()
        fallback.dateFormat = "yyyy-MM-dd"
        if let date = fallback.date(from: dateStr) {
            let df = DateFormatter()
            df.dateFormat = "dd MMM yyyy"
            return df.string(from: date)
        }
        return dateStr
    }
}

// MARK: - Dividend History List

struct DividendHistoryListView: View {
    let entries: [DividendEntry]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PAST DIVIDENDS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            VStack(spacing: Theme.Spacing.xSmall) {
                ForEach(Array(entries.enumerated()), id: \.element.id) { idx, entry in
                    DividendRowView(entry: entry)
                    if idx < entries.count - 1 {
                        Rectangle()
                            .fill(Theme.borderFine)
                            .frame(height: 0.5)
                            .padding(.horizontal, Theme.Spacing.card)
                    }
                }
            }
            .banknoteCard()
            .clipped()
        }
    }
}

// MARK: - Dividend Row

struct DividendRowView: View {
    let entry: DividendEntry

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(formatDate(entry.date ?? ""))
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
            }

            Spacer()

            if let amount = entry.amount {
                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text(IndianFormatter.price(amount))
                        .font(Theme.serialNumberFont(size: 13, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("per share")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }

            if let yield = entry.yield_pct {
                Text(String(format: "%.2f%%", yield))
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .callout))
                    .foregroundStyle(yield >= 2.0 ? Theme.bullGreen : Theme.inkSecondary)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.small)
                    .background(yield >= 2.0 ? Theme.bullGreen.opacity(0.08) : Theme.inkTertiary.opacity(0.06))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }

            Image(systemName: "indianrupeesign.circle.fill")
                .font(.body)
                .foregroundStyle(Theme.bullGreen.opacity(0.6))
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }

    private func formatDate(_ dateStr: String) -> String {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        if let date = iso.date(from: dateStr) {
            let df = DateFormatter()
            df.dateFormat = "dd MMM yyyy"
            return df.string(from: date)
        }
        let fallback = DateFormatter()
        fallback.dateFormat = "yyyy-MM-dd"
        if let date = fallback.date(from: dateStr) {
            let df = DateFormatter()
            df.dateFormat = "dd MMM yyyy"
            return df.string(from: date)
        }
        return dateStr
    }
}
