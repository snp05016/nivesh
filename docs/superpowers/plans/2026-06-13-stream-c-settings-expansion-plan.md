# Stream C: Settings Expansion — iOS Grouped List — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand SettingsScreen with 30+ new settings organized into standard iOS grouped `List` sections. Three new sub-screens for Sector Blacklist, Quiet Hours, and Report Manager. All `@AppStorage` — zero backend changes.

**Architecture:** Convert the existing ScrollView/VStack layout to a native `List` with `Section` groups. Keep existing `SettingsNoteGroup`, `ToggleNoteRow`, `PickerNoteRow`, `DatePickerNoteRow` components. Add new sub-screens as NavigationLink destinations. No custom tab bar — native iOS List navigation.

**Tech Stack:** SwiftUI `List` (`.insetGrouped`), `@AppStorage`, existing `SettingsNoteGroup`/`ToggleNoteRow`/`PickerNoteRow`/`DatePickerNoteRow`, `Theme.*`, `DenominationBackground`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `Views/SettingsScreen.swift` | Modify | Restructure to List, add all new settings rows + @AppStorage keys |
| `Views/SectorBlacklistView.swift` | Create | Toggle chips for 10 sectors |
| `Views/QuietHoursView.swift` | Create | Start/end time pickers with day-of-week toggles |
| `Views/ReportManagerView.swift` | Create | Saved reports list with delete |

---

### Task C1: Add All New @AppStorage Keys

**File:** `ios/StockApp/stockme/stockme/Views/SettingsScreen.swift`

Add new `@AppStorage` declarations after existing ones (after line 19).

- [ ] **Step 1: Add Trading Preferences keys**

```swift
    @AppStorage("nivesh_defaultScanType") private var defaultScanType = "ask"
    @AppStorage("nivesh_autoRunOnTap") private var autoRunOnTap = false
    @AppStorage("nivesh_riskTolerance") private var riskTolerance = "Moderate"
    @AppStorage("nivesh_defaultExchange") private var defaultExchange = "Auto"
    @AppStorage("nivesh_minMarketCap") private var minMarketCap = "Any"
    @AppStorage("nivesh_signalChangeAlerts") private var signalChangeAlerts = false
```

- [ ] **Step 2: Add AI & Analysis keys**

```swift
    @AppStorage("nivesh_autoRegenerateStale") private var autoRegenerateStale = false
    @AppStorage("nivesh_minConfidenceAlert") private var minConfidenceAlert = "50%"
    @AppStorage("nivesh_analysisLanguage") private var analysisLanguage = "English"
    @AppStorage("nivesh_debateRounds") private var debateRounds = "1"
    @AppStorage("nivesh_showGovernanceFirst") private var showGovernanceFirst = false
    @AppStorage("nivesh_alertOnBuy") private var alertOnBuy = true
    @AppStorage("nivesh_alertOnSell") private var alertOnSell = true
    @AppStorage("nivesh_muteHoldSignals") private var muteHoldSignals = false
```

- [ ] **Step 3: Add Appearance keys**

```swift
    @AppStorage("nivesh_fontSize") private var fontSize = "Standard"
    @AppStorage("nivesh_layoutDensity") private var layoutDensity = "Standard"
    @AppStorage("nivesh_defaultChartRange") private var defaultChartRange = "1M"
    @AppStorage("nivesh_reduceAnimations") private var reduceAnimations = false
    @AppStorage("nivesh_showHindiLabels") private var showHindiLabels = true
```

- [ ] **Step 4: Add Data & Privacy keys**

```swift
    @AppStorage("nivesh_hidePortfolioValues") private var hidePortfolioValues = false
    @AppStorage("nivesh_biometricTradeLock") private var biometricTradeLock = false
```

