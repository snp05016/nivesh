# Prompt 18: Remove 200-char Error limits

**Category:** Hardcoding

**Goal:** Analyze the iOS frontend architecture to address this specific issue.

**Problem Statement / Description:**
Remove hardcoded `.prefix(200)` limits in `NetworkManager` error diagnostics to allow users to see full, scrollable stack traces.

**Why it will improve the system:**
It makes the frontend application dynamic, config-driven, and robust against backend URL or data structure changes without requiring App Store updates.

**What you have to do:**
1. Read the relevant iOS Swift files (Views, ViewModels, NetworkManager).
2. Design the SwiftUI view or structural fix.
3. Implement the changes following unidirectional data flow.
4. Build and verify in Xcode / Previews.
