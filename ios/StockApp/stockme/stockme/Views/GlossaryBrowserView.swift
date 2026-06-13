import SwiftUI

struct GlossaryBrowserView: View {
    @State private var searchText = ""
    @State private var selectedCategory: TermCategory? = nil
    @AppStorage("glossaryRecentlyViewed") private var recentlyViewedData: Data = Data()
    @State private var recentlyViewed: [String] = []

    private var filteredTerms: [FinanceTerm] {
        let all = selectedCategory.map { FinanceTerms.shared.termsByCategory($0) } ?? FinanceTerms.shared.allTerms()
        if searchText.isEmpty { return all }
        let q = searchText.lowercased()
        return all.filter { $0.term.lowercased().contains(q) || $0.definition.lowercased().contains(q) }
    }

    private var suggestedTerms: [String] {
        ["P/E RATIO", "RSI", "FII", "Signal", "Confidence Score"]
    }

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            VStack(spacing: Theme.Spacing.none) {
                // Search bar
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(Theme.inkTertiary)
                        .font(.subheadline)
                    TextField("Search terms...", text: $searchText)
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                }
                .padding(Theme.Spacing.standard)
                .background(Theme.surfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                .padding(.horizontal, Theme.screenPadding)
                .padding(.vertical, Theme.Spacing.standard)

                // Category chips
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Theme.Spacing.small) {
                        ChipView(label: "All", isSelected: selectedCategory == nil) {
                            HapticManager.selection()
                            selectedCategory = nil
                        }
                        ForEach(TermCategory.allCases, id: \.self) { cat in
                            ChipView(label: cat.rawValue, isSelected: selectedCategory == cat) {
                                HapticManager.selection()
                                selectedCategory = selectedCategory == cat ? nil : cat
                            }
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
                .padding(.bottom, Theme.Spacing.small)

                GuillocheDivider()
                    .padding(.horizontal, Theme.screenPadding)

                // Results
                if filteredTerms.isEmpty {
                    VStack(spacing: Theme.Spacing.standard) {
                        Spacer(minLength: 60)
                        Text("No terms match \"\(searchText)\"")
                            .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkSecondary)
                        Text("Try:")
                            .font(Theme.microLabel())
                            .foregroundStyle(Theme.inkTertiary)
                        HStack(spacing: Theme.Spacing.small) {
                            ForEach(suggestedTerms, id: \.self) { term in
                                Button {
                                    HapticManager.selection()
                                    searchText = term
                                } label: {
                                    Text(term)
                                        .font(Theme.labelStyle)
                                        .foregroundStyle(Theme.securityGold)
                                }
                                .buttonStyle(EKPressStyle())
                            }
                        }
                        Spacer()
                    }
                    .padding(Theme.screenPadding)
                } else {
                    ScrollView {
                        LazyVStack(spacing: Theme.Spacing.tight) {
                            ForEach(filteredTerms, id: \.term) { term in
                                TermRow(entry: term, onTap: { addToRecent(term.term) })
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.vertical, Theme.Spacing.small)
                    }
                }

                // Recently viewed
                if !recentlyViewed.isEmpty, searchText.isEmpty, selectedCategory == nil {
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        GuillocheDivider()
                            .padding(.horizontal, Theme.screenPadding)
                        Text("RECENTLY VIEWED")
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .tracking(1.2)
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, Theme.Spacing.small)

                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: Theme.Spacing.small) {
                                ForEach(recentlyViewed, id: \.self) { term in
                                    if let entry = FinanceTerms.shared.lookup(term) {
                                        ChipView(label: term, isSelected: false) {
                                            HapticManager.selection()
                                        }
                                        .overlay {
                                            // invisible tap-through to show the term
                                        }
                                    }
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                    }
                }
            }
        }
        .crashGuard("GlossaryBrowser")
        .navigationTitle("Glossary")
        .navigationBarTitleDisplayMode(.large)
        .onAppear { loadRecentlyViewed() }
    }

    private func addToRecent(_ term: String) {
        recentlyViewed.removeAll { $0 == term }
        recentlyViewed.insert(term, at: 0)
        if recentlyViewed.count > 10 { recentlyViewed = Array(recentlyViewed.prefix(10)) }
        if let data = try? JSONEncoder().encode(recentlyViewed) {
            recentlyViewedData = data
        }
    }

    private func loadRecentlyViewed() {
        if let decoded = try? JSONDecoder().decode([String].self, from: recentlyViewedData) {
            recentlyViewed = decoded
        }
    }
}

// MARK: - Term Row

private struct TermRow: View {
    let entry: FinanceTerm
    let onTap: () -> Void
    @State private var showSheet = false

    var body: some View {
        Button {
            HapticManager.selection()
            onTap()
            showSheet = true
        } label: {
            HStack(spacing: Theme.Spacing.standard) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(entry.term.uppercased())
                        .font(Theme.officialStampFont(size: 11, relativeTo: .subheadline))
                        .tracking(1)
                        .foregroundStyle(Theme.inkPrimary)
                    Text(entry.definition)
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(2)
                }
                Spacer()
                Text(entry.category.rawValue)
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.horizontal, Theme.Spacing.small)
                    .padding(.vertical, 2)
                    .background(Theme.inkTertiary.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                Image(systemName: "chevron.right")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showSheet) {
            TermDefinitionSheet(entry: entry)
        }
    }
}

// MARK: - Chip View

private struct ChipView: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(Theme.labelStyle)
                .foregroundStyle(isSelected ? Theme.canvas : Theme.inkPrimary)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.tight)
                .background(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                        .fill(isSelected ? Theme.securityGold : Theme.surfaceElevated)
                )
        }
        .buttonStyle(EKPressStyle())
    }
}
