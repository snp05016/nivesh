import SwiftUI
import Combine
import Charts

struct SectorRotationSector: Identifiable, Codable {
    let id = UUID()
    let name: String
    let returnPct: Double
    let momentumScore: Double
    let quadrant: String
    let prevQuadrant: String
    let fiiFlowCr: Double
    let diiFlowCr: Double
    let institutionalConviction: Int
    let holdingsInSector: [String] // Mock string array
    
    enum CodingKeys: String, CodingKey {
        case name
        case returnPct = "return_pct"
        case momentumScore = "momentum_score"
        case quadrant
        case prevQuadrant = "prev_quadrant"
        case fiiFlowCr = "fii_flow_cr"
        case diiFlowCr = "dii_flow_cr"
        case institutionalConviction = "institutional_conviction"
        case holdingsInSector = "holdings_in_sector"
    }
}

struct SectorRotationResponse: Codable {
    let period: String
    let sectors: [SectorRotationSector]
}

@MainActor
class SectorRotationViewModel: ObservableObject {
    @Published var sectors: [SectorRotationSector] = []
    @Published var isLoading: Bool = false
    @Published var selectedPeriod: String = "3m"
    @Published var errorMessage: String? = nil
    /// Set when the server answers 402 (sector_rotation needs a higher plan).
    @Published var lockedTier: SubscriptionTier? = nil

    /// Goes through NetworkManager so the Bearer token is attached (the route
    /// depends on require_entitlement("sector_rotation")).
    func fetchRotation() async {
        isLoading = true
        errorMessage = nil
        lockedTier = nil
        defer { isLoading = false }
        do {
            let res = try await NetworkManager.shared._fetchDecode(
                SectorRotationResponse.self,
                endpoint: "/api/v1/market/sector-rotation?period=\(selectedPeriod)"
            )
            sectors = res.sectors.sorted(by: { $0.momentumScore > $1.momentumScore })
        } catch {
            errorMessage = error.localizedDescription
            lockedTier = (error as? NetworkError)?.requiredTier
        }
    }
}

struct SectorRotationScreen: View {
    @StateObject private var viewModel = SectorRotationViewModel()
    @State private var showHelp = false
    let periods = ["1m", "3m", "6m", "1y"]
    
    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.large) {
                HelpInlineButton(showHelp: $showHelp)
                    .padding(.horizontal, Theme.screenPadding)
                
                // Period Selector
                HStack(spacing: Theme.Spacing.standard) {
                    ForEach(periods, id: \.self) { period in
                        Button(action: { HapticManager.selection();  HapticManager.selection()
                            HapticManager.selection()
                            viewModel.selectedPeriod = period
                            Task { await viewModel.fetchRotation() }
                        }) {
                            Text(period.uppercased())
                                .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                                .padding(.horizontal, Theme.Spacing.card)
                                .padding(.vertical, Theme.Spacing.tight)
                                .background(viewModel.selectedPeriod == period ? Theme.inkPrimary : Color.clear)
                                .foregroundColor(viewModel.selectedPeriod == period ? Theme.canvas : Theme.inkSecondary)
                                .cornerRadius(Theme.CornerRadius.small)
                                .overlay(
                                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                        .stroke(Theme.borderFine, lineWidth: 1)
                                )
                        }
                        .buttonStyle(EKPressStyle())
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.top, Theme.Spacing.standard)
                
                if viewModel.isLoading {
                    ProgressView()
                        .padding()
                } else if let tier = viewModel.lockedTier, ReleaseGate.demoFeatures {
                    PremiumUpsellBanner(message: "Sector rotation analytics is part of \(tier.displayName)",
                                        tier: tier, featureKey: .sectorRotation)
                        .padding(.horizontal, Theme.screenPadding)
                } else if let err = viewModel.errorMessage {
                    Text(err)
                        .foregroundColor(Theme.bearRed)
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                } else if !viewModel.sectors.isEmpty {
                    
                    // Institutional Flow Section
                    InstitutionalFlowHighlight(sectors: viewModel.sectors)
                        .padding(.horizontal, Theme.screenPadding)
                    
                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)
                    
                    // Quadrant Scatter Chart
                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        Text("Momentum Matrix")
                            .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .title3))
                            .foregroundColor(Theme.inkPrimary)
                        
                        Chart {
                            ForEach(viewModel.sectors) { sector in
                                PointMark(
                                    x: .value("Return", sector.returnPct),
                                    y: .value("Momentum", sector.momentumScore)
                                )
                                .symbolSize(400) // Fixed size, prompt asked for mcap but we don't have it
                                .foregroundStyle(quadrantColor(sector.quadrant).opacity(0.8))
                                .annotation(position: .overlay) {
                                    Text(sector.name.prefix(3).uppercased())
                                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                        .foregroundColor(Theme.canvas)
                                }
                            }
                            
                            RuleMark(x: .value("Zero", 0.0))
                                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                                .foregroundStyle(Theme.inkTertiary)
                            
                            RuleMark(y: .value("Zero", 0.0))
                                .lineStyle(StrokeStyle(lineWidth: 1, dash: [4]))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .frame(height: UIScreen.main.bounds.height * 0.35)
                        .chartXAxis {
                            AxisMarks(values: .automatic) { _ in
                                AxisGridLine().foregroundStyle(Theme.borderFine)
                                AxisTick().foregroundStyle(Theme.inkTertiary)
                                AxisValueLabel().foregroundStyle(Theme.inkSecondary)
                            }
                        }
                        .chartYAxis {
                            AxisMarks(values: .automatic) { _ in
                                AxisGridLine().foregroundStyle(Theme.borderFine)
                                AxisTick().foregroundStyle(Theme.inkTertiary)
                                AxisValueLabel().foregroundStyle(Theme.inkSecondary)
                            }
                        }
                        .chartXAxisLabel("Return %")
                        .chartYAxisLabel("Momentum")
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    
                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)
                    
                    // Sector Cards
                    VStack(spacing: Theme.Spacing.card) {
                        ForEach(viewModel.sectors) { sector in
                            SectorRotationCard(sector: sector)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
            }
            .padding(.bottom, Theme.Spacing.large)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Sector Rotation")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if viewModel.sectors.isEmpty {
                Task { await viewModel.fetchRotation() }
            }
        }
        .helpSheet(isPresented: $showHelp, title: FeatureHelp.sectorRotation.title, subtitle: FeatureHelp.sectorRotation.subtitle, sections: FeatureHelp.sectorRotation.sections)
    }
    
    private func quadrantColor(_ quad: String) -> Color {
        switch quad {
        case "Leaders": return Theme.bullGreen
        case "Improving": return Theme.securityGold
        case "Laggards": return Theme.bearRed
        case "Fading": return Theme.holdAmber
        default: return Theme.inkSecondary
        }
    }
}

