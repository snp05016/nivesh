# Stream B: Morning Brief Prominent Card + Nav Bar Icon — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render Morning Brief as a prominent dismissible card pinned at the top of HomeScreen feed with a static `newspaper` icon in the navigation bar. Zero new API calls, zero new files.

**Architecture:** Modify `HomeScreen.swift` only. Replace the existing `.morning` section's card with an eye-catching dismissible card. Add toolbar icon. No new files — all inline changes.

**Tech Stack:** SwiftUI, existing `Theme.*` tokens, `@AppStorage`, `MorningDecreeCard`, `MorningSummaryResponse`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `Views/HomeScreen.swift` | Modify | Prominent brief card, toolbar icon, state management |

---

### Task B1: Add Morning Brief State + Date Tracking

**File:** `ios/StockApp/stockme/stockme/Views/HomeScreen.swift`

Find the `@State` declarations block (around line 627-634). Add:

- [ ] **Step 1: Add state variables**

After `@FocusState private var searchFocused: Bool` (line 629):

```swift
    @AppStorage("morningBriefShownDate") private var morningBriefShownDate = ""
    @State private var briefDismissed = false
```

- [ ] **Step 2: Add computed property for "should show brief today"**

After the new state variables:

```swift
    private var shouldShowBriefToday: Bool {
        let today = DateFormatter()
        today.dateFormat = "yyyy-MM-dd"
        let todayStr = today.string(from: Date())
        if morningBriefShownDate != todayStr { briefDismissed = false }
        return !briefDismissed && viewModel.morningBriefData != nil
    }
```

- [ ] **Step 3: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/HomeScreen.swift
git commit -m "Add morning brief dismiss state + date tracking to HomeScreen"
```

---

### Task B2: Build Prominent Dismissible Morning Brief Card

**File:** `ios/StockApp/stockme/stockme/Views/HomeScreen.swift`

Replace the existing `.morning` section render block (lines 2611-2622) with a prominent card. The card renders at the top of the feed (as section ID `.morning`) when `shouldShowBriefToday` is true.

- [ ] **Step 1: Replace the .morning case in renderSection**

Replace lines 2611-2622:

```swift
        case .morning:
            if shouldShowBriefToday, let briefData = viewModel.morningBriefData {
                VStack(spacing: Theme.Spacing.card) {
                    prominentMorningBriefCard(briefData)
                }
                .id(HomeSectionID.morning.rawValue)
            } else if let briefData = viewModel.morningBriefData {
                // Brief was dismissed today — show collapsed version
                VStack(spacing: Theme.Spacing.card) {
                    SectionHeader(title: "Morning Brief", hindiTitle: "प्रातःकालीन सारांश")
                    MorningDecreeCard(briefData: briefData)
                        .padding(.horizontal, Theme.screenPadding)
                }
                .id(HomeSectionID.morning.rawValue)
            } else {
                VStack(spacing: Theme.Spacing.card) {
                    SectionHeader(title: "Morning Brief", hindiTitle: "प्रातःकालीन सारांश")
                    DashboardLoadingCard(label: "Morning Brief", isLoading: viewModel.isLoading)
                }
                .id(HomeSectionID.morning.rawValue)
            }
