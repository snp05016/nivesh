# Prompt 11: Shift HMM Regime Logic to C/Rust

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Migrate the Hidden Markov Model state decoding from pure Python to a compiled C/Rust extension for 10x faster regime classification over long time horizons.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
