import SwiftUI
import Combine

// MARK: - Pre-IPO Marketplace ViewModel

@MainActor
class PreIPOViewModel: ObservableObject {
    @Published var companies: [UnlistedCompany] = []
    @Published var advisories: [OTCAdvisory] = []
    @Published var searchText: String = ""
    @Published var expandedIds: Set<String> = []
    @Published var isLoading = false
    @AppStorage("preIPO_bookmarks") private var bookmarksRaw: String = ""

    var bookmarkedIds: Set<String> {
        get { Set(bookmarksRaw.split(separator: ",").map(String.init)) }
        set { bookmarksRaw = newValue.joined(separator: ",") }
    }

    // Mock data for preview / offline — production fetches from backend
    private let mockCompanies: [UnlistedCompany] = [
        UnlistedCompany(id: "MOHAN_MEAKIN", name: "Mohan Meakin Ltd", sector: "Beverages",
                        ltp: 8550, prevLtp: 8200,
                        description: "India's oldest brewery and distillery with iconic brands including Old Monk rum. Pre-IPO OTC valuation reflects strong brand equity and distribution moat.",
                        keyMetrics: ["Revenue": "₹1,200 Cr", "PAT": "₹95 Cr", "P/E (est.)": "28x"]),
        UnlistedCompany(id: "APOLLO_GREEN", name: "Apollo Green Energy", sector: "Renewables",
                        ltp: 1240, prevLtp: 1190,
                        description: "Pure-play renewable energy platform targeting 5 GW solar capacity by 2028. Unlisted OTC price tracks secondary transaction data from SEBI-registered intermediaries.",
                        keyMetrics: ["Capacity": "900 MW", "Order Book": "₹4,800 Cr", "D/E": "1.2x"]),
        UnlistedCompany(id: "NSE_UNLISTED", name: "National Stock Exchange", sector: "Financial Infrastructure",
                        ltp: 4800, prevLtp: 4650,
                        description: "India's largest stock exchange by derivative volumes. Pre-IPO valuation tracked via secondary OTC market. IPO filing status: pending SEBI approval.",
                        keyMetrics: ["Revenue": "₹12,400 Cr", "PAT": "₹8,300 Cr", "Market Share": "92%"]),
        UnlistedCompany(id: "BYJUS_UNLISTED", name: "Manipal Health (Unlisted)", sector: "Healthcare",
                        ltp: 950, prevLtp: 980,
                        description: "Multi-specialty hospital network operator. OTC price reflects recent secondary block trades at depressed valuations ahead of potential IPO in 2027.",
                        keyMetrics: ["Beds": "9,000+", "Revenue": "₹4,200 Cr", "EBITDA Margin": "18%"]),
    ]

    private let mockAdvisories: [OTCAdvisory] = [
        OTCAdvisory(id: "ADV1", companyName: "Mohan Meakin Ltd",
                    entryPrice: 8200, targetPrice: 9800, stopLoss: 7600,
                    rationale: "Accumulation zone detected at 8,000–8,400. Brand re-rating cycle in progress post-premiumisation launch.",
                    isPremium: true),
        OTCAdvisory(id: "ADV2", companyName: "NSE Unlisted",
                    entryPrice: 4600, targetPrice: 5500, stopLoss: 4200,
                    rationale: "IPO premium expected on listing. Accumulate below 4,700 for 18-month horizon.",
                    isPremium: true),
    ]

    func load() {
        isLoading = true
        Task {
            // Production: fetch from /api/v1/unlisted/companies
            // For now, seed mock data
            self.companies = mockCompanies
            self.advisories = mockAdvisories
            isLoading = false
        }
    }

    var filteredCompanies: [UnlistedCompany] {
        guard !searchText.trimmingCharacters(in: .whitespaces).isEmpty else { return companies }
        let q = searchText.lowercased()
        // 6.5 Fuzzy token matching — simple contains + prefix for offline use
        return companies.filter {
            $0.name.lowercased().contains(q) ||
            $0.id.lowercased().contains(q) ||
            $0.sector.lowercased().contains(q) ||
            fuzzyMatch(query: q, target: $0.name.lowercased())
        }
    }

    /// Lightweight offline fuzzy matching — 2-gram overlap ratio
    private func fuzzyMatch(query: String, target: String) -> Bool {
        guard query.count >= 3 else { return false }
        let qGrams = bigrams(query)
        let tGrams = bigrams(target)
        let overlap = qGrams.intersection(tGrams).count
        let ratio = Double(overlap * 2) / Double(qGrams.count + tGrams.count)
        return ratio > 0.4
    }

