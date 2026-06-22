# Prompt: HomeScreen Redesign — Fix Violations + Surface More Information

## Context

You are working on `ios/StockApp/stockme/stockme/Views/HomeScreen.swift` (2758 lines). This file drives the main Nivesh dashboard. The redesign has TWO goals:

1. **Fix every AGENTS.md violation** found in the current code
2. **Surface more information** from data that is already fetched but not displayed

**Do NOT break any existing functionality.** All `HomeViewModel` properties, network calls, `feedVM` bindings, `authManager`, `navigationPath`, `timeframeConflicts`, `dailyAction`, `activeSectionOrder`, `HomeSectionID` enum, `HomeLayoutEditorSheet`, and the drag-to-reorder layout system must remain fully intact.

**Before editing any symbol**, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` per AGENTS.md §1. Run `gitnexus_detect_changes()` before committing.

---

## Part 1 — Fix AGENTS.md Violations (MANDATORY)

### 1.1 — Fix raw system color in News and YouTube section headers

**File:** `HomeScreen.swift`, `renderSection(id:)` extension  
**Location:** `case .news` (~line 2460) and `case .youtube` (~line 2553)

Both section headers use `.foregroundStyle(.secondary)` — a forbidden system color. Replace both with the bilingual `SectionHeader` pattern used in every other section.

**Current (WRONG — both sections):**
```swift
VStack(alignment: .leading, spacing: 2) {
    Text("ताज़ा समाचार")
        .font(.caption2)
        .foregroundStyle(.secondary)
    Text("MARKET NEWS")
        .font(.caption.weight(.semibold)).monospaced()
        .tracking(2.0)
        .foregroundStyle(.secondary)
}
.padding(.bottom, Theme.Spacing.standard)
.padding(.horizontal, Theme.screenPadding)

GuillocheDivider()
    .padding(.horizontal, Theme.screenPadding)
    .padding(.bottom, Theme.Spacing.standard)
```

**Replace with (CORRECT — for `.news`):**
```swift
VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
    SectionHeader(title: "Market News", hindiTitle: "ताज़ा समाचार")
}
.padding(.horizontal, Theme.screenPadding)
```

**Replace with (CORRECT — for `.youtube`):**
```swift
VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
    SectionHeader(title: "Expert Videos", hindiTitle: "विशेषज्ञ विश्लेषण")
}
.padding(.horizontal, Theme.screenPadding)
```

Remove the manually placed `GuillocheDivider()` after each header — `SectionHeader` already applies the correct styling and `GuillocheDivider()` belongs only between major page sections, not inside the section header itself.

---

### 1.2 — Fix Rectangle() thin-rule dividers inside cards (use nothing instead)

**File:** `HomeScreen.swift`  
**Violation:** AGENTS.md §2.5 — `Rectangle().fill(...).frame(height: 0.5)` used as a horizontal rule inside card bodies. This is not `GuillocheDivider()` nor a proper separator.

**Locations:**
- `MarketPulseDashCard` body (~line 1291): `Rectangle().fill(Color.primary.opacity(0.08)).frame(height: 0.5).padding(...)` between the ADBreathBar and the IndexRows
- `MacroDashCard` body (~line 1462): `Rectangle().fill(Color.primary.opacity(0.08)).frame(height: 0.5)` between macro groups

**Fix:** Inside cards, replace these thin Rectangle rules with a `Divider()` at 8% opacity — `Divider().opacity(0.08)` — which respects the system's adaptive color. Do NOT use `GuillocheDivider()` inside individual cards (it's for between page sections). The existing `Divider().opacity(0.08)` already used in `InstitutionalDashCard` and between IndexRows is the correct pattern.

```swift
// WRONG (remove):
Rectangle()
    .fill(Color.primary.opacity(0.08))
    .frame(height: 0.5)
    .padding(.horizontal, cardHPad)
    .padding(.vertical, Theme.Spacing.standard)

// CORRECT (replace with):
Divider()
    .opacity(0.08)
    .padding(.horizontal, cardHPad)
    .padding(.vertical, Theme.Spacing.standard)
