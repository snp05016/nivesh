import Foundation

// MARK: - Home section IDs (HomeScreen section order and scroll targets)

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
