# Prompt 13: Replace slow Selenium/BS4 scraping

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Swap out the blocking BeautifulSoup scraper with asynchronous `aiohttp` requests and strict TTL caching for parsing external news and data sites.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