```

---

### 1.3 — Fix hardcoded cornerRadius in InstitutionalDashCard

**File:** `HomeScreen.swift`, `InstitutionalDashCard` (~line 2255)  
**Violation:** AGENTS.md §2.1 — hardcoded `cornerRadius: 16` instead of `Theme.CornerRadius.card`

```swift
// WRONG:
.clipShape(RoundedRectangle(cornerRadius: 16))
.overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.borderFine, lineWidth: 0.5))

// CORRECT:
.clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
.overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderFine, lineWidth: 0.5))
```

---

### 1.4 — Fix magic spacing numbers

**Violation:** AGENTS.md §2.6 — The 8pt Grid. All spacing must use `Theme.Spacing.*` tokens.

Fix each of the following in-place:

| Location | Current | Replace with |
|----------|---------|--------------|
| `DashboardSection` VStack spacing (~line 2215) | `spacing: 10` | `spacing: Theme.Spacing.standard` |
| `TimeframeConflictsBanner` HStack spacing (~line 1153) | `spacing: 10` | `spacing: Theme.Spacing.standard` |
| `MomentumDashCard` between-section Spacer (~line 1378) | `Spacer().frame(height: 10)` | `Spacer().frame(height: Theme.Spacing.standard)` |
| `MarketMoodGauge` VStack spacing (~line 1515) | `spacing: 10` | `spacing: Theme.Spacing.standard` |
| `MarketPulseDashCard` inner VStack header spacing (~line 1266) | `spacing: 2` | `spacing: Theme.Spacing.xSmall` |
| `MomentumDashCard` header VStack spacing (~line 1350) | `spacing: 2` | `spacing: Theme.Spacing.xSmall` |

---

### 1.5 — Fix raw color in CompactNewsCell signal badge

**File:** `HomeScreen.swift`, `CompactNewsCell.signalBadge` (~line 1746)  
**Violation:** AGENTS.md §2.1 — `Color(hue: 0.05, saturation: 0.9, brightness: 0.95)` is a raw color. There is no perfect Theme token for hot-orange, but `Theme.holdAmber` is the closest authorized warm accent. Use it.

```swift
// WRONG:
if age < 2 * 3600 { return ("HOT", "flame.fill", Color(hue: 0.05, saturation: 0.9, brightness: 0.95)) }

// CORRECT:
if age < 2 * 3600 { return ("HOT", "flame.fill", Theme.holdAmber) }
```

---

### 1.6 — Fix GeometryReader inside ScrollView in IndexCardView and MomentumRowView

**Violation:** AGENTS.md §2.6 GeometryReader prohibition — `GeometryReader` inside `ScrollView` or `HStack` causes sibling views to overlap or clip.

**`IndexCardView`** (~line 1605): The entire `VStack` body is wrapped in `GeometryReader { idxGeo in ... .frame(width: idxGeo.size.width * 0.35) }`. This card is rendered inside a horizontal `ScrollView` → `HStack`, which is forbidden. Replace proportional sizing with `UIScreen.main.bounds.width`:

```swift
// WRONG:
var body: some View {
    GeometryReader { idxGeo in
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) { ... }
        .frame(width: idxGeo.size.width * 0.35)
        .banknoteCard()
    }
}

// CORRECT:
var body: some View {
    VStack(alignment: .leading, spacing: Theme.Spacing.medium) { ... }
    .frame(width: UIScreen.main.bounds.width * 0.32)
    .banknoteCard()
}
```

**`MomentumRowView`** (~line 1652): Uses `GeometryReader { momGeo in ... .frame(width: momGeo.size.width * 0.14, height: momGeo.size.width * 0.08) }` for the sparkline inside what renders as a list item within `MomentumSectionView`. Remove the GeometryReader wrapper and give the sparkline a fixed frame:

```swift
// WRONG:
var body: some View {
    GeometryReader { momGeo in
        HStack(spacing: Theme.Spacing.standard) {
            ...
            SparklineView(values: ticker.sparkline, color: signalColor)
                .frame(width: momGeo.size.width * 0.14, height: momGeo.size.width * 0.08)
        }
        .padding(...)
    }
}

