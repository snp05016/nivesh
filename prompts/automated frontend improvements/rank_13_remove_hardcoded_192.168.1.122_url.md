# Prompt 13: Remove Hardcoded 192.168.1.122 URL

**Category:** Hardcoding

**Goal:** Analyze the iOS frontend architecture to address this specific issue.

**Problem Statement / Description:**
Remove the hardcoded default URL `http://192.168.1.122:8000` from `NetworkManager.swift` and use Plist/XCConfig environment variables.

**Why it will improve the system:**
It makes the frontend application dynamic, config-driven, and robust against backend URL or data structure changes without requiring App Store updates.

**What you have to do:**
1. Read the relevant iOS Swift files (Views, ViewModels, NetworkManager).
2. Design the SwiftUI view or structural fix.
3. Implement the changes following unidirectional data flow.
4. Build and verify in Xcode / Previews.
