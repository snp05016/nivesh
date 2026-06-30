import SwiftUI

struct IPOHubView: View {
    @State private var selectedTab: IPOTab = .open
    
    enum IPOTab: String, CaseIterable {
        case open = "Open"
        case upcoming = "Upcoming"
        case closed = "Closed"
    }
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: 32) {
                IPOHubHeader()
                
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                
                IPOTabSelector(selectedTab: $selectedTab)
                
                IPOListSection(tab: selectedTab)
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("IPO Hub")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct IPOHubHeader: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("IPO Central")
                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                .foregroundColor(Theme.inkPrimary)
            
            Text("Track, analyze, and apply for the latest Initial Public Offerings.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct IPOTabSelector: View {
    @Binding var selectedTab: IPOHubView.IPOTab
    
    var body: some View {
        HStack(spacing: 0) {
            ForEach(IPOHubView.IPOTab.allCases, id: \.self) { tab in
                Button(action: {
                    HapticManager.selection()
                    selectedTab = tab
                }) {
                    VStack(spacing: Theme.Spacing.medium) {
                        Text(tab.rawValue)
                            .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                            .tracking(1.5)
                            .foregroundColor(selectedTab == tab ? Theme.inkPrimary : Theme.inkSecondary)
                        
                        Rectangle()
                            .fill(selectedTab == tab ? Theme.inkPrimary : Color.clear)
                            .frame(height: 2)
                    }
                }
                .buttonStyle(EKPressStyle())
                .frame(maxWidth: .infinity)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct IPOListSection: View {
    let tab: IPOHubView.IPOTab
    
    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            ForEach(0..<4, id: \.self) { index in
                IPOCard(tab: tab, index: index)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct IPOCard: View {
    let tab: IPOHubView.IPOTab
    let index: Int
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            HStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.canvasShadow)
                    .frame(width: 40, height: 40)
                    .overlay(
                        Text("Tech")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    )
                
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("Swiggy Ltd.")
                        .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                    
                    Text("Mainboard")
                        .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkSecondary)
                }
                
                Spacer()
                
                if tab == .open {
                    Text("Apply Now")
                        .font(Theme.labelStyle)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(Theme.bullGreen)
                        .foregroundColor(Theme.canvas)
                        .cornerRadius(Theme.CornerRadius.small)
                } else if tab == .upcoming {
                    Text("Nov 15")
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkSecondary)
                } else {
                    Text("Listed")
                        .font(Theme.labelStyle)
                        .foregroundColor(Theme.inkTertiary)
                }
            }
            
            GuillocheDivider()
            
            HStack(spacing: Theme.Spacing.large) {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("Price Band")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkTertiary)
                    
                    Text("₹371 - ₹390")
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkPrimary)
                }
                
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("Lot Size")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkTertiary)
                    
                    Text("38 Shares")
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkPrimary)
                }
                
                Spacer()
                
                if tab == .open {
                    VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                        Text("Closes In")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                            .tracking(1.5)
                            .foregroundColor(Theme.inkTertiary)
                        
                        Text("2 Days")
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                            .foregroundColor(Theme.bearRed)
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
