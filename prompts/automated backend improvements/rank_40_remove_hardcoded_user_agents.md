# Prompt 40: Remove Hardcoded User-Agents

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Replace the hardcoded 'Mozilla/5.0...' string in `_nse_session()` with the `fake-useragent` package to rotate User-Agents dynamically and avoid blocks.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
