import SwiftUI
import Combine

struct EarningsSurprise: Codable, Identifiable {
    var id: String { ticker + quarter }
    let ticker: String
    let company_name: String
    let quarter: String
    let estimated_eps: Double?
    let actual_eps: Double?
    let surprise_pct: Double?
    let classification: String
    let post_price_1d: Double?
    let post_price_5d: Double?
    let historical_score: Double?
    let serial_pattern: String?
}

struct EarningsCalendarDay: Codable, Identifiable {
    var id: String { ticker + (announcement_date ?? "") }
    let ticker: String
    let company_name: String?
    let announcement_date: String?
    let quarter: String?
    let estimated_eps: Double?
    let sparkline: [Double]?
    let price_change_7d_pct: Double?
    
    enum CodingKeys: String, CodingKey {
        case ticker, company_name, announcement_date, quarter
        case estimated_eps, sparkline, price_change_7d_pct
    }
}

struct EarningsCalendarResponse: Codable {
    let date: String
    let results: [EarningsCalendarDay]
    let count: Int
    
    enum CodingKeys: String, CodingKey {
        case date, results, count
    }
}

// MARK: - ViewModel

class EarningsSurpriseViewModel: ObservableObject {
    @Published var surprises: [EarningsSurprise] = []
    @Published var calendarDays: [EarningsCalendarDay] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var isCalendarView: Bool = false
    @Published var selectedCalendarDate: Date = Date()
    @Published var showHelp: Bool = false

    func fetchSurprises() {
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/earnings/surprises?period=current_quarter") else { return }
        isLoading = true; errorMessage = nil
        URLSession.shared.dataTask(with: url) { [weak self] data, _, error in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.isLoading = false
                if let error = error { self.errorMessage = error.localizedDescription; return }
                guard let data = data else { self.errorMessage = "No data."; return }
                do {
                    self.surprises = try JSONDecoder().decode([EarningsSurprise].self, from: data)
                    self.surprises.sort { abs($0.surprise_pct ?? 0) > abs($1.surprise_pct ?? 0) }
                } catch { self.errorMessage = error.localizedDescription }
            }
        }.resume()
    }
    
    func fetchCalendar() {
        let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd"
        let dateStr = df.string(from: selectedCalendarDate)
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/earnings/calendar?date=\(dateStr)") else { return }
        isLoading = true; errorMessage = nil
        URLSession.shared.dataTask(with: url) { [weak self] data, _, error in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.isLoading = false
                if let error = error { self.errorMessage = error.localizedDescription; return }
                guard let data = data else { self.errorMessage = "No data."; return }
                do {
                    let resp = try JSONDecoder().decode(EarningsCalendarResponse.self, from: data)
                    self.calendarDays = resp.results
                } catch { self.errorMessage = error.localizedDescription }
            }
        }.resume()
    }
}

// MARK: - Screen

struct EarningsSurpriseScreen: View {
    @StateObject private var vm = EarningsSurpriseViewModel()
    
    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()
            
            if vm.isLoading && vm.surprises.isEmpty {
                ProgressView().tint(Theme.securityGold)
            } else if let err = vm.errorMessage, vm.surprises.isEmpty {
                BanknoteErrorCanvas(title: "Earnings Surprise", detail: err, retryAction: { vm.fetchSurprises() })
            } else {
                ScrollView {
                    VStack(spacing: Theme.sectionSpacing) {
                        header
                        summaryBanner
                        GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                        
                        if vm.isCalendarView {
                            calendarSection
                        } else {
                            LazyVStack(spacing: Theme.Spacing.card) {
                                ForEach(vm.surprises) { s in
                                    SurpriseCard(surprise: s)
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                    }
                    .padding(.bottom, Theme.Spacing.xLarge)
                }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "sparkles.rectangle")
                        .font(Theme.engravedSerif(size: 12, weight: .semibold))
                        .foregroundColor(Theme.securityGold)
                    Text("EARNINGS SURPRISE")
                        .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkPrimary)
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: Theme.Spacing.small) {
                    Button { HapticManager.selection(); vm.showHelp = true }.buttonStyle(EKPressStyle())
                    label: {
                        Image(systemName: "questionmark.circle")
                            .font(Theme.engravedSerif(size: 18, weight: .medium))
                            .foregroundColor(Theme.securityGold)
                    }
                    .buttonStyle(EKPressStyle())
                    
                    Button {
    HapticManager.selection()
                        HapticManager.selection()
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                            vm.isCalendarView.toggle()
                            if vm.isCalendarView { vm.fetchCalendar() }
                        }
                    } label: {
                        Image(systemName: vm.isCalendarView ? "list.bullet" : "calendar")
                            .font(Theme.engravedSerif(size: 18, weight: .medium))
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
        .onAppear { if vm.surprises.isEmpty { vm.fetchSurprises() } }
        .onChange(of: vm.selectedCalendarDate) { _ in vm.fetchCalendar() }
        .sheet(isPresented: $vm.showHelp) { EarningsSurpriseHelpView() }
    }
    
    // MARK: - Views
    
    private var header: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("Track which companies beat or missed analyst estimates — and how the market reacted.")
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
                .lineSpacing(4)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
    }
    
