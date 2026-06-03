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

            VStack(spacing: 0) {
                pageHeader
                // 6.1 Pinned Advisory Banner
                advisoryBanner
                // 6.5 Search bar
                searchBar
                Divider().opacity(0.4)
                companyList
            }
        }
        .task { vm.load() }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("PRE-IPO & UNLISTED MARKET")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                    .tracking(2)
                    .foregroundColor(Theme.securityGold)
                Text("OTC Secondary Transaction Valuations")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 10)
        .background(Theme.canvasDeep)
    }

    // MARK: 6.1 Live Trade Advisory Banner

    private var advisoryBanner: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(vm.advisories) { adv in
                    advisoryCard(adv)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
        }
        .background(Theme.canvasDeep)
    }

    private func advisoryCard(_ adv: OTCAdvisory) -> some View {
        ZStack {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("SUPER PRO ADVISORY")
                        .font(.system(size: 8, weight: .bold, design: .monospaced))
                        .tracking(1.5)
                        .foregroundColor(Theme.securityGold)
                    Spacer()
                    Image(systemName: "lock.fill")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.securityGold.opacity(0.6))
                }
                Text(adv.companyName)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Theme.inkPrimary)
                HStack(spacing: 12) {
                    metricTag("Entry", IndianFormatter.price(adv.entryPrice))
                    metricTag("Tgt", IndianFormatter.price(adv.targetPrice))
                    metricTag("SL", IndianFormatter.price(adv.stopLoss))
                }
                // 6.1 Rationale text blurred for non-premium
                Text(adv.rationale)
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkSecondary)
                    .lineLimit(2)
                    .blur(radius: isSuperpro ? 0 : 4)
            }
            .padding(12)
            .frame(width: 260)
            .background(Theme.canvasDeep)
            .cornerRadius(8)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.securityGold.opacity(0.25), lineWidth: 1))

            // 6.1 Premium Token Security Lock
            if !isSuperpro {
                RoundedRectangle(cornerRadius: 8)
                    .fill(Theme.canvasDeep.opacity(0.6))
                    .overlay(
                        VStack(spacing: 4) {
                            Image(systemName: "lock.shield")
                                .font(.system(size: 18))
                                .foregroundColor(Theme.securityGold)
                            Text("SUPER PRO")
                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                .tracking(2)
                                .foregroundColor(Theme.securityGold)
                        }
                    )
            }
        }
        .frame(width: 260)
    }

    private func metricTag(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.system(size: 8, weight: .bold))
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundColor(Theme.inkPrimary)
        }
    }

    // MARK: 6.5 Search Bar

    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 13))
                .foregroundColor(Theme.inkTertiary)
            TextField("Search unlisted companies…", text: $vm.searchText)
                .font(.system(size: 13))
                .foregroundColor(Theme.inkPrimary)
            if !vm.searchText.isEmpty {
                Button(action: { vm.searchText = "" }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(Theme.inkTertiary)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(Theme.canvasDeep)
    }

    // MARK: Company List

    private var companyList: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                if vm.isLoading && vm.companies.isEmpty {
                    ForEach(0..<4, id: \.self) { _ in companyPlaceholder }
                } else {
                    ForEach(vm.filteredCompanies) { company in
                        companyRow(company)
                    }
                }
            }
            .padding(16)
        }
    }

    // MARK: 6.2 / 6.4 Company Row with Collapsible Detail

    private func companyRow(_ company: UnlistedCompany) -> some View {
        let isExpanded = vm.expandedIds.contains(company.id)
        let isBookmarked = vm.bookmarkedIds.contains(company.id)
        let isPos = company.changePct >= 0

        return VStack(alignment: .leading, spacing: 0) {
            // Main Row
            HStack(spacing: 12) {
                // Company initials badge
                ZStack {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Theme.securityGold.opacity(0.10))
                        .frame(width: 44, height: 44)
                    Text(String(company.name.prefix(2)).uppercased())
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundColor(Theme.securityGold)
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text(company.name)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(Theme.inkPrimary)
                    Text(company.sector)
                        .font(.system(size: 10))
                        .foregroundColor(Theme.inkSecondary)
                }

                Spacer()

                // 6.2 LTP + delta
                VStack(alignment: .trailing, spacing: 3) {
                    Text(IndianFormatter.price(company.ltp))
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                    HStack(spacing: 3) {
                        Image(systemName: isPos ? "arrow.up" : "arrow.down")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(isPos ? Theme.bullGreen : Theme.bearRed)
                        Text(IndianFormatter.delta(company.changePct))
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(isPos ? Theme.bullGreen : Theme.bearRed)
                    }
                }

                // Bookmark
                Button(action: { vm.toggleBookmark(company.id); HapticManager.impact(.light) }) {
                    Image(systemName: isBookmarked ? "bookmark.fill" : "bookmark")
                        .font(.system(size: 13))
                        .foregroundColor(isBookmarked ? Theme.securityGold : Theme.inkTertiary)
                }

                // 6.4 Chevron Expand Control
                Button(action: { withAnimation(.easeInOut(duration: 0.25)) { vm.toggleExpand(company.id) } }) {
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(Theme.inkTertiary)
                }
            }
            .padding(14)

            // 6.4 Expanded Metadata Sheet
            if isExpanded {
                VStack(alignment: .leading, spacing: 12) {
                    Divider().opacity(0.4)

                    Text(company.description)
                        .font(.system(size: 12))
                        .foregroundColor(Theme.inkSecondary)
                        .lineSpacing(3)

                    // 6.3 OTC Pricing Detail
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("OTC LTP")
                                .font(.system(size: 8, weight: .bold, design: .monospaced))
                                .foregroundColor(Theme.inkTertiary)
                            Text(IndianFormatter.price(company.ltp))
                                .font(.system(size: 16, weight: .bold, design: .monospaced))
                                .foregroundColor(Theme.inkPrimary)
                        }
                        Divider().frame(height: 36)
                        VStack(alignment: .leading, spacing: 3) {
                            Text("ABS CHANGE")
                                .font(.system(size: 8, weight: .bold, design: .monospaced))
                                .foregroundColor(Theme.inkTertiary)
                            Text(IndianFormatter.formatLakhsCrores(company.changeAbs))
                                .font(.system(size: 14, weight: .semibold, design: .monospaced))
                                .foregroundColor(company.changeAbs >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                        Divider().frame(height: 36)
                        VStack(alignment: .leading, spacing: 3) {
                            Text("% CHANGE")
                                .font(.system(size: 8, weight: .bold, design: .monospaced))
                                .foregroundColor(Theme.inkTertiary)
                            Text(IndianFormatter.delta(company.changePct))
                                .font(.system(size: 14, weight: .semibold, design: .monospaced))
                                .foregroundColor(company.changePct >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                    }

                    // Key Metrics grid
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                        ForEach(Array(company.keyMetrics.sorted(by: { $0.key < $1.key })), id: \.key) { key, val in
                            HStack {
                                Text(key)
                                    .font(.system(size: 10))
                                    .foregroundColor(Theme.inkTertiary)
                                Spacer()
                                Text(val)
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundColor(Theme.inkPrimary)
                            }
                            .padding(8)
                            .background(Theme.canvasDeep)
                            .cornerRadius(5)
                        }
                    }
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 14)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .banknoteCard()
    }

    private var companyPlaceholder: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 6).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 44, height: 44)
            VStack(alignment: .leading, spacing: 6) {
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 130, height: 12)
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 80, height: 10)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 6) {
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 70, height: 12)
                RoundedRectangle(cornerRadius: 3).fill(Theme.inkTertiary.opacity(0.10)).frame(width: 50, height: 10)
            }
        }
        .padding(14)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - SwiftUI Preview

#Preview("Pre-IPO Marketplace") {
    PreIPOMarketplaceView()
        .environmentObject(AuthManager())
}