- [ ] **Step 5: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/SettingsScreen.swift
git commit -m "Add all new @AppStorage keys for expanded settings"
```

---

### Task C2: Restructure SettingsScreen to List Layout

**File:** `ios/StockApp/stockme/stockme/Views/SettingsScreen.swift`

Replace the `body` ScrollView/VStack structure with a `List`-based layout. Keep all existing settings, add new ones per the section tables below.

- [ ] **Step 1: Replace the body**

Find the current `body` (starts at line 56). Replace the `ScrollView { VStack { ... } }` block with:

```swift
    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .fifty)

                List {
                    // ── Section 1: TRADING PREFERENCES ──
                    Section {
                        if let user = authManager.currentUser {
                            HStack(spacing: Theme.Spacing.card) {
                                ZStack {
                                    Circle().fill(Theme.securityGold).frame(width: 44, height: 44)
                                    Text(String(user.displayName.prefix(1)).uppercased())
                                        .font(Theme.serialNumberFont(size: 18, relativeTo: .body).weight(.semibold))
                                        .foregroundStyle(Theme.canvas)
                                }
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(user.displayName)
                                        .font(Theme.engravedSerif(size: 15, weight: .semibold))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text("Registry #\(String(user.userId))-AUTH")
                                        .font(Theme.serialNumberFont(size: 9))
                                        .foregroundStyle(Theme.inkTertiary)
                                }
                            }
                        }

                        PickerNoteRow(icon: "sparkles", color: Theme.securityGold, title: "Default Scan Type", selection: $defaultScanType, options: ["Ask Every Time", "Standard", "Deep", "Extreme"])
                        ToggleNoteRow(icon: "bolt.fill", color: Theme.bullGreen, title: "Auto-run on Stock Tap", isOn: $autoRunOnTap)
                        PickerNoteRow(icon: "shield.checkered", color: Theme.securityGold, title: "Risk Tolerance", selection: $riskTolerance, options: ["Conservative", "Moderate", "Aggressive"])
                        PickerNoteRow(icon: "building.2", color: Theme.inkSecondary, title: "Default Exchange", selection: $defaultExchange, options: ["Auto", "NSE", "BSE"])
                        NavigationLink {
                            SectorBlacklistView()
                        } label: {
                            HStack {
                                SettingIcon(icon: "tag", color: Theme.inkSecondary)
                                Text("SECTOR BLACKLIST")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        PickerNoteRow(icon: "chart.bar", color: Theme.inkSecondary, title: "Min Market Cap", selection: $minMarketCap, options: ["Any", "Large (>20K Cr)", "Mid (5-20K Cr)", "Small (<5K Cr)"])
                    } header: {
                        Text("TRADING PREFERENCES").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

                    // ── Section 2: NOTIFICATIONS ──
                    Section {
                        ToggleNoteRow(icon: "bell.badge", color: Theme.bearRed, title: "Signal Change Alerts", isOn: $signalChangeAlerts)
                        DatePickerNoteRow(icon: "clock.fill", color: Theme.securityGold, title: "Morning Brief Time", selection: morningBriefDate)
                        PickerNoteRow(icon: "speaker.wave.2", color: Theme.bearRed, title: "Notification Sound", selection: $notificationSound, options: ["Default", "rupee_rustle.mp3"])
                        NavigationLink {
                            QuietHoursView()
                        } label: {
                            HStack {
                                SettingIcon(icon: "moon.zzz", color: Theme.inkSecondary)
                                Text("QUIET HOURS")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                    } header: {
                        Text("NOTIFICATIONS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

                    // ── Section 3: AI & ANALYSIS ──
                    Section {
                        ToggleNoteRow(icon: "waveform.badge.magnifyingglass", color: Theme.securityGold, title: "Deep Scan by Default", isOn: $defaultDeepScan)
                        ToggleNoteRow(icon: "arrow.triangle.2.circlepath", color: Theme.bearRed, title: "Auto-regenerate Stale", isOn: $autoRegenerateStale)
                        PickerNoteRow(icon: "gauge.with.dots.needle.33percent", color: Theme.bullGreen, title: "Min Confidence Alert", selection: $minConfidenceAlert, options: ["50%", "65%", "75%", "90%"])
                        PickerNoteRow(icon: "globe", color: Theme.inkSecondary, title: "Analysis Language", selection: $analysisLanguage, options: ["English", "Hindi", "Hinglish"])
                        PickerNoteRow(icon: "arrow.triangle.branch", color: Theme.securityGold, title: "Debate Rounds", selection: $debateRounds, options: ["1", "2", "3"])
                        ToggleNoteRow(icon: "shield.lefthalf.filled", color: Theme.inkSecondary, title: "Show Governance First", isOn: $showGovernanceFirst)
                        ToggleNoteRow(icon: "arrow.up.circle", color: Theme.bullGreen, title: "Alert on BUY", isOn: $alertOnBuy)
                        ToggleNoteRow(icon: "arrow.down.circle", color: Theme.bearRed, title: "Alert on SELL", isOn: $alertOnSell)
                        ToggleNoteRow(icon: "pause.circle", color: Theme.holdAmber, title: "Mute HOLD Signals", isOn: $muteHoldSignals)
                    } header: {
                        Text("AI & ANALYSIS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

                    // ── Section 4: APPEARANCE ──
                    Section {
                        // Denomination theme grid (existing)
                        ForEach(AppTheme.allCases, id: \.self) { theme in
                            HStack {
                                Circle().fill(theme == .darkImmersive ? Theme.NoteTint.twoHundred : Theme.NoteTint.ten).frame(width: 24, height: 24)
                                Text(theme.displayName)
                                    .font(Theme.engravedSerif(size: 14))
                                Spacer()
                                if theme.rawValue == selectedThemeRaw {
                                    Image(systemName: "checkmark").foregroundStyle(Theme.securityGold)
                                }
                            }
                            .contentShape(Rectangle())
                            .onTapGesture {
                                HapticManager.impact(.medium)
                                withAnimation(.spring(response: 0.4, dampingFraction: 0.72)) {
                                    selectedThemeRaw = theme.rawValue
                                    ThemeManager.shared.current = theme
                                }
                            }
                        }

                        ToggleNoteRow(icon: "moon.fill", color: .indigo, title: "Dark Inks", isOn: $darkMode)
                        PickerNoteRow(icon: "textformat.size", color: Theme.inkSecondary, title: "Font Size", selection: $fontSize, options: ["Small", "Standard", "Large"])
                        PickerNoteRow(icon: "rectangle.3.group", color: Theme.inkSecondary, title: "Layout Density", selection: $layoutDensity, options: ["Compact", "Standard", "Spacious"])
                        PickerNoteRow(icon: "chart.xyaxis.line", color: Theme.securityGold, title: "Default Chart Range", selection: $defaultChartRange, options: ["1M", "3M", "6M", "1Y"])
                        ToggleNoteRow(icon: "hare", color: Theme.inkSecondary, title: "Reduce Animations", isOn: $reduceAnimations)
                        ToggleNoteRow(icon: "character.bubble", color: Theme.inkSecondary, title: "Show Hindi Labels", isOn: $showHindiLabels)
                    } header: {
                        Text("APPEARANCE").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

                    // ── Section 5: DATA & PRIVACY ──
                    Section {
                        NavigationLink {
                            ReportManagerView(reportManager: reportManager)
                        } label: {
                            HStack {
                                SettingIcon(icon: "doc.text", color: Theme.securityGold)
                                Text("SAVED REPORTS")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                                Text("\(reportManager.savedReports.count)")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        Button {
                            HapticManager.selection()
                            URLCache.shared.removeAllCachedResponses()
                        } label: {
                            HStack {
                                SettingIcon(icon: "photo.on.rectangle.angled", color: Theme.inkSecondary)
                                Text("CLEAR IMAGE CACHE")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        Button {
                            HapticManager.selection()
                            reportManager.savedReports.removeAll()
                        } label: {
                            HStack {
                                SettingIcon(icon: "brain.head.profile", color: Theme.bearRed)
                                Text("CLEAR ANALYSIS CACHE")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        Button {
                            // Export CSV via share sheet
                        } label: {
                            HStack {
                                SettingIcon(icon: "square.and.arrow.up", color: Theme.bullGreen)
                                Text("EXPORT PORTFOLIO CSV")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        ToggleNoteRow(icon: "faceid", color: Theme.bullGreen, title: "Security Threads (Face ID)", isOn: $biometricTimeoutRaw == "immediately" ? .constant(true) : .constant(false))
                        ToggleNoteRow(icon: "eye.slash", color: Theme.inkSecondary, title: "Hide Portfolio Values", isOn: $hidePortfolioValues)
                        ToggleNoteRow(icon: "touchid", color: Theme.securityGold, title: "Biometric for Trades", isOn: $biometricTradeLock)
                    } header: {
                        Text("DATA & PRIVACY").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

                    // ── Section 6: ACCOUNT ──
                    Section {
                        PickerNoteRow(icon: "indianrupeesign", color: Theme.securityGold, title: "Currency Format", selection: $currencyDisplay, options: ["Lakhs/Crores", "Absolute"])
                        PickerNoteRow(icon: "arrow.triangle.2.circlepath", color: Theme.inkSecondary, title: "Home Auto-refresh", selection: $homeAutoRefreshSeconds, options: ["0", "30", "60", "120"])
                        NavigationLink {
                            // Server URL sheet
                        } label: {
                            HStack {
                                SettingIcon(icon: "server.rack", color: Theme.inkSecondary)
                                Text("SERVER CONNECTION")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        ToggleNoteRow(icon: "newspaper", color: Theme.securityGold, title: "IPO Alerts", isOn: $ipoAlerts)
                        Button(role: .destructive) {
                            showClearHistoryAlert = true
                        } label: {
                            HStack {
                                SettingIcon(icon: "trash", color: Theme.bearRed)
                                Text("VOID ALL RECORDS")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.bearRed)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        Button(role: .destructive) {
                            authManager.logout()
                        } label: {
                            HStack {
                                SettingIcon(icon: "door.right.hand.open", color: Theme.bearRed)
                                Text("VOID SESSION")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.bearRed)
                                Spacer()
                            }
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                    } header: {
                        Text("ACCOUNT").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                    }

                    // ── Section 7: DEVELOPER (hidden) ──
                    if showDevTools {
                        Section {
                            Button("Push Test Notification") { showTestNotifSheet = true }
                            Button("Push Morning Summary Now") { /* existing logic */ }
                            Button("Harvest YouTube Now") { /* existing logic */ }
                            Text("Notif Permission: \(notifPermissionStatus)")
                                .font(.caption)
                        } header: {
                            Text("DEVELOPER TOOLS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .alert("Void All Records?", isPresented: $showClearHistoryAlert) {
                Button("Cancel", role: .cancel) {}
                Button("Void", role: .destructive) {
                    reportManager.savedReports.removeAll()
                }
            }
        }
    }
```

- [ ] **Step 2: Keep existing helper functions**

The existing `pushMorningSummary`, `harvestYouTube`, `testNotification` functions remain unchanged. All existing `@State` variables (`showClearHistoryAlert`, `showServerURLSheet`, `showDevTools`, etc.) stay. All existing `@AppStorage` keys (`biometricTimeoutRaw`, `darkMode`, `defaultDeepScan`, etc.) stay.

- [ ] **Step 3: Remove unused state**

Remove these now-unused parts:
- The old `ScrollView` + `VStack` with `SettingsNoteGroup` blocks (old body)
- The old section structures (App Preferences, Denomination Theme, Data Registry, Archives, Server Connection) since they're now folded into the new List sections

- [ ] **Step 4: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/SettingsScreen.swift
git commit -m "Restructure SettingsScreen to iOS List with 6 sections, add 30+ new settings"
```

---

### Task C3: Build SectorBlacklistView

**File:** Create `ios/StockApp/stockme/stockme/Views/SectorBlacklistView.swift`

- [ ] **Step 1: Create the view**

```swift
import SwiftUI

struct SectorBlacklistView: View {
    @AppStorage("nivesh_sectorBlacklist") private var blacklistData: Data = Data()
    @State private var excludedSectors: Set<String> = []

    private let allSectors = [
        "Banking", "IT", "Pharma", "Auto", "FMCG",
        "Metals", "Energy", "Realty", "Media", "PSU",
    ]

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            List {
                Section {
                    ForEach(allSectors, id: \.self) { sector in
                        HStack {
                            Text(sector)
                                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                .foregroundStyle(Theme.inkPrimary)
                            Spacer()
                            if excludedSectors.contains(sector) {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(Theme.bearRed)
                            } else {
                                Image(systemName: "circle")
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            HapticManager.selection()
                            if excludedSectors.contains(sector) {
                                excludedSectors.remove(sector)
                            } else {
                                excludedSectors.insert(sector)
                            }
                            save()
                        }
                    }
                } header: {
                    Text("EXCLUDED SECTORS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                } footer: {
                    Text("Stocks in excluded sectors will not appear in screener results or alerts.")
                        .font(Theme.engravedSerif(size: 11))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Sector Blacklist")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .onAppear { load() }
    }

    private func load() {
        if let decoded = try? JSONDecoder().decode(Set<String>.self, from: blacklistData) {
            excludedSectors = decoded
        }
    }

    private func save() {
        if let encoded = try? JSONEncoder().encode(excludedSectors) {
            blacklistData = encoded
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/SectorBlacklistView.swift
git commit -m "Add SectorBlacklistView with toggle chips for 10 sectors"
```

---

### Task C4: Build QuietHoursView

**File:** Create `ios/StockApp/stockme/stockme/Views/QuietHoursView.swift`

- [ ] **Step 1: Create the view**

```swift
import SwiftUI

struct QuietHoursView: View {
    @AppStorage("nivesh_quietHoursStart") private var startSeconds: Double = 79200 // 22:00
    @AppStorage("nivesh_quietHoursEnd") private var endSeconds: Double = 25200   // 07:00
    @AppStorage("nivesh_quietHoursDays") private var quietDaysData: Data = Data()
    @State private var activeDays: Set<Int> = [0, 1, 2, 3, 4, 5, 6]

    private let dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    private var startDate: Binding<Date> {
        Binding(get: {
            Calendar.current.startOfDay(for: Date()).addingTimeInterval(startSeconds)
        }, set: {
            let comps = Calendar.current.dateComponents([.hour, .minute], from: $0)
            startSeconds = Double((comps.hour ?? 22) * 3600 + (comps.minute ?? 0) * 60)
        })
    }

    private var endDate: Binding<Date> {
        Binding(get: {
            Calendar.current.startOfDay(for: Date()).addingTimeInterval(endSeconds)
        }, set: {
            let comps = Calendar.current.dateComponents([.hour, .minute], from: $0)
            endSeconds = Double((comps.hour ?? 7) * 3600 + (comps.minute ?? 0) * 60)
        })
    }

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            List {
                Section {
                    DatePicker("From", selection: startDate, displayedComponents: .hourAndMinute)
                        .font(Theme.engravedSerif(size: 14))
                    DatePicker("Until", selection: endDate, displayedComponents: .hourAndMinute)
                        .font(Theme.engravedSerif(size: 14))
                } header: {
                    Text("QUIET HOURS WINDOW").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }

                Section {
                    HStack(spacing: Theme.Spacing.small) {
                        ForEach(0..<7, id: \.self) { day in
                            Button {
                                HapticManager.selection()
                                if activeDays.contains(day) {
                                    activeDays.remove(day)
                                } else {
                                    activeDays.insert(day)
                                }
                                saveDays()
                            } label: {
                                Text(dayNames[day])
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(activeDays.contains(day) ? Theme.canvas : Theme.inkSecondary)
                                    .frame(width: 38, height: 38)
                                    .background(
                                        Circle()
                                            .fill(activeDays.contains(day) ? Theme.securityGold : Theme.surfaceElevated)
                                    )
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.small)
                } header: {
                    Text("ACTIVE DAYS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Quiet Hours")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .onAppear { loadDays() }
    }

    private func loadDays() {
        if let decoded = try? JSONDecoder().decode(Set<Int>.self, from: quietDaysData) {
            activeDays = decoded
        }
    }

    private func saveDays() {
        if let encoded = try? JSONEncoder().encode(activeDays) {
            quietDaysData = encoded
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/QuietHoursView.swift
git commit -m "Add QuietHoursView with time window picker and day-of-week toggles"
```

---

### Task C5: Build ReportManagerView

**File:** Create `ios/StockApp/stockme/stockme/Views/ReportManagerView.swift`

- [ ] **Step 1: Create the view**

```swift
import SwiftUI

struct ReportManagerView: View {
    @ObservedObject var reportManager: LocalReportManager
    @State private var confirmDeleteAll = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            if reportManager.savedReports.isEmpty {
                VStack(spacing: Theme.Spacing.standard) {
                    Spacer()
                    Image(systemName: "doc.text.magnifyingglass")
                        .font(.system(size: 48))
                        .foregroundStyle(Theme.inkTertiary)
                    Text("No saved reports")
                        .font(Theme.engravedSerif(size: 15))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                }
            } else {
                List {
                    ForEach(reportManager.savedReports, id: \.ticker) { report in
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            HStack {
                                Text(report.ticker)
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundStyle(Theme.securityGold)
                                Spacer()
                                Text(report.signal.label)
                                    .font(Theme.microLabel(size: 8))
                                    .foregroundStyle(report.signal.color)
                                    .padding(.horizontal, Theme.Spacing.tight)
                                    .padding(.vertical, 2)
                                    .background(report.signal.color.opacity(0.12))
                                    .clipShape(Capsule())
                            }
                            Text(report.companyName)
                                .font(Theme.engravedSerif(size: 12))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineLimit(1)
                            Text("Analysed: \(report.analysisDate)")
                                .font(Theme.microLabel(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .padding(.vertical, Theme.Spacing.small)
                    }
                    .onDelete { indexSet in
                        for i in indexSet {
                            reportManager.savedReports.remove(at: i)
                        }
                    }

                    Section {
                        Button(role: .destructive) {
                            confirmDeleteAll = true
                        } label: {
                            HStack {
                                Spacer()
                                Text("DELETE ALL REPORTS")
                                    .font(Theme.officialStampFont(size: 9))
                                Spacer()
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
        }
        .navigationTitle("Saved Reports")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbar {
            if !reportManager.savedReports.isEmpty {
                EditButton()
                    .foregroundStyle(Theme.securityGold)
            }
        }
        .alert("Delete all saved reports?", isPresented: $confirmDeleteAll) {
            Button("Cancel", role: .cancel) {}
            Button("Delete All", role: .destructive) {
                reportManager.savedReports.removeAll()
            }
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/ReportManagerView.swift
git commit -m "Add ReportManagerView with saved reports list and delete"
```

---

## Edge Cases
- All new `@AppStorage` keys use `nivesh_` prefix (existing convention)
- Empty saved reports → placeholder view in ReportManagerView
- Sector blacklist empty initially → `onAppear` loads from stored JSON
- Quiet hours days start with all 7 active
- Existing settings (biometricTimeoutRaw, darkMode, etc.) preserved with existing keys
- Face ID toggle in DATA section references existing `biometricTimeoutRaw` — modify to use separate toggle
- Dev tools hidden behind existing triple-tap mechanism (preserved)
- Export CSV button placeholder — full implementation deferred (needs portfolio data model)
- "Clear Analysis Cache" currently clears `reportManager.savedReports` — can be scoped later
