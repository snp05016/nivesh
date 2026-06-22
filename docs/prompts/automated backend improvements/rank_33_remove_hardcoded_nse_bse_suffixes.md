# Prompt 33: Remove Hardcoded NSE/BSE suffixes

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Eliminate hardcoded `.NS` and `.BO` string checks in `helpers.py` by centralizing exchange normalization through a single config-driven utility.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
