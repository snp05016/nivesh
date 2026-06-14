# Prompt 35: Move Signal Maps to DB

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Migrate `_BULLISH_SIGNALS` and `_SIGNAL_MAP` dictionaries out of the code and into a database-backed configuration for easier live tuning.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
