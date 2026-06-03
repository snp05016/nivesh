# Nivesh (निवेश) — Frontend Context

> Paste this into Claude to get frontend context before brainstorming next steps.
> Last updated: June 3, 2026. Reflects current shipped state.

---

## What Is This

**Nivesh Frontend** is a premium SwiftUI application styled like an Indian Rupee banknote. It provides high-end visual analysis of the Indian stock market, integrating a banknote-themed design system with advanced AI signals.

---

## Design System (Banknote Aesthetic)

- **Guilloché Patterns**: Animated dividers and background borders.
- **Security Thread**: Gold vertical strip with micro-text.
- **Ashoka Stamp**: Lion capital stamp integrated into Home.
- **RBI Seal**: Circular watermark on all cards.
- **Paper Texture**: 500-grain canvas noise overlay.
- **Verified Badge**: Visual indicator for verified users/data.
- **News Reader View**: Editorial layout with large hero images and serif typography.

---

## iOS App — 8 Tabs

| Tab | View | Description |
|---|---|---|
| **Home** | `HomeScreen` | Morning Brief (Priority Items), Indices strip, Sector Pulse heatmap. |
| **Directory** | `SearchScreen` | Bilingual search (खोज) with screener presets (Hidden Gems, Momentum). |
| **Assets** | `PortfolioScreen` | Rupee-styled hero card, 10-segment risk meter, Red Flags system. |
| **Alerts** | `AlertsScreen` | Manage price targets. Triggered alerts show on Home. |
| **Archives** | `HistoryScreen` | Cached analysis reports with Signal Change diffs. |
| **Compare** | `CompareScreen` | Side-by-side stock comparison (Price, P/E, Signal). |
| **Registry** | `SettingsScreen` | User verification, App preferences, APNs registration. |
| **Journal** | `TradeJournalScreen`| Log entry reasons, moods (FOMO/Contrarian), and outcomes. |

---

## Analysis Screen — Tabbed Layout

- **Overview**: Shows **Signal Change Flags**, **Confidence Rationale**, and **Price Projections**.
- **Analysis**: **Broker Consensus Strip**, Macro strip (Brent, VIX), and **Macro Impact Banner**.
- **Fundaments**: **Insider Trend Bars**, Quarterly Financials, and Valuation Badge (vs 3Y Avg).
- **Charts**: 11 charts including **Stock vs Nifty** (relative benchmark).
- **News**: Cards with images/summaries; opens **News Reader View**.

---

## Specialized Features

1.  **Advisor Matrix**: Integration of expert sentiment from the "Advisor Intelligence" pipeline.
2.  **Risk & Surveillance**: Visual ASM/GSM status chips and color-coded Red Flags (CRITICAL/WARNING/WATCH).
3.  **Tutorial & Onboarding**: `TutorialOverlayView` and `LaunchSequenceView` for new users.
4.  **Haptics & Animations**: Centralized `HapticManager` with `EKPressStyle` spring animations.
5.  **Signal Flip Detection**: Visual indicators when a stock's outlook changes (BULLISH → NEUTRAL).
6.  **Hardened Market Data**: Reliable Home Screen indices/sectors via history fallbacks (no "N/A" states).

---

## Technical Architecture

- **State Management**: `@MainActor` ViewModels with `async/await`.
- **Navigation**: `TabView` with index-based step tracking for tutorials.
- **Networking**: `NetworkManager.shared` with custom model decoding.
- **Persistence**: `UserDefaults` for auth and `@AppStorage` for UI state.
