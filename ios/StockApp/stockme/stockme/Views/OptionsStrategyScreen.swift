import SwiftUI
import Charts

// MARK: - Local Leg Model (editable, not Codable)

struct OptionLegVM: Identifiable, Equatable {
    let id = UUID()
    var type: String = "CALL"          // CALL or PUT
    var position: String = "LONG"      // LONG or SHORT
    var strike: Double = 100.0
    var premium: Double = 5.0

    func toAPILeg() -> OptionLeg {
        OptionLeg(type: type, position: position, strike: strike, premium: premium)
    }

    static func == (lhs: OptionLegVM, rhs: OptionLegVM) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Local Payoff Model

struct PayoffVectorPoint: Identifiable {
    let id = UUID()
    let price: Double
    let pnl: Double
}

// MARK: - Main Screen

struct OptionsStrategyScreen: View {
    @State private var spotPrice: String = "1000.0"
    @State private var legs: [OptionLegVM] = [OptionLegVM()]
    @State private var isLoading = false
    @State private var response: OptionsPayoffResponse? = nil
    @State private var localPayoff: [PayoffVectorPoint] = []
    @State private var localMetrics: (maxProfit: Double, maxLoss: Double, breakevens: [Double], netPremium: Double)? = nil
    @State private var errorMessage: String? = nil
    @State private var showHelp = false

