# Prompt 60: Clean up Monolithic Legacy Code

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Purge the unused `main_legacy_backup.py` and `main_old_monolithic.py` files and split `main.py` middleware into a dedicated `middleware/` folder.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