    private var summaryBanner: some View {
        let beats  = vm.surprises.filter { $0.classification == "BEAT" }.count
        let misses = vm.surprises.filter { $0.classification == "MISS" }.count
        let inline = vm.surprises.filter { $0.classification == "INLINE" }.count
        return VStack(spacing: Theme.Spacing.medium) {
            Text("THIS QUARTER")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)
            HStack(spacing: Theme.Spacing.none) {
                summaryItem(label: "BEATS",  count: beats,  color: Theme.bullGreen)
                summaryDivider
                summaryItem(label: "MISSES", count: misses, color: Theme.bearRed)
                summaryDivider
                summaryItem(label: "INLINE", count: inline, color: Theme.holdAmber)
            }
        }
        .padding(.vertical, Theme.Spacing.card)
        .frame(maxWidth: .infinity)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
    
    private func summaryItem(label: String, count: Int, color: Color) -> some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("\(count)")
                .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                .foregroundColor(color)
            Text(label)
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.0)
                .foregroundColor(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity)
    }
    
    private var summaryDivider: some View {
        Rectangle()
            .fill(Theme.borderFine)
            .frame(width: 0.5, height: 40)
    }
    
    // MARK: - Calendar
    
    private var calendarSection: some View {
        VStack(spacing: Theme.Spacing.card) {
            DatePicker("Select Date", selection: $vm.selectedCalendarDate, displayedComponents: .date)
                .datePickerStyle(.graphical)
                .tint(Theme.securityGold)
                .colorScheme(.dark)
                .padding(.horizontal, Theme.screenPadding)
                .banknoteCard()
                .padding(.horizontal, Theme.screenPadding)
            
            Text("EARNINGS ON THIS DATE")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)
            
            if vm.calendarDays.isEmpty && !vm.isLoading {
                Text("No earnings announcements on this date.")
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                    .foregroundColor(Theme.inkTertiary)
                    .padding(.vertical, Theme.Spacing.xLarge)
            } else {
                LazyVStack(spacing: Theme.Spacing.card) {
                    ForEach(vm.calendarDays) { day in
                        calendarDayCard(day)
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
    
    private func calendarDayCard(_ day: EarningsCalendarDay) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                Text(day.ticker)
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                if let qtr = day.quarter {
                    Text(qtr.uppercased())
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundColor(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, 2)
                        .background(Theme.securityGold.opacity(0.1))
                        .cornerRadius(Theme.CornerRadius.small)
                }
            }
            if let name = day.company_name {
                Text(name)
                    .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                    .foregroundColor(Theme.inkSecondary)
                    .lineLimit(1)
            }
            if let spark = day.sparkline, !spark.isEmpty {
                sparklineView(spark)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
    
    private func sparklineView(_ data: [Double]) -> some View {
        let minVal = data.min() ?? 0
        let maxVal = data.max() ?? 1
        let range = max(maxVal - minVal, 0.01)
        let isUp = (data.last ?? 0) >= (data.first ?? 0)
        return GeometryReader { geo in
            Path { path in
                for (i, v) in data.enumerated() {
                    let x = geo.size.width * CGFloat(i) / CGFloat(max(data.count - 1, 1))
                    let y = geo.size.height * (1 - CGFloat((v - minVal) / range))
                    if i == 0 { path.move(to: CGPoint(x: x, y: y)) }
                    else { path.addLine(to: CGPoint(x: x, y: y)) }
                }
            }
            .stroke(isUp ? Theme.bullGreen : Theme.bearRed, lineWidth: 1.5)
        }
        .frame(height: 30)
        .padding(.top, Theme.Spacing.xSmall)
    }
}

// MARK: - Surprise Card

struct SurpriseCard: View {
    let surprise: EarningsSurprise
    
    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            // Top row
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(surprise.ticker)
                        .font(Theme.serialNumberFont(size: 17, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                    Text(surprise.company_name)
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                        .foregroundColor(Theme.inkSecondary)
                        .lineLimit(1)
                }
                Spacer()
                surpriseChip
            }
            
            GuillocheDivider()
            
            // EPS comparison
            HStack(alignment: .bottom) {
                epsColumn(label: "EST EPS", value: surprise.estimated_eps, color: Theme.inkTertiary)
                Spacer()
                epsColumn(label: "ACTUAL", value: surprise.actual_eps, color: Theme.inkPrimary)
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text("SURPRISE")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                    if let pct = surprise.surprise_pct {
                        Text(IndianFormatter.percent(pct))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 20, relativeTo: .title3))
                            .foregroundColor(classificationColor)
                    } else { Text("--").font(Theme.serialNumberFont(size: 16, relativeTo: .body)).foregroundColor(Theme.inkSecondary) }
                }
            }
            
            // Footer: pattern + reaction
            if surprise.serial_pattern != nil || surprise.post_price_5d != nil {
                GuillocheDivider()
                HStack {
                    if let pattern = surprise.serial_pattern {
                        Label(pattern.uppercased(), systemImage: surprise.classification == "BEAT" ? "flame.fill" : "arrow.triangle.2.circlepath")
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .foregroundColor(Theme.securityGold)
                    }
                    Spacer()
                    if let post5d = surprise.post_price_5d {
                        HStack(spacing: Theme.Spacing.xSmall) {
                            Text("5D:")
                                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                .foregroundColor(Theme.inkTertiary)
                            Text(IndianFormatter.percent(post5d))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                                .font(Theme.serialNumberFont(size: 13, relativeTo: .caption))
                                .foregroundColor(post5d >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .overlay(alignment: .topLeading) {
            Rectangle().fill(classificationColor).frame(width: 3).clipShape(RoundedRectangle(cornerRadius: 2))
        }
    }
    
    private func epsColumn(label: String, value: Double?, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
            Text(value != nil ? "₹\(String(format: "%.2f", value!))" : "--")
                .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                .foregroundColor(color)
        }
    }
    
    private var surpriseChip: some View {
        Text(surprise.classification)
            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
            .tracking(0.5)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.xSmall)
            .background(classificationColor.opacity(0.1))
            .foregroundColor(classificationColor)
            .cornerRadius(Theme.CornerRadius.small)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(classificationColor.opacity(0.3), lineWidth: 0.5))
    }
    
    private var classificationColor: Color {
        switch surprise.classification {
        case "BEAT": return Theme.bullGreen
        case "MISS": return Theme.bearRed
        default: return Theme.holdAmber
        }
    }
}

// MARK: - Help View

struct EarningsSurpriseHelpView: View {
    @Environment(\.dismiss) var dismiss
    
    private let sections: [(icon: String, title: String, detail: String)] = [
        ("chart.bar.doc.horizontal.fill", "Surprise Cards",
         "Each card shows a company's earnings announcement. The BEAT (green), MISS (red), or INLINE (amber) badge tells you if actual EPS exceeded, fell short of, or matched analyst estimates. The percentage shows the magnitude of the surprise."),
        ("calendar", "Calendar View",
         "Tap the calendar icon to switch to a date-picker view. Select any date to see which companies are reporting earnings that day. Use the sparkline charts to see 7-day price action leading up to the announcement."),
        ("flame.fill", "Serial Patterns",
         "A 'BEAT STREAK' indicates the company has BEAT estimates for multiple consecutive quarters — a positive signal. A 'MISS STREAK' suggests structural issues. Watch for pattern breaks."),
        ("chart.line.uptrend.xyaxis", "Post-Earnings Reaction",
         "The 5D reaction shows how the stock moved in the 5 trading days after the announcement. A BEAT with negative 5D reaction may mean 'buy the rumor, sell the news' or higher expectations were already priced in."),
        ("bolt.fill", "Historical Score",
         "The decoder score (0–100) reflects how reliable the estimate was. Higher scores mean the analyst consensus was more accurate historically for this company. Use this to gauge estimate quality."),
    ]
    
    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .twoHundred)
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text("HOW TO READ")
                                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                                .tracking(1.5)
                                .foregroundColor(Theme.inkTertiary)
                                .padding(.horizontal, Theme.screenPadding)
                            Text("Earnings surprises reveal which companies are beating expectations — a key driver of stock prices.")
                                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                .foregroundColor(Theme.inkPrimary)
                                .lineSpacing(4)
                                .padding(.horizontal, Theme.screenPadding)
                        }
                        
                        ForEach(Array(sections.enumerated()), id: \.offset) { idx, sec in
                            helpCard(idx: idx, section: sec)
                        }
                    }
                    .padding(.top, Theme.Spacing.large)
                    Spacer(minLength: 80)
                }
            }
            .navigationTitle("Earnings Surprise Guide")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { HapticManager.selection(); dismiss() }.buttonStyle(EKPressStyle())
                        .font(Theme.officialStampFont(size: 12, relativeTo: .body))
                        .foregroundColor(Theme.securityGold)
                }
            }
        }
    }
    
    private func helpCard(idx: Int, section: (icon: String, title: String, detail: String)) -> some View {
        HStack(alignment: .top, spacing: Theme.Spacing.card) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .fill(Theme.securityGold.opacity(0.08))
                    .frame(width: 40, height: 40)
                Text("\(idx + 1)")
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                    .foregroundColor(Theme.securityGold)
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: section.icon)
                        .font(Theme.engravedSerif(size: 14, weight: .medium))
                        .foregroundColor(Theme.securityGold)
                    Text(section.title)
                        .font(Theme.engravedSerif(size: 15, weight: .semibold, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                }
                Text(section.detail)
                    .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                    .foregroundColor(Theme.inkSecondary)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}
