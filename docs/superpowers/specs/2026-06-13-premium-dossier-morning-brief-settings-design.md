# Premium Dossier, Morning Brief Popup & Settings Expansion — Design Document

> Date: 13 June 2026 | Status: Design Approved | 3 independent streams

## Stream A: Extreme Analysis — Premium Dossier Redesign

**Goal:** Redesign the Extreme Analysis "AI REPORT" tab to look like a declassified intelligence dossier. No data changes — visual only.

**File:** `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift`

### Visual Language
- **Redaction bar section headers**: Each section title renders as a black bar with struck-through text on scroll-enter, then animates (spring, 0.4s) to reveal the actual title. Implemented via `RedactionSectionHeader(title:)` ViewModifier that watches scroll position.
- **Classified circular stamps**: `riskFactorsSection`, governance components, and `fundamentalsSection` get a red `CLASSIFIED` or `CONFIDENTIAL` circular stamp overlay in the top-right corner. `heroChartSection` gets "SATELLITE IMAGERY" stamp. No watermark behind `aiVerdictCard` text — readability over ornamentation.
- **Document footer**: Below `disclaimerSection`, a dossier-style footer: "DOCUMENT END · Nivesh AI Research Desk · Classification: UNCLASSIFIED".
- **Aged-paper background**: Slightly warmer tint on `DenominationBackground`. Subtle typewriter-texture `.opacity(0.02)` overlay. Must preserve high text contrast — no tinting on text areas.

### Implementation
- New components (in-file private structs):
  - `DossierSectionHeader(title:)` — redaction bar with animation
  - `ClassifiedStamp(text:)` — circular red stamp overlay
  - `DossierFooter()` — end-of-document footer
- Modified sections:
  - `heroChartSection` → add stamp
  - All 10+ section headers → replace with `DossierSectionHeader`
  - `riskFactorsSection`, `fundamentalsSection` → add stamp
- `extremeModeSwitcher` → unchanged
- Standard analysis tier → unchanged (dossier only for extreme)

---

## Stream B: Morning Brief — Prominent Card + Nav Bar Icon

**Goal:** Render the Morning Brief as a prominent, dismissible card pinned at the top of the HomeScreen feed. A static icon in the top navigation bar provides quick access. Zero new API calls.

**Files:** `HomeScreen.swift` only (no new files)

### Behavior
- `@AppStorage("morningBriefShownDate")` — stores `"2026-06-13"` last-dismissed date
- On `HomeScreen.onAppear`: if `morningBriefShownDate != today` AND `morningBriefData != nil` → show the prominent card at the top of the feed
- Card is NOT a modal/overlay — it's a section in the ScrollView, pinned as the first card
- Does NOT fetch new data — uses existing `viewModel.morningBriefData`
- If data hasn't loaded yet when onAppear fires, card appears when data arrives (`onChange`)

### Prominent Dismissible Card (Rendered in `renderSection(id: .top)`)
Replaces the current `SectionHeader(title: "Morning Brief")` + `MorningDecreeCard` in the `.morning` section. Instead, an eye-catching card rendered at position zero in the feed:

```
┌──────────────────────────────────┐
│  🟢 MARKETS OPEN · June 13 09:15│  ← mood dot + dateline
│                                  │
│  Market mood: CAUTIOUSLY POSITIVE│
│  FIIs returned with ₹2,400 Cr   │
│  buying. Global cues mixed...   │  ← summary (3 lines max)
│  Key Q4 results today: TCS...   │
│                                  │
│  ────────────────────────────── │
│  ⚠ TCS Q4 expected +8% YoY      │  ← priority items (2 lines max)
│  ⚠ SEBI deadline on Finflix     │
│                                  │
│  [READ FULL BRIEF]    [✕ DISMISS]│  ← action buttons
└──────────────────────────────────┘
```

**Card details:**
- Mood-colored left-edge accent strip (green/red/amber, 4pt wide)
- "MARKETS OPEN" dateline with mood dot in `officialStampFont`
- Summary: `engravedSerif`, 3-line limit with "...READ FULL BRIEF" link
- Priority items: up to 2 shown inline
- Two buttons at bottom:
  - "READ FULL BRIEF" — expands card inline to show full brief content (or navigates to existing `MorningDecreeCard` full view)
  - "✕ DISMISS" — hides the card for the day, sets `morningBriefShownDate = today`
- Dismiss animation: card collapses with `.transition(.move(edge: .top).combined(with: .opacity))`
- After dismiss: card is gone until next day

### Static Nav Bar Icon
- Rendered in HomeScreen's `.toolbar` at `.navigationBarLeading` position
- Visual: `newspaper` SF Symbol in `Theme.securityGold`, 28×28pt tap target
- Shows only when `viewModel.morningBriefData != nil`
- Tap: if card is dismissed/re-hidden today, shows it again. If card is already visible, scrolls to it via `ScrollViewReader`
- Mood-colored dot (6pt) at top-right corner of the icon when brief is unread/new

