# Stock App Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate imports and improve code readability in `main.py` and `database.py` while ensuring the application remains functional.

**Architecture:** Refactoring imports to the top level, removing duplicates, and applying consistent styling.

**Tech Stack:** Python, FastAPI, SQLAlchemy.

---

### Task 1: Refactor `database.py`

**Files:**
- Modify: `database.py`

- [ ] **Step 1: Cleanup and consolidate imports in `database.py`**
    - Move `contextmanager` from `from contextlib import contextmanager` to the top.
    - Consolidate all imports at the top.
    - Remove redundant `import hashlib` inside `create_user`.
    - Improve spacing between classes and functions.

- [ ] **Step 2: Commit `database.py` changes**

```bash
git add database.py
git commit -m "refactor: consolidate imports and improve readability in database.py"
```

### Task 2: Refactor `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Consolidate and deduplicate imports in `main.py`**
    - Move `import json`, `import threading`, `import random`, `import math`, `import anthropic` to the top.
    - Remove duplicate `import time` and `import time as _time`. Standardize on `import time`.
    - Group imports logically: standard library, third-party, local.

- [ ] **Step 2: Improve readability in `main.py`**
    - Ensure consistent spacing between functions and classes (2 newlines for top-level).
    - Fix any indentation inconsistencies.

- [ ] **Step 3: Commit `main.py` changes**

```bash
git add main.py
git commit -m "refactor: consolidate imports and improve readability in main.py"
```

### Task 3: Verification

- [ ] **Step 1: Verify app starts**
    - Run: `python main.py` or use a script that starts the FastAPI app.
    - Expected: No import errors, server starts.

- [ ] **Step 2: Run `test_run.py`**
    - Run: `python test_run.py`
    - Expected: Tests pass as before.
