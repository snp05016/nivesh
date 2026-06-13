# Premium Dossier, Morning Brief Popup & Settings Expansion — Design Document

> Date: 13 June 2026 | Status: Design Approved | 3 independent streams

## Stream A: Extreme Analysis — Premium Dossier Redesign

**Goal:** Redesign the Extreme Analysis "AI REPORT" tab to look like a declassified intelligence dossier. No data changes — visual only.

**File:** `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift`

### Visual Language
- **Redaction bar section headers**: Each section title renders as a black bar with struck-through text on scroll-enter, then animates (spring, 0.4s) to reveal the actual title. Implemented via `RedactionSectionHeader(title:)` ViewModifier that watches scroll position.
- **Classified circular stamps**: `riskFactorsSection`, governance components, and `fundamentalsSection` get a red `CLASSIFIED` or `CONFIDENTIAL` circular stamp overlay in the top-right corner. `heroChartSection` gets "SATELLITE IMAGERY" stamp.
- **"TOP SECRET // EYES ONLY" watermark**: `aiVerdictCard` background gets a subtle, semi-transparent watermark text at 6° rotation.
- **Document footer**: Below `disclaimerSection`, a dossier-style footer: "DOCUMENT END · Nivesh AI Research Desk · Classification: UNCLASSIFIED".
- **Aged-paper background**: Slightly warmer tint on `DenominationBackground`. Subtle typewriter-texture `.opacity(0.02)` overlay.

### Implementation
- New components (in-file private structs):
  - `DossierSectionHeader(title:)` — redaction bar with animation
  - `ClassifiedStamp(text:)` — circular red stamp overlay
  - `DossierFooter()` — end-of-document footer
- Modified sections:
  - `heroChartSection` → add stamp
  - `aiVerdictCard` → add watermark
  - All 10+ section headers → replace with `DossierSectionHeader`
  - `riskFactorsSection`, `fundamentalsSection` → add stamp
- `extremeModeSwitcher` → unchanged
- Standard analysis tier → unchanged (dossier only for extreme)

---

## Stream B: Morning Brief — Full-Screen Alert + FAB

**Goal:** Morning Brief appears as a full-screen modern alert on first app open after configured time. After dismiss, a floating FAB persists on HomeScreen showing mood dot. Zero new API calls.

**Files:** `HomeScreen.swift`, new file `MorningBriefAlertView.swift`

### Behavior
- `@AppStorage("morningBriefShownDate")` — stores `"2026-06-13"` last-shown date
- `@AppStorage("morningBriefTime")` — existing setting, default "08:00"
- On `HomeScreen.onAppear`: if `morningBriefShownDate != today` AND `currentTime >= morningBriefTime` → show full-screen alert
- Does NOT fetch new data — uses existing `viewModel.morningBriefData`
- If data hasn't loaded yet when onAppear fires, show after data arrives (use `onChange(of: viewModel.morningBriefData)`)

### Full-Screen Alert (`MorningBriefAlertView.swift`)
- `DenominationBackground(.twoHundred)` backdrop
- Top: "⚡ MARKETS OPEN" with date and time in `officialStampFont`
- Center: Large banknote card with:
  - Mood-colored top strip (green/red/amber based on `briefData.mood`)
  - "📊 MARKET MOOD" label
  - Mood text in `engravedSerif` large
  - Summary text (scrollable if long)
  - Divider
  - Priority items list (if present)
  - "GOT IT" button at bottom — `EKPressStyle`, gold fill
- Bottom: "Nivesh AI · [date] [time]" attribution
- Dismissible via swipe-down (`.interactiveDismissDisabled(false)`) or button

### FAB (Floating Action Button)
- Renders only after brief has been shown AND before market close (15:30 IST)
- Position: `.overlay(alignment: .bottomTrailing)` on HomeScreen's outer ZStack
- Visual: 52×52pt circle, `Theme.surfaceElevated`, 2pt `Theme.securityGold` border, `book.pages` icon
- Mood-colored dot: 10pt circle at top-right of button (green/red/amber)
- Tap: sets `showMorningBrief = true`, opens the full-screen alert again
- Fade-in animation on first appear after dismiss

### State
```
@State private var showMorningBrief = false
@AppStorage("morningBriefShownDate") private var briefShownDate = ""
```

---

## Stream C: Settings — 4-Tab Banking Console

**Goal:** Expand SettingsScreen with 4 tabs and 30+ new settings. All `@AppStorage` — no backend.

**File:** `ios/StockApp/stockme/stockme/Views/SettingsScreen.swift`

### Tab Bar
- Internal pill-tab switcher (same pattern as `extremeModeSwitcher` in AnalysisScreen)
- Tabs: **Profile · Analysis · Appearance · Data**
- Active tab: `Theme.securityGold` fill, `Theme.canvas` text
- Inactive: `Theme.surfaceElevated` fill, `Theme.inkSecondary` text

### Tab Content — New Settings (Bold = NEW)