    private func bigrams(_ s: String) -> Set<String> {
        guard s.count >= 2 else { return [] }
        var result = Set<String>()
        let chars = Array(s)
        for i in 0..<(chars.count - 1) {
            result.insert(String([chars[i], chars[i+1]]))
        }
        return result
    }

    func toggleExpand(_ id: String) {
        if expandedIds.contains(id) { expandedIds.remove(id) } else { expandedIds.insert(id) }
    }

    func toggleBookmark(_ id: String) {
        var bm = bookmarkedIds
        if bm.contains(id) { bm.remove(id) } else { bm.insert(id) }
        bookmarkedIds = bm
    }
}

// MARK: - Pre-IPO Marketplace View

struct PreIPOMarketplaceView: View {
    @StateObject private var vm = PreIPOViewModel()
    @EnvironmentObject var authManager: AuthManager
    private let isSuperpro: Bool = true

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            VStack(spacing: Theme.Spacing.none) {
                pageHeader
                // 6.1 Pinned Advisory Banner
                advisoryBanner
                // 6.5 Search bar
                searchBar
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                companyList
            }
        }
        .task { vm.load() }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("प्री-आईपीओ और अनलिस्टेड")
                    .font(Theme.hindiFont(size: 11))
                    .foregroundStyle(Theme.inkSecondary)
                Text("PRE-IPO & UNLISTED MARKET")
                    .font(Theme.engravedSerif(size: 24, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)
                Text("OTC Secondary Transaction Valuations")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
        .padding(.bottom, Theme.Spacing.medium)
        .background(Theme.canvasDeep)
    }

    // MARK: 6.1 Live Trade Advisory Banner

    private var advisoryBanner: some View {
        ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.standard) {
                ForEach(vm.advisories) { adv in
                    advisoryCard(adv, cardWidth: UIScreen.main.bounds.width * 0.75)
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
        }
        .scrollIndicators(.hidden)
        .background(Theme.canvasDeep)
    }

    private func advisoryCard(_ adv: OTCAdvisory, cardWidth: CGFloat) -> some View {
        ZStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                HStack {
                    Text("SUPER PRO ADVISORY")
                        .font(Theme.serialNumberFont(size: 8))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)
                    Spacer()
                    Image(systemName: "lock.fill")
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(Theme.securityGold.opacity(0.6))
                }
                Text(adv.companyName)
                    .font(Theme.officialStampFont(size: 13))
                    .foregroundStyle(Theme.inkPrimary)
                HStack(spacing: Theme.Spacing.standard) {
                    metricTag("Entry", IndianFormatter.price(adv.entryPrice))
                    metricTag("Tgt", IndianFormatter.price(adv.targetPrice))
                    metricTag("SL", IndianFormatter.price(adv.stopLoss))
                }
                // 6.1 Rationale text blurred for non-premium
                Text(adv.rationale)
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(2)
                    .blur(radius: isSuperpro ? 0 : 4)
            }
            .padding(Theme.Spacing.standard)
            .frame(width: cardWidth)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.securityGold.opacity(0.25), lineWidth: 1))

            // 6.1 Premium Token Security Lock
            if !isSuperpro {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .fill(Theme.canvasDeep.opacity(0.6))
                    .overlay(
                        VStack(spacing: Theme.Spacing.small) {
                            Image(systemName: "lock.shield")
                                .font(Theme.officialStampFont(size: 18))
                                .foregroundStyle(Theme.securityGold)
                            Text("SUPER PRO")
                                .font(Theme.serialNumberFont(size: 9))
                                .tracking(2)
                                .foregroundStyle(Theme.securityGold)
                        }
                    )
            }
        }
        .frame(width: cardWidth)
    }

    private func metricTag(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(Theme.inkPrimary)
        }
    }

    // MARK: 6.5 Search Bar

    private var searchBar: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "magnifyingglass")
                .font(Theme.officialStampFont(size: 13))
                .foregroundStyle(Theme.inkTertiary)
            TextField("Search unlisted companies…", text: $vm.searchText)
                .font(Theme.officialStampFont(size: 13))
                .foregroundStyle(Theme.inkPrimary)
            if !vm.searchText.isEmpty {
                Button(action: { HapticManager.selection(); vm.searchText = "" }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
                .accessibilityLabel("Clear search")
            }
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, 9)
        .background(Theme.canvasDeep)
    }

    // MARK: Company List

    private var companyList: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.medium) {
                if vm.isLoading && vm.companies.isEmpty {
                    ForEach(0..<4, id: \.self) { _ in companyPlaceholder }
                } else {
                    ForEach(vm.filteredCompanies) { company in
                        companyRow(company)
                    }
                }
            }
            .padding(Theme.Spacing.card)
        }
    }

    // MARK: 6.2 / 6.4 Company Row with Collapsible Detail

    private func companyRow(_ company: UnlistedCompany) -> some View {
        let isExpanded = vm.expandedIds.contains(company.id)
        let isBookmarked = vm.bookmarkedIds.contains(company.id)
        let isPos = company.changePct >= 0

        return VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            // Main Row
            HStack(spacing: Theme.Spacing.standard) {
                // Company initials badge
                ZStack {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                        .fill(Theme.securityGold.opacity(0.10))
                        .frame(width: 44, height: 44)
                    Text(String(company.name.prefix(2)).uppercased())
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundStyle(Theme.securityGold)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(company.name)
                        .font(Theme.officialStampFont(size: 13))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(company.sector)
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(Theme.inkSecondary)
                }

                Spacer()

                // 6.2 LTP + delta
                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text(IndianFormatter.price(company.ltp))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundStyle(Theme.inkPrimary)
                    HStack(spacing: Theme.Spacing.xSmall) {
                        Image(systemName: isPos ? "arrow.up" : "arrow.down")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(isPos ? Theme.bullGreen : Theme.bearRed)
                        Text(IndianFormatter.delta(company.changePct))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(isPos ? Theme.bullGreen : Theme.bearRed)
                    }
                }

                // Bookmark
                Button(action: { HapticManager.selection(); vm.toggleBookmark(company.id); HapticManager.impact(.light) }) {
                    Image(systemName: isBookmarked ? "bookmark.fill" : "bookmark")
                        .font(Theme.officialStampFont(size: 13))
                        .foregroundStyle(isBookmarked ? Theme.securityGold : Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
                .accessibilityLabel("Toggle bookmark")

                // 6.4 Chevron Expand Control
                Button(action: { HapticManager.selection(); withAnimation(.easeInOut(duration: 0.25)) { vm.toggleExpand(company.id) } }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(Theme.officialStampFont(size: 11))
                        .foregroundStyle(Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
                .accessibilityLabel("Toggle expand")
            }
            .padding(Theme.Spacing.card)

            // 6.4 Expanded Metadata Sheet
            if isExpanded {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                    Text(company.description)
                        .font(Theme.officialStampFont(size: 12))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(3)

                    // 6.3 OTC Pricing Detail
                    HStack(spacing: Theme.Spacing.standard) {
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text("OTC LTP")
                                .font(Theme.serialNumberFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.price(company.ltp))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        Rectangle().fill(Theme.inkPrimary.opacity(0.10)).frame(width: 0.5, height: 36)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text("ABS CHANGE")
                                .font(Theme.serialNumberFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.formatLakhsCrores(company.changeAbs))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundStyle(company.changeAbs >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                        Rectangle().fill(Theme.inkPrimary.opacity(0.10)).frame(width: 0.5, height: 36)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text("% CHANGE")
                                .font(Theme.serialNumberFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                            Text(IndianFormatter.delta(company.changePct))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundStyle(company.changePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                    }

                    // Key Metrics grid
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                        ForEach(Array(company.keyMetrics.sorted(by: { $0.key < $1.key })), id: \.key) { key, val in
                            HStack {
                                Text(key)
                                    .font(Theme.officialStampFont(size: 10))
                                    .foregroundStyle(Theme.inkTertiary)
                                Spacer()
                                Text(val)
                                    .font(Theme.officialStampFont(size: 10))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            .padding(Theme.Spacing.medium)
                            .background(Theme.canvasDeep)
                            .cornerRadius(Theme.CornerRadius.tight)
                        }
                    }
                }
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.bottom, Theme.Spacing.card)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .banknoteCard()
    }

    private var companyPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 44, height: 44)
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.37, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.23, height: 10)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.tight) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.14, height: 10)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - SwiftUI Preview

#Preview("Pre-IPO Marketplace") {
    PreIPOMarketplaceView()
        .environmentObject(AuthManager())
}
