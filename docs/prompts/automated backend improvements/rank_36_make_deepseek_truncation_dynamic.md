# Prompt 36: Make DeepSeek Truncation Dynamic

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Remove the hardcoded 8000-character limit in `reformat_with_deepseek` and implement a dynamic token-counting threshold using tiktoken.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
