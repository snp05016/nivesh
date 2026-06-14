# Prompt 51: Fix PortfolioScreen full-state reloads

**Category:** Architecture

**Goal:** Analyze the iOS frontend architecture to address this specific issue.

**Problem Statement / Description:**
Replace heavy full-screen `@State` updates in `PortfolioScreen.swift` with granular `Equatable` view wrappers to stop frame drops.

**Why it will improve the system:**
It drastically improves scroll performance, reduces memory leaks, and ensures battery-efficient network usage.

**What you have to do:**
1. Read the relevant iOS Swift files (Views, ViewModels, NetworkManager).
2. Design the SwiftUI view or structural fix.
3. Implement the changes following unidirectional data flow.
4. Build and verify in Xcode / Previews.