#### Tab 1: PROFILE
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| User card | Display | — | Existing, unchanged |
| **Default Scan Type** | Picker | `defaultScanType` | Ask Every Time / Standard / Deep / Extreme |
| **Auto-run on Stock Tap** | Toggle | `autoRunOnTap` | false |
| **Risk Tolerance** | Picker | `riskTolerance` | Conservative / Moderate / Aggressive |
| **Default Exchange** | Picker | `defaultExchange` | Auto / NSE / BSE |
| **Sector Blacklist** | Navigation | — | Opens `SectorBlacklistView` |
| **Min Market Cap** | Picker | `minMarketCap` | Any / Large (>20K Cr) / Mid (5-20K Cr) / Small (<5K Cr) |
| Price Alerts | Navigation | — | Existing (unchanged) |
| Signal Change Alerts | Toggle | `signalChangeAlerts` | false |
| Morning Brief Time | Picker | `morningBriefTime` | Existing (unchanged) |
| Notification Sound | Picker | `notificationSound` | Existing (unchanged) |
| **Quiet Hours** | Navigation | — | Opens `QuietHoursView` (start/end picker) |

#### Tab 2: ANALYSIS
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| Deep Scan by Default | Toggle | `deepScanByDefault` | Existing (unchanged) |
| **Auto-regenerate Stale** | Toggle | `autoRegenerateStale` | false |
| **Min Confidence Alert** | Picker | `minConfidenceAlert` | 50% / 65% / 75% / 90% |
| **Analysis Language** | Picker | `analysisLanguage` | English / Hindi / Hinglish |
| **Debate Rounds** | Picker | `debateRounds` | 1 / 2 / 3 |
| **Show Governance First** | Toggle | `showGovernanceFirst` | false |
| Alert on BUY | Toggle | `alertOnBuy` | true |
| Alert on SELL | Toggle | `alertOnSell` | true |
| Mute HOLD | Toggle | `muteHoldSignals` | false |

#### Tab 3: APPEARANCE
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| Denomination Theme | Grid | `selectedTheme` | Existing, unchanged |
| Dark Inks | Toggle | `darkInksEnabled` | Existing (unchanged) |
| **Font Size** | Picker | `fontSize` | Small / Standard / Large |
| **Layout Density** | Picker | `layoutDensity` | Compact / Standard / Spacious |
| **Default Chart Range** | Picker | `defaultChartRange` | 1M / 3M / 6M / 1Y |
| **Reduce Animations** | Toggle | `reduceAnimations` | false |
| **Show Hindi Labels** | Toggle | `showHindiLabels` | true |

#### Tab 4: DATA
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| **Saved Reports** | Navigation | — | Opens report manager |
| **Clear Image Cache** | Button | — | Confirm dialog → purge |
| **Clear Analysis Cache** | Button | — | Confirm dialog → purge |
| **Export Portfolio CSV** | Button | — | Share sheet |
| Face ID Lock | Toggle | `faceIdLock` | Existing (unchanged) |
| **Hide Portfolio Values** | Toggle | `hidePortfolioValues` | false |
| **Scramble P&L on Tilt** | Toggle | `scramblePnL` | false |
| **Biometric for Trades** | Toggle | `biometricTradeLock` | false |
| Currency Format | Picker | `currencyFormat` | Existing (unchanged) |
| Home Auto-Refresh | Picker | `homeAutoRefreshSeconds` | Existing (unchanged) |
| Server URL | Navigation | — | Existing (unchanged) |
| Void All Records | Button | — | Existing, unchanged |
| Void Session | Button | — | Existing, unchanged |
| IPO Alerts | Toggle | `ipoAlertsEnabled` | Existing (unchanged) |
| Dev Tools | Hidden | — | Existing (unchanged) |

### New Sub-Screens
- `SectorBlacklistView.swift` — toggle chips for sectors (Banking, IT, Pharma, Auto, FMCG, Metals, Energy, Realty, Media, PSU)
- `QuietHoursView.swift` — start/end time pickers, days-of-week toggles
- `ReportManagerView.swift` — list saved reports with delete swipe, counts per ticker

### Design Pattern (Consistency)
- All rows use existing `SettingsNoteGroup`, `ToggleNoteRow`, `PickerNoteRow` patterns
- Tabs use `extremeModeSwitcher`-style pill buttons
- All new @AppStorage keys prefixed with `nivesh_` (existing convention)
- Sub-screens use `NavigationLink` from parent, `NavigationStack` + `DenominationBackground` inside

---

## Implementation Plan (3 Sub-Teams)

### Team 1: Extreme Dossier (1 subagent)
- New components: `DossierSectionHeader`, `ClassifiedStamp`, `DossierFooter`
- Modify: `heroChartSection`, `aiVerdictCard`, all section headers in `aiReportScroll`
- File: `AnalysisScreen.swift` only

### Team 2: Morning Brief (1 subagent)
- New file: `MorningBriefAlertView.swift`
- Modify: `HomeScreen.swift` (add FAB, sheet trigger, state)
- Zero API changes

### Team 3: Settings Expansion (2 subagents)
- Subagent 3A: Settings screen restructure (tabs, all new rows in main SettingsScreen.swift)
- Subagent 3B: Sub-screens (SectorBlacklistView, QuietHoursView, ReportManagerView)
- File: `SettingsScreen.swift` + 3 new files

**Order:** All 3 streams are independent. Can run in parallel. Stream C's subagents 3A and 3B must be sequential (3B depends on 3A's tab structure).

---
