import SwiftUI

// MARK: - Section IDs (shared with HomeScreen)

enum HomeSectionID: String, CaseIterable, Identifiable, Codable {
    var id: String { rawValue }
    case top           = "home.top"
    case portfolio     = "home.portfolio"
    case indices       = "home.indices"
    case watchlist     = "home.watchlist"
    case sectors       = "home.sectors"
    case morning       = "home.morning"
    case news          = "home.news"
    case youtube       = "home.youtube"
    case earnings      = "home.earnings"
    case marketPulse   = "home.mkt.pulse"
    case momentum      = "home.mkt.momentum"
    case macroAlt      = "home.mkt.macro"
    case institutional = "home.mkt.institutional"

    var title: String {
        switch self {
        case .top:           return "Today's Action"
        case .portfolio:     return "Portfolio"
        case .indices:       return "Market Indices"
        case .watchlist:     return "Watchlist"
        case .sectors:       return "Sector Pulse"
        case .morning:       return "Morning Brief"
        case .news:          return "Market News"
        case .youtube:       return "Expert Videos"
        case .earnings:      return "Upcoming Results"
        case .marketPulse:   return "Market Pulse"
        case .momentum:      return "Momentum Scan"
        case .macroAlt:      return "Macro & Alternatives"
        case .institutional: return "Institutional Flow"
        }
    }

    var hindiTitle: String {
        switch self {
        case .top:           return "आज की कार्रवाई"
        case .portfolio:     return "निवेश पोर्टफोलियो"
        case .indices:       return "बाजार सूचकांक"
        case .watchlist:     return "बाज़ार की निगरानी"
        case .sectors:       return "क्षेत्र प्रदर्शन"
        case .morning:       return "प्रातःकालीन सारांश"
        case .news:          return "ताज़ा समाचार"
        case .youtube:       return "विशेषज्ञ विश्लेषण"
        case .earnings:      return "आगामी परिणाम"
        case .marketPulse:   return "बाजार की नब्ज"
        case .momentum:      return "गति विश्लेषण"
        case .macroAlt:      return "वृहद अर्थव्यवस्था"
        case .institutional: return "संस्थागत प्रवाह"
        }
    }

    var icon: String {
        switch self {
        case .top:           return "bolt.fill"
        case .portfolio:     return "indianrupeesign.circle.fill"
        case .indices:       return "waveform.path.ecg"
        case .watchlist:     return "eye.fill"
        case .sectors:       return "chart.bar.fill"
        case .morning:       return "sun.horizon.fill"
        case .news:          return "newspaper.fill"
        case .youtube:       return "play.rectangle.fill"
        case .earnings:      return "calendar.badge.clock"
        case .marketPulse:   return "waveform"
        case .momentum:      return "arrow.up.right.circle.fill"
        case .macroAlt:      return "globe.asia.australia.fill"
        case .institutional: return "building.columns.fill"
        }
    }
}

// MARK: - NiveshNavigationSidebar

struct NiveshNavigationSidebar: View {
    @Binding var isOpen: Bool
    @Binding var scrollTarget: String?

    var body: some View {
        let drawerWidth = UIScreen.main.bounds.width * 0.78
        ZStack(alignment: .leading) {
            // Scrim — transparent when closed, blocks touches only when open
            Color.black
                .opacity(isOpen ? 0.52 : 0)
                .ignoresSafeArea()
                .onTapGesture { close() }
                .allowsHitTesting(isOpen)

            // Drawer — always in tree, offset off-screen when closed
            DrawerContent(
                isOpen: $isOpen,
                scrollTarget: $scrollTarget,
                drawerWidth: drawerWidth
            )
            .frame(width: drawerWidth)
            .offset(x: isOpen ? 0 : -drawerWidth)
            // Crucial: Only allow hits on the drawer itself if it's open,
            // but the drawer content should always handle its internal touches
            .allowsHitTesting(isOpen)
        }
        .ignoresSafeArea()
        // Removed the .allowsHitTesting(isOpen) from the outer ZStack
        // to ensure the transition/animation logic works correctly without clipping
        .animation(.spring(response: 0.38, dampingFraction: 0.88), value: isOpen)
    }

