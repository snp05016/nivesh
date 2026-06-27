import os
import re

files_to_fix = [
    "backend/routers/portfolio.py",
    "backend/services/macro_modifiers.py",
    "backend/services/nse_data_provider.py",
    "backend/services/filings_extractor.py",
    "backend/services/options_scraper.py",
    "backend/services/scraper.py",
    "backend/services/harvester_expert.py",
    "backend/services/nse_client.py"
]

pattern = re.compile(r'"User-Agent":\s*\(?\s*"Mozilla/[^"]+"(\s*\)\s*,|,)?', re.IGNORECASE | re.MULTILINE)

for filepath in files_to_fix:
    if not os.path.exists(filepath):
        continue
    with open(filepath, "r") as f:
        content = f.read()
    
    # We will replace hardcoded UA strings with a call to config.settings.get_user_agent()
    # First, inject the import at the top
    if "from config.settings import get_user_agent" not in content and "User-Agent" in content:
        content = "from config.settings import get_user_agent\n" + content
    
    new_content = re.sub(pattern, r'"User-Agent": get_user_agent(),', content)
    
    with open(filepath, "w") as f:
        f.write(new_content)

print("Done patching User-Agents!")