// CORRECT:
var body: some View {
    HStack(spacing: Theme.Spacing.standard) {
        ...
        if !ticker.sparkline.isEmpty {
            SparklineView(values: ticker.sparkline, color: signalColor)
                .frame(width: 48, height: 28)
        }
    }
    .padding(.horizontal, Theme.Spacing.standard)
    .padding(.vertical, Theme.Spacing.standard)
}
```

---

## Part 2 — Surface More Information (WITHOUT new network calls)

All data for these additions is ALREADY fetched by `HomeViewModel` or `feedVM`. No new endpoints, no new network calls, no new `@StateObject` variables.

---

### 2.1 — Render `MarketMoodGauge` in the `.marketPulse` section

`MarketMoodGauge` is **fully implemented** (defined at line 1492) but **never rendered anywhere in the app**. Add it to the `.marketPulse` section, below the `MarketPulseDashCard`, using data already in `pulse.advances` and `pulse.declines`.

**In `renderSection(id:)`, `case .marketPulse`:**

```swift
case .marketPulse:
    DashboardSection(id: HomeSectionID.marketPulse.rawValue, title: "Market Pulse", hindi: "बाजार की नब्ज", icon: "waveform.path.ecg") {
        if let pulse = viewModel.dashboard?.pulse {
            MarketPulseDashCard(pulse: pulse)
            
            // ── NEW: Market Mood Gauge ──────────────────────────────
            if pulse.advances + pulse.declines > 0 {
                let ratio = Double(pulse.advances) / Double(pulse.advances + pulse.declines)
                MarketMoodGauge(ratio: ratio)
            }
        } else {
            DashboardLoadingCard(label: "Market Pulse", isLoading: viewModel.dashboardLoading)
        }
    }
```

---

### 2.2 — Upgrade the `.top` section header with a market status row

The current `.top` section shows only the "RESERVE BANK OF INTELLIGENCE" branding + Quick Nav + Daily Action card. Add a compact **market status strip** between the branding row and the Quick Nav chips. This is computed from the current time — no network call required.

**Add this new private struct before the `renderSection` extension:**

```swift
private struct MarketStatusStrip: View {
    private var isMarketOpen: Bool {
        let cal = Calendar(identifier: .gregorian)
        var comps = cal.dateComponents(in: TimeZone(identifier: "Asia/Kolkata")!, from: Date())
        guard let weekday = comps.weekday, weekday != 1, weekday != 7 else { return false } // Sun=1, Sat=7
        let hour = comps.hour ?? 0
        let minute = comps.minute ?? 0
        let totalMinutes = hour * 60 + minute
        return totalMinutes >= 555 && totalMinutes < 930 // 9:15 AM to 3:30 PM IST
    }

    private var statusLabel: String { isMarketOpen ? "NSE OPEN" : "NSE CLOSED" }
    private var statusColor: Color { isMarketOpen ? Theme.bullGreen : Theme.bearRed }

    private var istTimeString: String {
        let f = DateFormatter()
        f.timeZone = TimeZone(identifier: "Asia/Kolkata")
        f.dateFormat = "EEE, d MMM · HH:mm IST"
        return f.string(from: Date()).uppercased()
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.small) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 6, height: 6)
                    .shadow(color: statusColor.opacity(0.5), radius: 3)
                Text(statusLabel)
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.2)
                    .foregroundStyle(statusColor)
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.medium)
            .background(statusColor.opacity(0.08))
            .cornerRadius(Theme.CornerRadius.small)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(statusColor.opacity(0.25), lineWidth: 0.5))

            Text(istTimeString)
                .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                .foregroundStyle(Theme.inkTertiary)

            Spacer()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.bottom, Theme.Spacing.small)
    }
}
```

**In `renderSection(id:)`, `case .top`, insert `MarketStatusStrip()` between the branding HStack and the Quick Nav ScrollView:**

```swift
case .top:
    Group {
        if let user = authManager.currentUser {
            HStack { /* existing branding + avatar — UNCHANGED */ }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
        }

        // ── NEW: Market Status Strip ─────────────────────────────
        MarketStatusStrip()

        // existing Quick Nav ScrollView — UNCHANGED
        ScrollView(.horizontal) { ... }

        // existing DailyActionCard — UNCHANGED
        if let action = dailyAction { ... }
    }
    .id(HomeSectionID.top.rawValue)
