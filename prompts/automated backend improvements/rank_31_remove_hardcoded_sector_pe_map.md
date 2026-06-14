# Prompt 31: Remove Hardcoded SECTOR_PE_MAP

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Move the hardcoded `SECTOR_PE_MAP` dictionary out of `analysis.py` into a database table that automatically updates using daily market medians.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