### State
```
@State private var briefDismissed = false
@AppStorage("morningBriefShownDate") private var briefShownDate = ""
```
- `briefDismissed` resets to `false` when date changes (today != briefShownDate)
- Card visibility: `!briefDismissed && briefData != nil`

---

## Stream C: Settings — Native iOS Grouped List

**Goal:** Expand SettingsScreen with 30+ new settings organized into standard iOS grouped `List` sections. All `@AppStorage` — no backend.

**File:** `ios/StockApp/stockme/stockme/Views/SettingsScreen.swift`

### Layout
- Standard iOS `List` with `.insetGrouped` style
- Divided into labeled `Section` groups — no custom tab bar
- Each section has a `Section { ... } header: { ... }` with header text in `Theme.officialStampFont`
- Scrollable vertically, native iOS look with Banknote Aesthetic skin (colors, fonts, card style)

### Section Content — New Settings (Bold = NEW)

#### Section: TRADING PREFERENCES
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

#### Section: AI & ANALYSIS
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

#### Section: APPEARANCE
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| Denomination Theme | Grid | `selectedTheme` | Existing, unchanged |
| Dark Inks | Toggle | `darkInksEnabled` | Existing (unchanged) |
| **Font Size** | Picker | `fontSize` | Small / Standard / Large |
| **Layout Density** | Picker | `layoutDensity` | Compact / Standard / Spacious |
| **Default Chart Range** | Picker | `defaultChartRange` | 1M / 3M / 6M / 1Y |
| **Reduce Animations** | Toggle | `reduceAnimations` | false |
| **Show Hindi Labels** | Toggle | `showHindiLabels` | true |

#### Section: DATA & PRIVACY
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| **Saved Reports** | Navigation | — | Opens report manager |
| **Clear Image Cache** | Button | — | Confirm dialog → purge |
| **Clear Analysis Cache** | Button | — | Confirm dialog → purge |
| **Export Portfolio CSV** | Button | — | Share sheet |
| Face ID Lock | Toggle | `faceIdLock` | Existing (unchanged) |
| **Hide Portfolio Values** | Toggle | `hidePortfolioValues` | false |
| **Biometric for Trades** | Toggle | `biometricTradeLock` | false |
| Currency Format | Picker | `currencyFormat` | Existing (unchanged) |
| Home Auto-Refresh | Picker | `homeAutoRefreshSeconds` | Existing (unchanged) |
| Server URL | Navigation | — | Existing (unchanged) |

#### Section: ACCOUNT
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| Void All Records | Button | — | Existing, unchanged |
| Void Session | Button | — | Existing, unchanged |
| IPO Alerts | Toggle | `ipoAlertsEnabled` | Existing (unchanged) |

#### Section: DEVELOPER (hidden, triple-tap to reveal)
| Setting | Type | Key | Options |
|---------|------|-----|---------|
| Dev Tools | — | — | Existing, unchanged |

### New Sub-Screens
- `SectorBlacklistView.swift` — toggle chips for sectors (Banking, IT, Pharma, Auto, FMCG, Metals, Energy, Realty, Media, PSU)
- `QuietHoursView.swift` — start/end time pickers, days-of-week toggles
- `ReportManagerView.swift` — list saved reports with delete swipe, counts per ticker

### Design Pattern (Consistency)
- ALL rows use existing `SettingsNoteGroup`, `ToggleNoteRow`, `PickerNoteRow` patterns
- All new @AppStorage keys prefixed with `nivesh_` (existing convention)
- Sub-screens use `NavigationLink` from parent, `NavigationStack` + `DenominationBackground` inside
- No custom pill switcher — standard iOS `List` navigation

---

## Implementation Plan (3 Sub-Teams)

### Team 1: Extreme Dossier (1 subagent)
- New components: `DossierSectionHeader`, `ClassifiedStamp`, `DossierFooter`
- Modify: `heroChartSection`, all section headers in `aiReportScroll`
- File: `AnalysisScreen.swift` only
- Note: No watermark on `aiVerdictCard`

### Team 2: Morning Brief (1 subagent)
- Modify: `HomeScreen.swift` (prominent card section + toolbar icon + state)
- No new files needed
- Zero API changes

### Team 3: Settings Expansion (2 subagents)
- Subagent 3A: Restructure `SettingsScreen.swift` — convert to `List` with `Section` groups, add all new rows
- Subagent 3B: New sub-screens (`SectorBlacklistView`, `QuietHoursView`, `ReportManagerView`)
- File: `SettingsScreen.swift` + 3 new files
- Note: No "Scramble P&L on Tilt" setting

**Order:** All 3 streams are independent. Can run in parallel. Stream C's subagents 3A and 3B must be sequential (3B depends on 3A's NavigationLink destinations).

---
