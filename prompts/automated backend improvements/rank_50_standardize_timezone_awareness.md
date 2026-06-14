# Prompt 50: Standardize Timezone Awareness

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Audit all `datetime.utcnow()` and `datetime.now()` calls across `orchestrator.py` to strictly use `timezone.utc` to prevent localized server time bugs.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