    private var parsedSpot: Double { Double(spotPrice) ?? 1000.0 }

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            ScrollView {
                VStack(spacing: Theme.sectionSpacing) {
                    headerSection
                    spotPriceSection
                    legBuilderSection
                    metricsSection
                    chartSection
                }
                .padding(.bottom, Theme.sectionSpacing)
            }
            .scrollIndicators(.hidden)
        }
        .navigationBarHidden(true)
        .sheet(isPresented: $showHelp) {
            helpSheet
        }
        .onAppear { computeLocal() }
    }

    // MARK: - Header

    private var headerSection: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("रणनीति निर्माता")
                    .font(Theme.hindiFont(size: 10))
                    .foregroundStyle(Theme.inkTertiary)
                Text("OPTIONS STRATEGY BUILDER")
                    .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                    .foregroundStyle(Theme.inkPrimary)
                Text("Construct multi-leg strategies & visualise payoff")
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(1)
            }
            Spacer()
            Button(action: { HapticManager.selection(); showHelp = true }) {
                Image(systemName: "questionmark.circle.fill")
                    .font(.title3)
                    .foregroundStyle(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
    }

    // MARK: - Spot Price

    private var spotPriceSection: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("SPOT PRICE (₹)")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.2)
                    .foregroundStyle(Theme.inkTertiary)
                TextField("1000.00", text: $spotPrice)
                    .keyboardType(.decimalPad)
                    .font(Theme.serialNumberFont(size: 20, relativeTo: .headline))
                    .foregroundStyle(Theme.inkPrimary)
                    .onChange(of: spotPrice) { _, _ in computeLocal() }
            }
            Spacer()
            Text("₹")
                .font(Theme.engravedSerif(size: 24, weight: .bold))
                .foregroundStyle(Theme.securityGold)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: - Leg Builder

    private var legBuilderSection: some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack {
                Text("STRATEGY LEGS")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.2)
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text("\(legs.count) \(legs.count == 1 ? "LEG" : "LEGS")")
                    .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                    .foregroundStyle(Theme.securityGold)
            }
            .padding(.horizontal, Theme.screenPadding)

            ForEach(legs) { leg in
                legRow(leg)
                    .padding(.horizontal, Theme.screenPadding)
            }

            addLegButton
                .padding(.horizontal, Theme.screenPadding)
        }
    }

    private func legRow(_ leg: OptionLegVM) -> some View {
        guard let idx = legs.firstIndex(where: { $0.id == leg.id }) else {
            return AnyView(EmptyView())
        }
        return AnyView(
            VStack(spacing: Theme.Spacing.medium) {
                // Row 1: Type and Position toggles + delete
                HStack(spacing: Theme.Spacing.tight) {
                    Text("LEG \(idx + 1)")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)

                    typePicker(idx: idx)
                    positionPicker(idx: idx)

                    Spacer()

                    Button(action: {
                        HapticManager.selection()
                        withAnimation { legs.remove(at: idx); computeLocal() }
                    }) {
                        Image(systemName: "trash")
                            .font(.caption)
                            .foregroundStyle(Theme.bearRed.opacity(0.6))
                    }
                    .buttonStyle(EKPressStyle())
                    .disabled(legs.count <= 1)
                    .opacity(legs.count <= 1 ? 0.3 : 1.0)
                }

                // Row 2: Strike and Premium
                HStack(spacing: Theme.Spacing.standard) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("STRIKE (₹)")
                            .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                            .tracking(0.8)
                            .foregroundStyle(Theme.inkTertiary)
                        TextField("Strike", value: $legs[idx].strike, format: .number)
                            .keyboardType(.decimalPad)
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .callout))
                            .foregroundStyle(Theme.inkPrimary)
                            .onChange(of: legs[idx].strike) { _, _ in computeLocal() }
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("PREMIUM (₹)")
                            .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                            .tracking(0.8)
                            .foregroundStyle(Theme.inkTertiary)
                        TextField("Premium", value: $legs[idx].premium, format: .number)
                            .keyboardType(.decimalPad)
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .callout))
                            .foregroundStyle(Theme.inkPrimary)
                            .onChange(of: legs[idx].premium) { _, _ in computeLocal() }
                    }
                }
            }
            .padding(Theme.Spacing.standard)
            .frame(maxWidth: .infinity)
            .banknoteCard()
        )
    }

    private func typePicker(idx: Int) -> some View {
        HStack(spacing: 1) {
            ForEach(["CALL", "PUT"], id: \.self) { t in
                Button(action: {
                    HapticManager.selection()
                    legs[idx].type = t; computeLocal()
                }) {
                    Text(t)
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(0.8)
                        .foregroundStyle(legs[idx].type == t ? Theme.canvas : Theme.inkSecondary)
                        .padding(.horizontal, Theme.Spacing.standard)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(legs[idx].type == t ? Theme.securityGold : Theme.canvasDeep)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .clipShape(Capsule())
        .overlay(Capsule().stroke(Theme.borderSage, lineWidth: 0.5))
    }

    private func positionPicker(idx: Int) -> some View {
        HStack(spacing: 1) {
            ForEach(["BUY", "SELL"], id: \.self) { p in
                let mapped = p == "BUY" ? "LONG" : "SHORT"
                Button(action: {
                    HapticManager.selection()
                    legs[idx].position = mapped; computeLocal()
                }) {
                    Text(p)
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(0.8)
                        .padding(.horizontal, Theme.Spacing.standard)
                        .padding(.vertical, Theme.Spacing.small)
                        .foregroundStyle(legs[idx].position == mapped ? Theme.canvas : Theme.inkSecondary)
                        .background(legs[idx].position == mapped
                            ? (mapped == "LONG" ? Theme.bullGreen : Theme.bearRed)
                            : Theme.canvasDeep)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .clipShape(Capsule())
        .overlay(Capsule().stroke(Theme.borderSage, lineWidth: 0.5))
    }

    private var addLegButton: some View {
        Button(action: {
            HapticManager.soft()
            withAnimation { legs.append(OptionLegVM()); computeLocal() }
        }) {
            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: "plus.circle.fill")
                    .font(.callout)
                Text("ADD LEG")
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                    .tracking(1.2)
            }
            .foregroundStyle(Theme.securityGold)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.standard)
            .background(Theme.securityGold.opacity(0.06))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.securityGold.opacity(0.25), style: StrokeStyle(lineWidth: 0.5, dash: [4, 4]))
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: - Metrics

    private var metricsSection: some View {
        VStack(spacing: Theme.Spacing.medium) {
            Text("KEY METRICS")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, Theme.screenPadding)

            if let resp = response {
                remoteMetricsCard(resp)
            } else if let local = localMetrics {
                localMetricsCard(local)
            }

            if let err = errorMessage {
                Text(err)
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                    .foregroundStyle(Theme.bearRed)
                    .padding(.horizontal, Theme.screenPadding)
            }
        }
    }

    private func remoteMetricsCard(_ r: OptionsPayoffResponse) -> some View {
        VStack(spacing: Theme.Spacing.medium) {
            HStack {
                strategyTypeBadge(r.strategyType)
                Spacer()
                Text("NET \(r.netPremium >= 0 ? "CREDIT" : "DEBIT"): \(r.netPremiumFormatted)")
                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption))
                    .foregroundStyle(r.netPremium >= 0 ? Theme.bullGreen : Theme.bearRed)
            }

            GuillocheDivider()

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.standard) {
                metricBox("MAX PROFIT", r.maxProfitFormatted, Theme.bullGreen, unlimited: r.maxProfitUnlimited)
                metricBox("MAX LOSS", r.maxLossFormatted, Theme.bearRed, unlimited: r.maxLossUnlimited)
                metricBox("BREAKEVEN", breakevensText(r.breakevens), Theme.inkPrimary)
                metricBox("SPOT PRICE", IndianFormatter.price(r.spotPrice), Theme.securityGold)
            }
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }

    private func localMetricsCard(_ m: (Double, Double, [Double], Double)) -> some View {
        let premium = m.3
        VStack(spacing: Theme.Spacing.medium) {
            HStack {
                Text("LOCAL — \(legs.count) LEG\(legs.count > 1 ? "S" : "")")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.0)
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text("NET \(premium >= 0 ? "CREDIT" : "DEBIT"): \(IndianFormatter.price(premium))")
                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption))
                    .foregroundStyle(premium >= 0 ? Theme.bullGreen : Theme.bearRed)
            }

            GuillocheDivider()

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.standard) {
                metricBox("MAX PROFIT", IndianFormatter.price(m.0), Theme.bullGreen)
                metricBox("MAX LOSS", IndianFormatter.price(m.1), Theme.bearRed)
                metricBox("BREAKEVEN", breakevensText(m.2), Theme.inkPrimary)
                metricBox("SPOT PRICE", IndianFormatter.price(parsedSpot), Theme.securityGold)
            }

            Button(action: { fetchFromAPI() }) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.caption)
                    Text("FETCH FROM SERVER")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(1.0)
                }
                .foregroundStyle(Theme.securityGold)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.tight)
                .background(Theme.securityGold.opacity(0.06))
                .clipShape(Capsule())
            }
            .buttonStyle(EKPressStyle())
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }

    private func strategyTypeBadge(_ type: String) -> some View {
        Text(type.uppercased())
            .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
            .tracking(1.2)
            .foregroundStyle(Theme.securityGold)
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.xSmall)
            .background(Theme.securityGold.opacity(0.08))
            .clipShape(Capsule())
            .overlay(Capsule().stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
    }

    private func metricBox(_ label: String, _ value: String, _ color: Color, unlimited: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            Text(unlimited ? "∞" : value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .callout).weight(.bold))
                .foregroundStyle(color)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.standard)
        .background(color.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }

    private func breakevensText(_ bes: [Double]) -> String {
        if bes.isEmpty { return "—" }
        return bes.prefix(4).map { IndianFormatter.price($0) }.joined(separator: ", ")
            + (bes.count > 4 ? " +\(bes.count - 4) more" : "")
    }

    // MARK: - Chart

    private var chartSection: some View {
        VStack(spacing: Theme.Spacing.medium) {
            Text("PAYOFF CHART")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, Theme.screenPadding)

            if localPayoff.isEmpty && response == nil {
                loadingChartPlaceholder
            } else {
                let points = response != nil ? response!.payoffVector.map {
                    PayoffVectorPoint(price: $0.underlyingPrice, pnl: $0.pnl)
                } : localPayoff

                Chart(points) { pt in
                    LineMark(
                        x: .value("Underlying (₹)", pt.price),
                        y: .value("P&L (₹)", pt.pnl)
                    )
                    .foregroundStyle(pt.pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
                    .lineStyle(StrokeStyle(lineWidth: 2))

                    AreaMark(
                        x: .value("Underlying (₹)", pt.price),
                        yStart: .value("Zero", 0),
                        yEnd: .value("P&L (₹)", pt.pnl)
                    )
                    .foregroundStyle(
                        Gradient(colors: [
                            (pt.pnl >= 0 ? Theme.bullGreen : Theme.bearRed).opacity(0.18),
                            (pt.pnl >= 0 ? Theme.bullGreen : Theme.bearRed).opacity(0.02),
                        ])
                    )
                }
                .chartXAxis {
                    AxisMarks(position: .bottom) { _ in
                        AxisValueLabel()
                            .font(Theme.microLabel(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartYAxis {
                    AxisMarks { _ in
                        AxisValueLabel()
                            .font(Theme.microLabel(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartOverlay { proxy in
                    GeometryReader { geo in
                        Path { path in
                            guard let xPos = proxy.position(forX: parsedSpot) else { return }
                            path.move(to: CGPoint(x: xPos, y: geo.frame(in: .local).minY))
                            path.addLine(to: CGPoint(x: xPos, y: geo.frame(in: .local).maxY))
                        }
                        .stroke(Theme.securityGold.opacity(0.4), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
                    }
                }
                .chartYAxisLabel {
                    Text("P&L (₹)")
                        .font(Theme.microLabel(size: 9, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkTertiary)
                }
                .chartXAxisLabel {
                    Text("Underlying Price (₹)")
                        .font(Theme.microLabel(size: 9, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkTertiary)
                }
                .frame(height: UIScreen.main.bounds.height * 0.42)
                .padding(Theme.Spacing.card)
                .banknoteCard()
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }

    private var loadingChartPlaceholder: some View {
        RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
            .fill(Theme.canvasDeep)
            .frame(height: UIScreen.main.bounds.height * 0.42)
            .overlay(
                VStack(spacing: Theme.Spacing.medium) {
                    ProgressView()
                        .tint(Theme.securityGold)
                    Text("ADD LEGS TO SEE PAYOFF")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(1.0)
                        .foregroundStyle(Theme.inkTertiary)
                }
            )
            .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: - Help Sheet

    private var helpSheet: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                    Group {
                        Text("ABOUT THE STRATEGY BUILDER")
                            .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                            .foregroundStyle(Theme.inkPrimary)

                        helpRow("1", "Set the current spot price of the underlying")
                        helpRow("2", "Add legs — each leg is one Call or Put option")
                        helpRow("3", "Choose Buy (Long) or Sell (Short) for each leg")
                        helpRow("4", "Enter Strike Price and Premium for each leg")
                        helpRow("5", "The payoff chart updates instantly showing P&L")
                    }

                    GuillocheDivider()

                    Group {
                        Text("STRATEGY EXAMPLES")
                            .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .headline))
                            .foregroundStyle(Theme.inkPrimary)

                        exampleRow("COVERED CALL", "Buy underlying + Sell Out-of-Money Call")
                        exampleRow("BULL CALL SPREAD", "Buy lower strike Call + Sell higher strike Call")
                        exampleRow("IRON CONDOR", "4 legs: OTM Put spread + OTM Call spread")
                        exampleRow("LONG STRADDLE", "Buy Call + Buy Put at same strike")
                        exampleRow("SHORT STRANGLE", "Sell OTM Put + Sell OTM Call")
                    }

                    GuillocheDivider()

                    Group {
                        Text("READING THE CHART")
                            .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .headline))
                            .foregroundStyle(Theme.inkPrimary)

                        chartLegendRow("Green area", "Profit zone (P&L > 0)", Theme.bullGreen)
                        chartLegendRow("Red area", "Loss zone (P&L < 0)", Theme.bearRed)
                        chartLegendRow("Gold dotted line", "Current spot price", Theme.securityGold)
                        chartLegendRow("X axis", "Underlying asset price (₹)", Theme.inkPrimary)
                        chartLegendRow("Y axis", "Profit / Loss (₹)", Theme.inkPrimary)
                    }

                    GuillocheDivider()

                    Group {
                        Text("PAYOFF FORMULAS")
                            .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .headline))
                            .foregroundStyle(Theme.inkPrimary)

                        formulaRow("Long Call", "max(0, S - K) - Premium")
                        formulaRow("Short Call", "Premium - max(0, S - K)")
                        formulaRow("Long Put", "max(0, K - S) - Premium")
                        formulaRow("Short Put", "Premium - max(0, K - S)")
                        Text("S = Underlying price, K = Strike price")
                            .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .padding(Theme.screenPadding)
                .padding(.bottom, Theme.sectionSpacing)
            }
            .background(DenominationBackground(denomination: .twoHundred))
            .navigationTitle("How to Use")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("DONE") { HapticManager.selection(); showHelp = false }
                        .buttonStyle(EKPressStyle())
                }
            }
        }
        .presentationDetents([.large])
    }

    private func helpRow(_ num: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Text(num)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote).weight(.bold))
                .foregroundStyle(Theme.securityGold)
                .frame(width: 20, alignment: .center)
            Text(text)
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
        }
    }

    private func exampleRow(_ name: String, _ desc: String) -> some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Text(name)
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption).weight(.bold))
                .foregroundStyle(Theme.securityGold)
                .frame(width: 130, alignment: .leading)
            Text(desc)
                .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
        }
    }

    private func chartLegendRow(_ symbol: String, _ meaning: String, _ color: Color) -> some View {
        HStack(spacing: Theme.Spacing.standard) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(symbol)
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption).weight(.semibold))
                .foregroundStyle(color)
            Text("— \(meaning)")
                .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
        }
    }

    private func formulaRow(_ label: String, _ formula: String) -> some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Text(label)
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption).weight(.bold))
                .foregroundStyle(Theme.securityGold)
                .frame(width: 90, alignment: .leading)
            Text(formula)
                .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
        }
    }

    // MARK: - Local Computation (offline fallback)

    private func computeLocal() {
        guard !legs.isEmpty, parsedSpot > 0 else {
            localPayoff = []
            localMetrics = nil
            return
        }

        let rangePct = 0.20
        let priceMin = parsedSpot * (1.0 - rangePct)
        let priceMax = parsedSpot * (1.0 + rangePct)
        let steps = 100
        let step = (priceMax - priceMin) / Double(steps - 1)

        var pts: [PayoffVectorPoint] = []
        var netPremium: Double = 0
        for leg in legs {
            if leg.position == "SHORT" { netPremium += leg.premium }
            else { netPremium -= leg.premium }
        }

        for i in 0..<steps {
            let price = priceMin + step * Double(i)
            var totalPnl: Double = 0
            for leg in legs {
                totalPnl += legPayoff(leg: leg, underlying: price)
            }
            pts.append(PayoffVectorPoint(price: price, pnl: totalPnl))
        }

        let pnls = pts.map { $0.pnl }
        let maxP = pnls.max() ?? 0
        let minP = pnls.min() ?? 0

        var bes: [Double] = []
        for i in 0..<(pts.count - 1) {
            let p1 = pts[i], p2 = pts[i + 1]
            if p1.pnl * p2.pnl <= 0, !(p1.pnl == 0 && p2.pnl == 0) {
                if p1.pnl == 0 { bes.append(p1.price) }
                else if p2.pnl == 0 { bes.append(p2.price) }
                else {
                    let frac = abs(p1.pnl) / (abs(p1.pnl) + abs(p2.pnl))
                    bes.append(p1.price + frac * (p2.price - p1.price))
                }
            }
        }

        localPayoff = pts
        localMetrics = (maxP, minP, bes.sorted(), netPremium)
    }

    private func legPayoff(leg: OptionLegVM, underlying: Double) -> Double {
        let payoff: Double
        if leg.type == "CALL" {
            payoff = max(0, underlying - leg.strike)
        } else {
            payoff = max(0, leg.strike - underlying)
        }
        return leg.position == "LONG" ? payoff - leg.premium : leg.premium - payoff
    }

    // MARK: - API Fetch

    private func fetchFromAPI() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let apiLegs = legs.map { $0.toAPILeg() }
                let result = try await NetworkManager.shared.getOptionsPayoff(
                    spotPrice: parsedSpot,
                    legs: apiLegs
                )
                await MainActor.run {
                    response = result
                    isLoading = false
                    errorMessage = nil
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}
