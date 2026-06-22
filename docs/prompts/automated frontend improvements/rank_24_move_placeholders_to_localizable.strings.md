# Prompt 24: Move Placeholders to Localizable.strings

**Category:** Hardcoding

**Goal:** Analyze the iOS frontend architecture to address this specific issue.

**Problem Statement / Description:**
Extract all hardcoded English placeholder text in Search and Copilot screens into a `Localizable.strings` file for future l10n.

**Why it will improve the system:**
It makes the frontend application dynamic, config-driven, and robust against backend URL or data structure changes without requiring App Store updates.

**What you have to do:**
1. Read the relevant iOS Swift files (Views, ViewModels, NetworkManager).
2. Design the SwiftUI view or structural fix.
3. Implement the changes following unidirectional data flow.
4. Build and verify in Xcode / Previews.
