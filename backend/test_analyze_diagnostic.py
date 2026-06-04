import sys
import os
import json
import asyncio
from datetime import date

# Add current directory to path so we can import main
sys.path.append(os.getcwd())

from main import analyze, _normalize_response

async def diagnostic():
    ticker = "TCS"
    exchange = "NSE"
    print(f"Testing analyze for {ticker}.{exchange}...")
    
    try:
        # We use mock if available or just run it. 
        # analyze function might take time.
        result = analyze(ticker, exchange)
        # _normalize_response is called inside analyze usually, but let's be sure
        normalized = _normalize_response(result)
        
        mandatory_keys = [
            "ticker", "company_name", "analysis_date", "signal", "confidence_pct",
            "current_price_inr", "target_prices", "upside_downside_pct",
            "bull_case", "bear_case", "key_risks", "key_factors",
            "fundamentals_snapshot", "what_to_watch", "disclaimer"
        ]
        
        print("\n=== Top-level Mandatory Keys ===")
        for key in mandatory_keys:
            present = key in normalized
            val = normalized.get(key)
            print(f"{key:25}: {'OK' if present else 'MISSING'} ({type(val).__name__})")

        print("\n=== target_prices ===")
        tp = normalized.get("target_prices", {})
        for key in ["short_term_3m", "medium_term_12m", "long_term_36m"]:
            print(f"{key:25}: {'OK' if key in tp else 'MISSING'}")

        print("\n=== upside_downside_pct ===")
        ud = normalized.get("upside_downside_pct", {})
        for key in ["short_term", "medium_term", "long_term"]:
            print(f"{key:25}: {'OK' if key in ud else 'MISSING'}")

        print("\n=== key_factors ===")
        kf = normalized.get("key_factors", {})
        for key in [
            "management_quality", "geopolitical_context", "promoter_fii_dii_activity",
            "turnaround_story", "fundamentals_summary", "global_macro_impact",
            "news_sentiment"
        ]:
            print(f"{key:25}: {'OK' if key in kf else 'MISSING'}")

    except Exception as e:
        print(f"Error during diagnostic: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnostic())
