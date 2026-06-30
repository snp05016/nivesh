import SwiftUI

struct PortfolioDashboardView: View {
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                
                ScrollView {
                    LazyVStack(spacing: Theme.Spacing.xLarge) {
                        NetWorthSection()
                        
                        GuillocheDivider()
                            .padding(.horizontal, Theme.screenPadding)
                        
                        AssetAllocationSection()
                    }
                    .padding(.vertical, Theme.Spacing.standard)
                }
            }
            .navigationTitle("Portfolio")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { HapticManager.selection(); 
                        HapticManager.selection()
                        // Handle adding transaction action
                    }) {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

struct NetWorthSection: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack {
                Text("NET WORTH")
                    .font(.caption.bold())
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Image(systemName: "lock.shield")
                    .foregroundColor(Theme.securityGold)
            }
            
            HStack {
                Text("₹ 45.20 Lakhs") // Mocked pre-formatted value
                    .font(.title2.monospaced())
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
            }
            
            GuillocheDivider()
            
            HStack {
                Text("Total Returns")
                    .font(.subheadline)
                    .fontDesign(.serif)
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Text("+ ₹ 4.50 Lakhs (11.0%)")
                    .font(.subheadline.monospaced())
                    .foregroundColor(Theme.bullGreen)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct AssetAllocationSection: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack {
                Text("Asset Allocation")
                    .font(.headline)
                    .fontDesign(.serif)
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
            }
            .padding(.horizontal, Theme.screenPadding)
            
            VStack(spacing: Theme.Spacing.standard) {
                AllocationRow(title: "Equity", value: "₹ 30.50 Lakhs", percentage: "67.4%", color: Theme.bullGreen)
                GuillocheDivider()
                AllocationRow(title: "Debt", value: "₹ 10.00 Lakhs", percentage: "22.1%", color: Theme.securityGold)
                GuillocheDivider()
                AllocationRow(title: "Gold", value: "₹ 4.70 Lakhs", percentage: "10.4%", color: Theme.inkSecondary)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

struct AllocationRow: View {
    let title: String
    let value: String
    let percentage: String
    let color: Color
    
    var body: some View {
        HStack {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            
            Text(title)
                .font(.subheadline)
                .fontDesign(.serif)
                .foregroundColor(Theme.inkPrimary)
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(value)
                    .font(.subheadline.monospaced())
                    .foregroundColor(Theme.inkPrimary)
                Text(percentage)
                    .font(.caption.monospaced())
                    .foregroundColor(Theme.inkSecondary)
            }
        }
    }
}

struct PortfolioDashboardView_Previews: PreviewProvider {
    static var previews: some View {
        PortfolioDashboardView()
    }
}