struct InstitutionalFlowHighlight: View {
    let sectors: [SectorRotationSector]
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text("Institutional Flow")
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .foregroundColor(Theme.inkSecondary)
            
            if let topBuy = sectors.max(by: { $0.fiiFlowCr < $1.fiiFlowCr }),
               let topSell = sectors.min(by: { $0.fiiFlowCr < $1.fiiFlowCr }) {
                
                Text("FIIs buying \(topBuy.name) (\(flowLabel(topBuy.fiiFlowCr))), selling \(topSell.name) (\(flowLabel(topSell.fiiFlowCr)))")
                    .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    /// Signed crore flow through the shared formatter: "+₹1,250 Cr" / "-₹340.0 Cr".
    private func flowLabel(_ crores: Double) -> String {
        (crores > 0 ? "+" : "") + IndianFormatter.formatLakhsCrores(crores * 1_00_00_000)
    }
}

struct SectorRotationCard: View {
    let sector: SectorRotationSector
    
    var body: some View {
        Button(action: { HapticManager.selection();  HapticManager.selection()
            HapticManager.selection()
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack {
                    Text(sector.name)
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                    
                    Spacer()
                    
                    Text("\(sector.quadrant)")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.canvasDeep)
                        .cornerRadius(Theme.CornerRadius.small)
                        .foregroundColor(Theme.inkSecondary)
                }
                
                HStack(spacing: Theme.Spacing.large) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("Return")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                            .foregroundColor(Theme.inkSecondary)
                        Text("\(sector.returnPct >= 0 ? "+" : "")\(String(format: "%.1f", sector.returnPct))%")
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                            .foregroundColor(sector.returnPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                    
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("Momentum")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                            .foregroundColor(Theme.inkSecondary)
                        Text("\(String(format: "%.1f", sector.momentumScore))")
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                            .foregroundColor(Theme.inkPrimary)
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("Conviction")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                            .foregroundColor(Theme.inkSecondary)
                        
                        HStack(spacing: Theme.Spacing.xSmall) {
                            Image(systemName: "building.columns.fill")
                                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                                .foregroundColor(Theme.securityGold)
                            Text("\(sector.institutionalConviction)%")
                                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                                .foregroundColor(Theme.inkPrimary)
                        }
                    }
                }
                
                HStack {
                    FIIFlowIndicator(label: "FII", flow: sector.fiiFlowCr)
                    Spacer()
                    FIIFlowIndicator(label: "DII", flow: sector.diiFlowCr)
                }
                .padding(.top, Theme.Spacing.tight)
                
                if !sector.holdingsInSector.isEmpty {
                    Text("You have \(sector.holdingsInSector.count) holdings here")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.holdAmber.opacity(0.1))
                        .foregroundColor(Theme.holdAmber)
                        .cornerRadius(Theme.CornerRadius.small)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
    }
}

struct FIIFlowIndicator: View {
    let label: String
    let flow: Double
    
    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Text(label)
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .foregroundColor(Theme.inkSecondary)
            
            Image(systemName: flow >= 0 ? "arrow.up.right" : "arrow.down.right")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .foregroundColor(flow >= 0 ? Theme.bullGreen : Theme.bearRed)
            
            Text("₹\(Int(abs(flow))) Cr")
                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                .foregroundColor(Theme.inkPrimary)
        }
    }
}