```

---

### 2.3 — Enrich the `.earnings` section with result quality badges

The earnings rows currently show only ticker + daysAway + earningsDate. The `EarningsEvent` model (from `HomeViewModel.earningsEvents`) may carry an `isMyHolding` flag or similar — check the model definition. If the ticker is in `viewModel.watchlist`, add a small "WATCHLIST" badge next to the ticker so users can instantly see which upcoming results affect them.

**In `case .earnings`, the ForEach loop:**

```swift
ForEach(upcoming) { event in
    NavigationLink(value: event.ticker) {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                HStack(spacing: Theme.Spacing.small) {
                    Text(event.ticker)
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundStyle(Theme.inkPrimary)
                    
                    // ── NEW: Watchlist badge ─────────────────
                    if viewModel.watchlist.contains(where: { $0.ticker == event.ticker }) {
                        Text("WATCHLIST")
                            .font(Theme.officialStampFont(size: 7))
                            .tracking(0.8)
                            .foregroundStyle(Theme.securityGold)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.securityGold.opacity(0.12))
                            .cornerRadius(Theme.CornerRadius.small)
                            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                    }
                }
            }
            Spacer()
            Text(event.daysAway == 0 ? "Today" : "In \(event.daysAway) days")
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(event.daysAway <= 3 ? Theme.holdAmber : Theme.inkSecondary)
            Text("· \(event.earningsDate)")
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
            Image(systemName: "chevron.right")
                .font(.caption2)
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(.horizontal, Theme.screenPadding)
    }
    .buttonStyle(.plain)
    .ekPressHaptic()
}
```

---

### 2.4 — Add advance/decline count labels to `ADBreathBar` in `MarketPulseDashCard`

The `ADBreathBar` shows a colored ratio bar but the raw A/D counts (`pulse.advances`, `pulse.declines`) are available but not shown as text. Show them in the card.

**In `MarketPulseDashCard`, after the `ADBreathBar(...)` call:**

```swift
if pulse.advances + pulse.declines > 0 {
    ADBreathBar(advancing: pulse.advances, declining: pulse.declines)
        .padding(.horizontal, cardHPad)
    
    // ── NEW: A/D count labels ────────────────────────────────
    HStack {
        HStack(spacing: Theme.Spacing.xSmall) {
            Image(systemName: "arrow.up")
                .font(.caption2.weight(.bold))
                .foregroundStyle(Theme.bullGreen)
            Text("\(pulse.advances) Advancing")
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundStyle(Theme.bullGreen)
        }
        Spacer()
        HStack(spacing: Theme.Spacing.xSmall) {
            Text("\(pulse.declines) Declining")
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundStyle(Theme.bearRed)
            Image(systemName: "arrow.down")
                .font(.caption2.weight(.bold))
                .foregroundStyle(Theme.bearRed)
        }
    }
    .padding(.horizontal, cardHPad)
    .padding(.top, Theme.Spacing.xSmall)
    .padding(.bottom, Theme.Spacing.small)
}
```

---

## Part 3 — Visual Polish Pass

### 3.1 — Improve Watchlist empty state

The current empty state is plain text centered with padding. Replace with a proper empty state card matching AGENTS.md §2.8 Category A:

```swift
// In case .watchlist, replace the empty-state Text with:
VStack(spacing: Theme.Spacing.card) {
    Image(systemName: "binoculars")
        .font(.largeTitle.weight(.light))
        .foregroundStyle(Theme.inkTertiary.opacity(0.4))
    Text("NO STOCKS ON WATCHLIST")
        .font(Theme.officialStampFont(size: 11))
        .tracking(1.5)
        .foregroundStyle(Theme.inkTertiary)
    Text("Add stocks from Search to track them here.")
        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
        .foregroundStyle(Theme.inkSecondary)
        .multilineTextAlignment(.center)
}
.frame(maxWidth: .infinity)
.padding(.vertical, Theme.Spacing.xLarge)
.padding(.horizontal, Theme.screenPadding)
```

---

### 3.2 — Remove the `DashboardSection` wrapper from sections that already have their own bilingual headers

`DashboardSection` adds a redundant section header row with an SF Symbol + `SectionHeader`. But `.marketPulse`, `.momentum`, `.macroAlt`, and `.institutional` all use `DashboardSection` while the *inner cards* already have their own SecurityThread + GuillocheDivider + bilingual header built in. This creates duplicate headers.

Remove the `DashboardSection` wrapper from these four cases and replace with just the card content, adding the outer section ID manually:

```swift
case .marketPulse:
    VStack(spacing: Theme.Spacing.standard) {
        if let pulse = viewModel.dashboard?.pulse {
            MarketPulseDashCard(pulse: pulse)
            if pulse.advances + pulse.declines > 0 {
                let ratio = Double(pulse.advances) / Double(pulse.advances + pulse.declines)
                MarketMoodGauge(ratio: ratio)
            }
        } else {
            DashboardLoadingCard(label: "Market Pulse", isLoading: viewModel.dashboardLoading)
        }
    }
    .padding(.horizontal, Theme.screenPadding)
    .id(HomeSectionID.marketPulse.rawValue)

