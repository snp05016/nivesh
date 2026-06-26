import logging
#!/usr/bin/env python3
"""
refresh_nse_symbols.py — Rebuild nse_bse_symbols.json from live sources

Run on your server (with internet access) to keep the stock database fresh:
    python3 backend/scripts/refresh_nse_symbols.py

Sources:
  NSE equities : https://archives.nseindia.com/content/equities/EQUITY_L.csv
  BSE equities : https://github.com/maanavshah/stock-market-india (names.js)

Output:
  backend/data/nse_bse_symbols.json  — merged, deduplicated list
"""

import csv, json, os, re, subprocess, sys, tempfile, time, urllib.request
from io import StringIO

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "nse_bse_symbols.json")
REPO_URL    = "https://github.com/maanavshah/stock-market-india.git"
NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# ── Sector guesser ─────────────────────────────────────────────────────────
SECTOR_KEYWORDS = {
    "Bank": "Banking", "Finance": "Finance", "Insurance": "Insurance",
    "Pharma": "Pharma", "Drug": "Pharma", "Chem": "Chemicals",
    "Tech": "IT", "Software": "IT", "Cement": "Cement",
    "Steel": "Steel", "Power": "Power", "Energy": "Renewable Energy",
    "Solar": "Renewable Energy", "Auto": "Auto", "Motor": "Auto",
    "Textile": "Textiles", "Hotel": "Hotels", "Media": "Media",
    "Retail": "Retail", "Jewel": "Retail", "Realty": "Real Estate",
    "Construct": "Infrastructure", "Infra": "Infrastructure",
    "Aero": "Defence", "Oil": "Oil & Gas", "Gas": "Oil & Gas",
    "Petro": "Oil & Gas", "Fertil": "Fertilizers", "Agro": "Agriculture",
    "Seed": "Agriculture", "Food": "FMCG", "Beverage": "FMCG",
    "Consumer": "FMCG", "Paint": "Paints", "Mining": "Mining",
    "Metal": "Metals", "Copper": "Metals", "Alum": "Metals",
    "Logistic": "Logistics", "Telecom": "Telecom", "Sugar": "Sugar",
    "Brew": "FMCG", "Tobacco": "FMCG",
}
def guess_sector(name: str) -> str:
    for kw, s in SECTOR_KEYWORDS.items():
        if kw.lower() in name.lower():
            return s
    return "Diversified"


# ── NSE ────────────────────────────────────────────────────────────────────
def fetch_nse() -> list[dict]:
    logging.info("Fetching NSE EQUITY_L.csv...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        req = urllib.request.Request(NSE_CSV_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logging.info(f"  NSE fetch failed: {e}")
        return []

    reader = csv.DictReader(StringIO(raw))
    stocks = []
    for row in reader:
        if row.get("SERIES", "").strip().upper() != "EQ":
            continue
        ticker = row.get("SYMBOL", "").strip().upper()
        name   = row.get("NAME OF COMPANY", "").strip()
        if ticker and name:
            stocks.append({"ticker": ticker, "name": name,
                           "sector": guess_sector(name), "exchange": "NSE"})
    logging.info(f"  NSE: {len(stocks)} equity symbols")
    return stocks


# ── BSE via GitHub repo ────────────────────────────────────────────────────
def _tokens(s: str) -> set[str]:
    s = re.sub(r'\b(LTD|LIMITED|INDIA|INDUSTRIES|IND|CO|CORP|PVT|AND|THE)\b', '', s.upper())
    return set(re.findall(r'[A-Z]{2,}', s))

def fetch_bse_from_repo(nse_stocks: list[dict]) -> list[dict]:
    logging.info("Cloning maanavshah/stock-market-india for BSE names...")
    tmpdir = tempfile.mkdtemp()
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", REPO_URL, tmpdir],
            check=True, capture_output=True, timeout=60
        )
    except Exception as e:
        logging.info(f"  git clone failed: {e}")
        return []

    names_js = os.path.join(tmpdir, "bse", "constant", "names.js")
    if not os.path.exists(names_js):
        logging.info("  bse/constant/names.js not found in repo")
        return []

    with open(names_js) as f:
        content = f.read()

    pattern = re.compile(r"'(\d+)'\s*:\s*\{\s*'companyName'\s*:\s*'([^']+)'\s*\}")
    bse_raw = pattern.findall(content)
    logging.info(f"  BSE raw entries in repo: {len(bse_raw)}")

    NON_EQ = re.compile(
        r'\d{2}[A-Z]|^[0-9]+[A-Z]{2}|BOND|NCD|DEBENTURE|PREF\b|WARR|SERIES|TRANCHE',
        re.IGNORECASE
    )

    # Build NSE token index for dedup
    nse_token_idx: dict[str, list] = {}
    for s in nse_stocks:
        for tok in _tokens(s["name"]):
            nse_token_idx.setdefault(tok, []).append(s["ticker"])

    def is_dup(name: str) -> bool:
        toks = _tokens(name)
        if not toks:
            return False
        candidates: dict[str, int] = {}
        for t in toks:
            for tk in nse_token_idx.get(t, []):
                candidates[tk] = candidates.get(tk, 0) + 1
        threshold = min(2, len(toks))
        return any(v >= threshold for v in candidates.values())

    bse_only: list[dict] = []
    for code, raw_name in bse_raw:
        c = int(code)
        if not (500000 <= c <= 599999):
            continue
        if NON_EQ.search(raw_name):
            continue
        if len(raw_name.strip()) < 4:
            continue
        if is_dup(raw_name):
            continue
        name_title = raw_name.strip().title().replace("Ltd.", "Ltd").replace("Ltd ", "Ltd ")
        bse_only.append({
            "ticker":   code,
            "name":     name_title,
            "sector":   guess_sector(raw_name),
            "exchange": "BSE",
        })

    logging.info(f"  BSE-only (not already in NSE): {len(bse_only)}")
    return bse_only


# ── Merge & save ───────────────────────────────────────────────────────────
def merge_and_save(nse: list[dict], bse_only: list[dict]) -> None:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    seen: set[str] = set()
    merged: list[dict] = []
    for s in nse + bse_only:
        if s["ticker"] not in seen:
            seen.add(s["ticker"])
            merged.append(s)

    logging.info(f"\nMerge summary:")
    logging.info(f"  NSE:      {len(nse):>5}")
    logging.info(f"  BSE-only: {len(bse_only):>5}")
    logging.info(f"  Total:    {len(merged):>5}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    logging.info(f"\nSaved: {OUTPUT_PATH}")


def main() -> None:
    nse = fetch_nse()
    time.sleep(1)
    bse_only = fetch_bse_from_repo(nse)

    if not nse and not bse_only:
        logging.info("\nBoth sources failed. Keeping existing file unchanged.")
        sys.exit(1)

    merge_and_save(nse, bse_only)
    logging.info("\nDone. Restart the backend to pick up the new symbol list.")


if __name__ == "__main__":
    main()
