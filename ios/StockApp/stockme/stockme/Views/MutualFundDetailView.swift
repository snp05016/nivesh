import SwiftUI

struct MutualFundDetailView: View {
    let fund: MutualFundDTO?
    
    init(fund: MutualFundDTO? = nil) {
        self.fund = fund
    }
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                MutualFundDetailHeader(fund: fund)
                
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                
                MutualFundNAVHistorySection()
                
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                
                MutualFundRiskometerSection()
                
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                
                MutualFundFundManagerSection()
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Fund Details")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct MutualFundDetailHeader: View {
    let fund: MutualFundDTO?
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text(fund?.fundName ?? "Fund Details")
                .font(Theme.engravedSerif(size: 24, weight: .bold, relativeTo: .title2))
                .foregroundColor(Theme.inkPrimary)
            
            HStack(spacing: Theme.Spacing.card) {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("NAV")
                        .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkTertiary)
                    
                    if let nav = fund?.nav {
                        Text(String(format: "₹%.2f", nav))
                            .font(Theme.serialNumberFont(size: 24, relativeTo: .title2))
                            .foregroundColor(Theme.inkPrimary)
                    } else {
                        Text("-")
                            .font(Theme.serialNumberFont(size: 24, relativeTo: .title2))
                            .foregroundColor(Theme.inkPrimary)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                    Text("AMC")
                        .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkTertiary)
                    
                    Text(fund?.amc ?? "-")
                        .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                }
            }
            .padding(.top, Theme.Spacing.medium)
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct MutualFundNAVHistorySection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("NAV History")
                .font(Theme.engravedSerif(size: 20, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)
                .padding(.horizontal, Theme.screenPadding)
            
            VStack(spacing: Theme.Spacing.medium) {
                // Mock Chart Area
                Rectangle()
                    .fill(Theme.canvasShadow)
                    .frame(height: 200)
                    .overlay(
                        Text("Chart Placeholder")
                            .font(Theme.officialStampFont(size: 14, relativeTo: .body))
                            .foregroundColor(Theme.inkSecondary)
                    )
                    .cornerRadius(Theme.CornerRadius.medium)
                
                HStack(alignment: .center, spacing: Theme.Spacing.medium) {
                    Text("1M")
                    Text("6M")
                    Text("1Y")
                        .bold()
                        .foregroundColor(Theme.canvas)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(Theme.inkPrimary)
                        .cornerRadius(Theme.CornerRadius.small)
                    Text("3Y")
                    Text("5Y")
                }
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(Theme.inkSecondary)
                .padding(.top, Theme.Spacing.small)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

struct MutualFundRiskometerSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Riskometer")
                .font(Theme.engravedSerif(size: 20, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)
                .padding(.horizontal, Theme.screenPadding)
            
            HStack(spacing: Theme.Spacing.card) {
                Circle()
                    .strokeBorder(Theme.bearRed, lineWidth: 8)
                    .frame(width: 80, height: 80)
                    .overlay(
                        Text("Very High")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                            .multilineTextAlignment(.center)
                            .foregroundColor(Theme.bearRed)
                    )
                
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("Very High Risk")
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)
                    
                    Text("Investors understand that their principal will be at very high risk.")
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkSecondary)
                        .lineLimit(3)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

struct MutualFundFundManagerSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Fund Management")
                .font(Theme.engravedSerif(size: 20, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)
                .padding(.horizontal, Theme.screenPadding)
            
            HStack(spacing: Theme.Spacing.card) {
                Circle()
                    .fill(Theme.canvasShadow)
                    .frame(width: 48, height: 48)
                
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("Rahul Singh")
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)
                    
                    Text("Managing since Oct 2019")
                        .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                        .foregroundColor(Theme.inkSecondary)
                }
                Spacer()
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}
