# Stream A: Extreme Analysis Premium Dossier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the "AI REPORT" tab of extreme analysis to look like a declassified intelligence dossier. Redaction-bar section headers, CLASSIFIED circular stamps, aged-paper background, document footer. No data changes.

**Architecture:** Three new private structs (`DossierSectionHeader`, `ClassifiedStamp`, `DossierFooter`) added inline in `AnalysisScreen.swift`. All 10+ section headers in `aiReportScroll` replaced with redaction bars. Key sections get classified stamps. Aged-paper tint applied via background overlay. Standard analysis tier untouched.

**Tech Stack:** SwiftUI, existing `Theme.*` tokens, existing `GuillocheDivider`, `EKPressStyle`, `HapticManager`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `AnalysisScreen.swift` | Modify | Add 3 new components, replace section headers, add stamps, aged-paper background, dossier footer |

---

### Task A1: Add Dossier Components (Private Structs)

**File:** `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift`

Insert these 3 private structs near the other private structs (after `ExplainThisSignalCard`, around line 1966):

- [ ] **Step 1: Add `DossierSectionHeader` — redaction bar that animates to reveal**

```swift
private struct DossierSectionHeader: View {
    let title: String
    @State private var revealed = false

    var body: some View {
        if revealed {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                .tracking(2)
                .foregroundStyle(Theme.inkPrimary)
                .transition(.opacity.combined(with: .move(edge: .leading)))
        } else {
            HStack(spacing: 0) {
                Text("████████  ")
                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption))
                    .foregroundStyle(Theme.bearRed.opacity(0.5))
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                    .tracking(2)
                    .foregroundStyle(Theme.bearRed.opacity(0.4))
                    .strikethrough(true, color: Theme.bearRed.opacity(0.3))
            }
            .padding(.horizontal, Theme.Spacing.small)
            .padding(.vertical, Theme.Spacing.tight)
            .background(Theme.bearRed.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.bearRed.opacity(0.15), lineWidth: 0.5))
            .onAppear {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.7).delay(0.15)) {
                    revealed = true
                }
            }
        }
    }
}
```

- [ ] **Step 2: Add `ClassifiedStamp` — red circular stamp overlay**

```swift
private struct ClassifiedStamp: View {
    let text: String
    let size: CGFloat

    init(_ text: String = "CLASSIFIED", size: CGFloat = 64) {
        self.text = text
        self.size = size
    }

    var body: some View {
        Text(text.uppercased())
            .font(Theme.officialStampFont(size: 6, relativeTo: .caption2))
            .tracking(2)
            .foregroundStyle(Theme.bearRed.opacity(0.18))
            .frame(width: size, height: size)
            .overlay(
                Circle()
                    .strokeBorder(Theme.bearRed.opacity(0.12), style: StrokeStyle(lineWidth: 1.5, dash: [4, 2]))
            )
            .rotationEffect(.degrees(-12))
    }
}
```

- [ ] **Step 3: Add `DossierFooter` — end-of-document classification**

```swift
private struct DossierFooter: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            GuillocheDivider()
            HStack {
                Text("DOCUMENT END")
                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                Text("·")
                    .foregroundStyle(Theme.inkTertiary)
                Text("Nivesh AI Research Desk")
                    .font(Theme.engravedSerif(size: 8, weight: .regular, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
                Text("·")
                    .foregroundStyle(Theme.inkTertiary)
                Text("UNCLASSIFIED")
                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                    .tracking(1)
                    .foregroundStyle(Theme.bullGreen.opacity(0.5))
            }
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.standard)
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "Add dossier components: DossierSectionHeader, ClassifiedStamp, DossierFooter"
```

---

### Task A2: Replace Section Headers with Redaction Bars

**File:** `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift`

Replace every `SectionHeaderView(title: "TEXT")` and `SectionDivider()` with `DossierSectionHeader(title: "TEXT")` inside the extreme-only render path. Since `aiReportScroll` is shared by both standard and extreme, wrap the changes in a conditional: `if analysis.analysisTier == "extreme"`.

- [ ] **Step 1: Wrap stockHeaderSection title in DossierSectionHeader**

Find `stockHeaderSection` (line 652). The section currently has no explicit header — it directly shows company name. Add a dossier header ABOVE the company name, only for extreme:

