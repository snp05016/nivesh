import SwiftUI

struct MutualFundDiscoveryView: View {
    @StateObject private var viewModel = MutualFundViewModel()
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                MutualFundDiscoveryHeader()
                
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                
                MutualFundCategorySelector(selectedCategory: $viewModel.selectedCategory, categories: viewModel.availableCategories)
                
                MutualFundListSection(category: viewModel.selectedCategory ?? "Funds", funds: viewModel.filteredFunds)
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Mutual Funds")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await viewModel.fetchFunds()
        }
    }
}

struct MutualFundDiscoveryHeader: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Discover Funds")
                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                .foregroundColor(Theme.inkPrimary)
            
            Text("Invest in top-rated mutual funds curated by experts.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)
            
            HStack(spacing: Theme.Spacing.standard) {
                MutualFundStatBox(title: "AUM Managed", value: "₹2.4 Crores")
                MutualFundStatBox(title: "Avg. Return", value: "14.2%", isPositive: true)
            }
            .padding(.top, Theme.Spacing.medium)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct MutualFundStatBox: View {
    let title: String
    let value: String
    var isPositive: Bool = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(title)
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)
            
            Text(value)
                .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                .foregroundColor(isPositive ? Theme.bullGreen : Theme.inkPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct MutualFundCategorySelector: View {
    @Binding var selectedCategory: String?
    let categories: [String]
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Spacing.standard) {
                ForEach(categories, id: \.self) { category in
                    Button(action: { HapticManager.selection(); 
                        HapticManager.selection()
                        selectedCategory = category
                    }) {
                        Text(category)
                            .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                            .tracking(1.5)
                            .padding(.horizontal, Theme.Spacing.card)
                            .padding(.vertical, Theme.Spacing.medium)
                            .background(selectedCategory == category ? Theme.inkPrimary : Color.clear)
                            .foregroundColor(selectedCategory == category ? Theme.canvas : Theme.inkSecondary)
                            .cornerRadius(Theme.CornerRadius.small)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                    .stroke(Theme.borderFine, lineWidth: selectedCategory == category ? 0 : 1)
                            )
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

struct MutualFundListSection: View {
    let category: String
    let funds: [MutualFundDTO]
    
    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            HStack {
                Text("Top \(category)")
                    .font(Theme.engravedSerif(size: 20, weight: .semibold, relativeTo: .title3))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
            }
            .padding(.horizontal, Theme.screenPadding)
            
            ForEach(funds) { fund in
                MutualFundRowCard(fund: fund)
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

struct MutualFundRowCard: View {
    let fund: MutualFundDTO
    
    var body: some View {
        NavigationLink(destination: MutualFundDetailView(fund: fund)) {
            HStack(spacing: Theme.Spacing.card) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .fill(Theme.canvasShadow)
                    .frame(width: 48, height: 48)
                    .overlay(
                        Text(String(fund.fundName.prefix(1)))
                            .font(Theme.engravedSerif(size: 24, weight: .bold, relativeTo: .body))
                            .foregroundColor(Theme.inkSecondary)
                    )
                
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(fund.fundName)
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)
                        .lineLimit(1)
                    
                    Text("\(fund.category) • \(fund.amc)")
                        .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkSecondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    if let nav = fund.nav {
                        Text(String(format: "₹%.2f", nav))
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                            .foregroundColor(Theme.inkPrimary)
                    } else {
                        Text("-")
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                            .foregroundColor(Theme.inkPrimary)
                    }
                    
                    Text("NAV")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded {
            HapticManager.selection()
        })
    }
}
