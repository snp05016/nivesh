# Prompt 37: Eliminate Hardcoded Token Limits

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Extract the `max_tokens=1000` hardcoded limits in the LLM agent configurations and map them to dynamic variables controlled via `.env`.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
