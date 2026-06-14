# Prompt 39: Centralize Cache TTLs

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Move `_QUICK_INFO_TTL` and `_ASM_GSM_CACHE_TTL` out of random places in routers and into a centralized `settings.py` or `.env` configuration.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
