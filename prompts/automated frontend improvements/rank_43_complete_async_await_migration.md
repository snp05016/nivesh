# Prompt 43: Complete async/await migration

**Category:** Architecture

**Goal:** Analyze the iOS frontend architecture to address this specific issue.

**Problem Statement / Description:**
Refactor any remaining legacy closures or Combine publishers in `NetworkManager.swift` to modern Swift concurrency (`async/await`).

**Why it will improve the system:**
It drastically improves scroll performance, reduces memory leaks, and ensures battery-efficient network usage.

**What you have to do:**
1. Read the relevant iOS Swift files (Views, ViewModels, NetworkManager).
2. Design the SwiftUI view or structural fix.
3. Implement the changes following unidirectional data flow.
4. Build and verify in Xcode / Previews.