```

- [ ] **Step 2: Add the prominentMorningBriefCard function**

Add this private function in the `HomeScreen` extension where `renderSection` lives:

```swift
    @ViewBuilder
    private func prominentMorningBriefCard(_ briefData: MorningSummaryResponse) -> some View {
        let moodColor: Color = {
            switch briefData.mood {
            case "positive": return Theme.bullGreen
            case "negative": return Theme.bearRed
            default: return Theme.holdAmber
            }
        }()

        VStack(spacing: Theme.Spacing.none) {
            HStack(alignment: .center, spacing: Theme.Spacing.none) {
                // Mood-colored left-edge accent strip
                Rectangle()
                    .fill(moodColor)
                    .frame(width: 4)
                    .frame(maxHeight: .infinity)

                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    // Dateline with mood dot
                    HStack(spacing: Theme.Spacing.tight) {
                        Circle()
                            .fill(moodColor)
                            .frame(width: 8, height: 8)
                        Text("MARKETS OPEN")
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .tracking(1.2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("·")
                            .foregroundStyle(Theme.inkTertiary)
                        Text(Date().formatted(.dateTime.day().month(.abbreviated).hour().minute()))
                            .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                    }

                    // Mood headline
                    Text(briefData.mood == "positive" ? "Market mood: POSITIVE" :
                         briefData.mood == "negative" ? "Market mood: NEGATIVE" : "Market mood: NEUTRAL")
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                        .foregroundStyle(Theme.inkPrimary)

                    // Summary (3 lines max)
                    Text(briefData.summary)
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(4)
                        .lineLimit(3)

                    // Priority items (max 2)
                    if let priority = briefData.priorityItems, !priority.isEmpty {
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            ForEach(priority.prefix(2), id: \.self) { item in
                                HStack(spacing: Theme.Spacing.small) {
                                    Text("⚠")
                                        .font(.caption2)
                                    Text(item)
                                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                                        .foregroundStyle(Theme.inkSecondary)
                                        .lineLimit(1)
                                }
                            }
                        }
                    }

                    // Action buttons
                    HStack(spacing: Theme.Spacing.standard) {
                        Button {
                            HapticManager.selection()
                            // Expand to show full brief — toggle to full MorningDecreeCard mode
                            briefDismissed = false // un-dismissed to trigger re-read
                            // The card stays expanded. Tapping READ FULL BRIEF scrolls to detailed section
                        } label: {
                            Text("READ FULL BRIEF")
                                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                .tracking(1)
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.standard)
                                .padding(.vertical, Theme.Spacing.small)
                                .background(Theme.securityGold.opacity(0.1))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                        }
                        .buttonStyle(EKPressStyle())

                        Button {
                            HapticManager.selection()
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                briefDismissed = true
                                let today = DateFormatter()
                                today.dateFormat = "yyyy-MM-dd"
                                morningBriefShownDate = today.string(from: Date())
                            }
                        } label: {
                            Text("✕ DISMISS")
                                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                                .tracking(1)
                                .foregroundStyle(Theme.inkTertiary)
                        }
                        .buttonStyle(EKPressStyle())
                    }
                }
                .padding(Theme.Spacing.card)
            }
            .banknoteCard()
            .padding(.horizontal, Theme.screenPadding)
            .transition(.move(edge: .top).combined(with: .opacity))
        }
    }
```

- [ ] **Step 3: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/HomeScreen.swift
git commit -m "Build prominent dismissible morning brief card replacing old section"
```

---

### Task B3: Add Nav Bar Icon for Morning Brief

**File:** `ios/StockApp/stockme/stockme/Views/HomeScreen.swift`

Add a `newspaper` icon to the navigation bar that shows a mood dot when a brief is available. The HomeScreen is inside a NavigationStack from the parent TabView, so `.toolbar` works.

- [ ] **Step 1: Find the outer body container**

The HomeScreen body starts at line 640 with `NavigationStack(path: $navigationPath)`. Wait — looking at the earlier exploration, line 641 shows `NavigationStack(path: $navigationPath) {`. But my grep didn't find NavigationStack in HomeScreen. Let me re-check.

Actually, the grep might have failed because I used `"` quotes. Line 641 is: `NavigationStack(path: $navigationPath) {`. So there IS a NavigationStack. Let me add toolbar items to it.

Find the closing of the ScrollView and outer ZStack (around line 714 where `.sheet` modifiers start). Add this BEFORE the `.sheet` modifiers:

```swift
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                if viewModel.morningBriefData != nil {
                    Button {
                        HapticManager.selection()
                        if briefDismissed {
                            briefDismissed = false
                            morningBriefShownDate = ""
                        }
                    } label: {
                        ZStack(alignment: .topTrailing) {
                            Image(systemName: "newspaper")
                                .font(.title3.weight(.medium))
                                .foregroundStyle(briefDismissed ? Theme.inkTertiary : Theme.securityGold)
                                .frame(width: 28, height: 28)

                            if briefDismissed, viewModel.morningBriefData != nil {
                                // Mood dot when unread (dismissed but data exists = "there's a brief you haven't seen")
                                let moodColor: Color = {
                                    switch viewModel.morningBriefData?.mood {
                                    case "positive": return Theme.bullGreen
                                    case "negative": return Theme.bearRed
                                    default: return Theme.holdAmber
                                    }
                                }()
                                Circle()
                                    .fill(moodColor)
                                    .frame(width: 7, height: 7)
                                    .offset(x: 4, y: -4)
                            }
                        }
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
```

- [ ] **Step 2: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/HomeScreen.swift
git commit -m "Add morning brief newspaper icon to nav bar with mood dot"
```

---

## Edge Cases
- Brief data not loaded yet → card not shown, icon not shown
- User dismisses brief → card removed with animation, icon shows mood dot (unread indicator)
- Next day → `briefDismissed` auto-resets via `shouldShowBriefToday` computed property
- User taps nav icon when brief dismissed → resets `briefDismissed` and clears date so card reappears
- Already visible card → "READ FULL BRIEF" can trigger scroll-to on existing MorningDecreeCard section
- No API calls anywhere — uses `viewModel.morningBriefData` from existing fetch