// Apply the same pattern (remove DashboardSection wrapper) to:
// case .momentum, case .macroAlt, case .institutional
```

For `.momentum`:
```swift
case .momentum:
    VStack {
        if let momentum = viewModel.dashboard?.momentum {
            MomentumDashCard(momentum: momentum)
        } else {
            DashboardLoadingCard(label: "Momentum Scan", isLoading: viewModel.dashboardLoading)
        }
    }
    .padding(.horizontal, Theme.screenPadding)
    .id(HomeSectionID.momentum.rawValue)
```

For `.macroAlt`:
```swift
case .macroAlt:
    VStack {
        if let macro = viewModel.dashboard?.macro {
            MacroDashCard(macro: macro)
        } else {
            DashboardLoadingCard(label: "Macro Data", isLoading: viewModel.dashboardLoading)
        }
    }
    .padding(.horizontal, Theme.screenPadding)
    .id(HomeSectionID.macroAlt.rawValue)
```

For `.institutional`:
```swift
case .institutional:
    VStack {
        if let inst = viewModel.dashboard?.institutional {
            InstitutionalDashCard(flow: inst)
        } else {
            DashboardLoadingCard(label: "Institutional Flow", isLoading: viewModel.dashboardLoading)
        }
    }
    .padding(.horizontal, Theme.screenPadding)
    .id(HomeSectionID.institutional.rawValue)
```

---

## Part 4 — Verification Checklist

After all changes, verify:

- [ ] `gitnexus_detect_changes()` shows only `HomeScreen.swift` in the diff
- [ ] Xcode build: zero errors, zero warnings
- [ ] No `Rectangle().fill(...)` rules remain inside card bodies
- [ ] No `.foregroundStyle(.secondary)` in news or YouTube headers
- [ ] No `GeometryReader` inside any `ScrollView` or horizontal `HStack`
- [ ] No raw hex / `Color(hue:saturation:brightness:)` values remain
- [ ] No magic spacing numbers (`10`, `2`, `14`, `16`) — all replaced with `Theme.Spacing.*` or `Theme.CornerRadius.*`
- [ ] `MarketMoodGauge` renders in `.marketPulse` section
- [ ] `MarketStatusStrip` renders in `.top` section
- [ ] Watchlist empty state is a card, not plain text
- [ ] All existing ViewModel bindings, `.task {}` blocks, `.refreshable {}`, `navigationPath`, `HomeSectionID` reordering still work
- [ ] The `HomeLayoutEditorSheet` drag-to-reorder still persists correctly

---

## What NOT to Touch

- `HomeViewModel` — all `@Published` properties, all fetch methods, all timers
- `feedVM: HomeFeedViewModel` — all bindings
- `HomeSectionID` enum, `activeSectionOrder`, `scrollTarget`
- `HomeLayoutEditorSheet` struct
- The `.task {}` and `.refreshable {}` blocks in `HomeScreen.body`
- `PortfolioNoteCard`, `MorningDecreeCard`, `DailyActionCard`, `SectorHeatmapView`
- `CompactNewsCell` body logic (only change the `Color(hue:...)` to `Theme.holdAmber`)
- `NewsDetailSheet` (do not touch)
- `StockRow`, `IndexChip`, `SectionHeader` — defined elsewhere, referenced here
- Any networking code, authentication, or data model structs
