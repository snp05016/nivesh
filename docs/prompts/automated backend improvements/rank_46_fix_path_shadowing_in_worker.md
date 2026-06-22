# Prompt 46: Fix Path Shadowing in Worker

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Resolve the risky `sys.path.insert(0)` hack in `_run_analysis_worker` that shadows the `tradingagents-core` module, which causes brittle local imports.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