    private func close() {
        isOpen = false
    }
}

// MARK: - Drawer content (separate struct limits re-render scope)

private struct DrawerContent: View {
    @Binding var isOpen: Bool
    @Binding var scrollTarget: String?
    let drawerWidth: CGFloat

    var body: some View {
        ZStack(alignment: .topLeading) {
            Theme.canvasDeep.ignoresSafeArea()
            SecurityThread()

            VStack(spacing: Theme.Spacing.none) {
                header
                Rectangle().fill(Theme.securityGold.opacity(0.28)).frame(height: 0.5)

                ScrollView() {
                    VStack(spacing: Theme.Spacing.none) {
                        ForEach(Array(HomeSectionID.allCases.enumerated()), id: \.element.id) { i, section in
                            BookmarkRow(number: i + 1, section: section) {
                                scrollTarget = section.rawValue
                                withAnimation(.spring(response: 0.36, dampingFraction: 0.86)) { isOpen = false }
                            }
                            if i < HomeSectionID.allCases.count - 1 {
                                Rectangle().fill(Theme.inkTertiary.opacity(0.1)).frame(height: 0.5).padding(.leading, 56)
                            }
                        }
                    }
                    .padding(.vertical, Theme.Spacing.medium)
                }
                .scrollIndicators(.hidden)
                .layoutPriority(1) // Ensure ScrollView takes priority in the VStack

                Spacer(minLength: 0)

                // Footer hint
                VStack(spacing: Theme.Spacing.none) {
                    Rectangle().fill(Theme.securityGold.opacity(0.18)).frame(height: 0.5)
                    Text("TAP TO JUMP TO SECTION")
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary) // contrast verified for dark canvasDeep bg
                        .tracking(1.5)
                        .padding(.vertical, Theme.Spacing.card)
                }
            }
        }
        .ignoresSafeArea(edges: .vertical)
        .shadow(color: .black.opacity(0.26), radius: 16, x: 6, y: 0)
    }

    private var header: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("NIVESH")
                    .font(Theme.engravedSerif(size: 16, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)
                Text("SECTION NAVIGATOR")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.securityGold)
                    .tracking(1.5)
            }
            Spacer()
            Button {
                withAnimation(.spring(response: 0.36, dampingFraction: 0.86)) { isOpen = false }
            } label: {
                Image(systemName: "xmark")
                    .font(Theme.officialStampFont(size: 13))
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(Theme.Spacing.medium)
                    .background(Theme.inkPrimary.opacity(0.07))
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Close sidebar")
        }
        .padding(.horizontal, Theme.Spacing.screen)
        .padding(.top, 64) // safe area compensation
        .padding(.bottom, Theme.Spacing.card)
    }
}

// MARK: - Bookmark Row

private struct BookmarkRow: View {
    let number: Int
    let section: HomeSectionID
    let onTap: () -> Void

    var body: some View {
        Button(action: {
            HapticManager.selection()
            onTap()
        }) {
            HStack(spacing: Theme.Spacing.standard) {
                // Numbered badge
                ZStack {
                    Circle()
                        .fill(Theme.securityGold.opacity(0.13))
                        .frame(width: 32, height: 32)
                    Text("\(number)")
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundStyle(Theme.securityGold)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    HStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: section.icon)
                            .font(Theme.officialStampFont(size: 10))
                            .foregroundStyle(Theme.securityGold.opacity(0.85))
                        Text(section.title.uppercased())
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Text(section.hindiTitle)
                        .font(Theme.hindiFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary)
                }

                Spacer()

                Image(systemName: "arrow.right")
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.securityGold.opacity(0.5))
            }
            .padding(.horizontal, Theme.Spacing.screen)
            .padding(.vertical, Theme.Spacing.card)
            .background(Color.white.opacity(0.001)) // Ensure the entire row is tappable
        }
        .buttonStyle(.plain)
    }
}