In `stockHeaderSection`, before the `HStack` with companyName, add:
```swift
if analysis.analysisTier == "extreme" {
    DossierSectionHeader(title: "SUBJECT PROFILE")
        .padding(.bottom, Theme.Spacing.small)
}
```

- [ ] **Step 2: Replace AI VERDICT header with DossierSectionHeader**

In `aiVerdictCard` (line 760), replace the `SectionDivider()` + `Text("AI VERDICT")` (lines 762-766) with:
```swift
DossierSectionHeader(title: "AI VERDICT")
    .padding(.bottom, Theme.Spacing.medium)
```
Remove the `SectionDivider()` call entirely. Keep the date on the right side. Wrap this in `if analysis.analysisTier == "extreme"` — for standard tier, keep existing SectionDivider+text.

- [ ] **Step 3: Replace all other section headers in aiReportScroll**

In `aiReportScroll` (line 607), find each section function call and replace their internal headers. The sections are:
- `signalTimelineSection` → replace `SectionHeaderView(title: "SIGNAL ACCURACY TIMELINE")` with `DossierSectionHeader(title: "SIGNAL ACCURACY TIMELINE")`
- `dialecticDebateSection` → replace its header with `DossierSectionHeader(title: "DIALECTIC DEBATE")`
- `timeHorizonSection` → replace with `DossierSectionHeader(title: "TIME HORIZONS")`
- `riskFactorsSection` → replace with `DossierSectionHeader(title: "RISK FACTORS")`
- `fundamentalsSection` → replace with `DossierSectionHeader(title: "FUNDAMENTALS")`
- `extremeChartSections` → replace with `DossierSectionHeader(title: "BONUS CHARTS")`
- `newsSection` → replace with `DossierSectionHeader(title: "SIGNALS INTELLIGENCE")`
- `whatToWatchSection` → replace with `DossierSectionHeader(title: "SURVEILLANCE WATCHLIST")`
- `disclaimerSection` → replace with `DossierSectionHeader(title: "DISCLAIMER")`

Each replacement must be conditional: `if analysis.analysisTier == "extreme"`. For standard tier, keep existing headers.

- [ ] **Step 4: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "Replace all section headers with redaction bars in extreme dossier mode"
```

---

### Task A3: Add Classified Stamps + Aged Paper + Footer

**File:** `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift`

- [ ] **Step 1: Add CLASSIFIED stamp to riskFactorsSection**

Find `riskFactorsSection`. At the top of its VStack, add:
```swift
if analysis.analysisTier == "extreme" {
    HStack {
        Spacer()
        ClassifiedStamp("CLASSIFIED", size: 56)
            .offset(x: 12, y: -8)
    }
    .padding(.bottom, -40)
    .zIndex(1)
}
```

- [ ] **Step 2: Add CONFIDENTIAL stamp to fundamentalsSection**

Same pattern as above, using `ClassifiedStamp("CONFIDENTIAL", size: 56)`.

- [ ] **Step 3: Add SATELLITE IMAGERY stamp to heroChartSection**

In `heroChartSection`, add at top-right corner:
```swift
if analysis.analysisTier == "extreme" {
    ClassifiedStamp("SATELLITE IMAGERY", size: 72)
        .frame(maxWidth: .infinity, alignment: .topTrailing)
        .offset(x: -8, y: 8)
        .zIndex(2)
}
```

- [ ] **Step 4: Add aged-paper background overlay**

In `renderFullAnalysis` (line 564), find the extreme branch. Add a subtle overlay to the outer container:
```swift
// On the VStack or ZStack containing the extreme content:
.overlay(
    Rectangle()
        .fill(Theme.inkPrimary)
        .opacity(0.015)
        .allowsHitTesting(false)
)
```

- [ ] **Step 5: Add DossierFooter after disclaimerSection**

In `aiReportScroll` (line 630), after `disclaimerSection(analysis)`, add:
```swift
if analysis.analysisTier == "extreme" {
    DossierFooter()
        .padding(.top, Theme.Spacing.large)
}
```

- [ ] **Step 6: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "Add classified stamps, aged-paper overlay, dossier footer to extreme analysis"
```

---

## Edge Cases
- Standard analysis tier renders unchanged (no dossier elements)
- Redaction bar animation fires once via `onAppear` + `@State`
- Stamps use `.allowsHitTesting(false)` on background overlay so taps pass through
- Aged-paper tint is `.opacity(0.015)` — preserves text contrast per spec
- No watermark on `aiVerdictCard` per revised spec
