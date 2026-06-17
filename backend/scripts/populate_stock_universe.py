import asyncio
import logging
import io
import sys
import os
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_session
from models.db_models import StockUniverse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Fallback small list if NSE CSV fails
FALLBACK_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BAJFINANCE.NS", "BHARTIARTL.NS"
]

def fetch_nse_symbols() -> list[str]:
    """Fetch all NSE listed symbols from NSE India website."""
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    try:
        logger.info(f"Fetching NSE equity list from {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        symbols = df['SYMBOL'].tolist()
        
        # Suffix with .NS for Yahoo Finance
        tickers = [f"{sym}.NS" for sym in symbols]
        logger.info(f"Successfully fetched {len(tickers)} tickers from NSE.")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch from NSE: {e}. Using fallback.")
        return FALLBACK_TICKERS

async def fetch_ticker_info(ticker: str, semaphore: asyncio.Semaphore) -> tuple[str, dict]:
    """Fetch stock info from yfinance asynchronously."""
    async with semaphore:
        try:
            # Run yfinance blocking call in a thread
            info = await asyncio.to_thread(lambda: yf.Ticker(ticker).info)
            # small sleep to prevent rate limits
            await asyncio.sleep(0.1)
            return ticker, info
        except Exception as e:
            logger.debug(f"Failed to fetch {ticker}: {e}")
            return ticker, {}

def parse_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

async def populate_universe():
    with get_session() as session:
        existing_tickers = {r[0] for r in session.query(StockUniverse.ticker).all()}
    
    tickers = fetch_nse_symbols()
    # Filter out tickers we already have
    tickers_to_fetch = [t for t in tickers if t not in existing_tickers]
    
    # Limit to remainings needed to reach ~2000 or process the rest
    # We will just process up to 1000 at a time to avoid rate limits
    tickers_to_fetch = tickers_to_fetch[:1000]
    
    if not tickers_to_fetch:
        logger.info("All stocks already populated.")
        return
        
    logger.info(f"Starting to fetch yfinance data for {len(tickers_to_fetch)} remaining stocks...")

    # Lower concurrency to help prevent rate limits
    semaphore = asyncio.Semaphore(5)
    
    tasks = [fetch_ticker_info(t, semaphore) for t in tickers_to_fetch]
    results = await asyncio.gather(*tasks)

    # Process and save to database
    records = []
    for t, info in results:
        if not info or "shortName" not in info:
            continue
            
        market_cap = parse_float(info.get("marketCap"))
        pe_ratio = parse_float(info.get("trailingPE"))
        
        # Convert ratios to percentages where needed
        roe = parse_float(info.get("returnOnEquity"))
        roe = roe * 100 if roe is not None else None
        
        roce = parse_float(info.get("returnOnCapitalEmployed")) # Sometimes missing in YF, but we try
        roce = roce * 100 if roce is not None else None
        
        promoter = parse_float(info.get("heldPercentInsiders"))
        promoter = promoter * 100 if promoter is not None else None
        
        fii_holding = parse_float(info.get("heldPercentInstitutions"))
        fii_holding = fii_holding * 100 if fii_holding is not None else None
        
        div_yield = parse_float(info.get("dividendYield"))
        div_yield = div_yield * 100 if div_yield is not None else None
        
        ebitda_margin = parse_float(info.get("ebitdaMargins"))
        ebitda_margin = ebitda_margin * 100 if ebitda_margin is not None else None
        
        # Convert yf debtToEquity ratio (YF provides it as a percentage e.g., 50.5 for 50.5% or ratio, varies, but usually percentage in info)
        # We will keep it as ratio if we divide by 100 (standard Nivesh approach in nl_screener)
        de = parse_float(info.get("debtToEquity"))
        if de is not None:
            de = de / 100.0  # Convert 50.5 to 0.505 ratio
        
        stock_record = StockUniverse(
            ticker=t,
            company_name=info.get("shortName", t),
            sector=info.get("sector", "Unknown"),
            industry=info.get("industry", "Unknown"),
            market_cap=market_cap,
            pe_ratio=pe_ratio,
            roe=roe,
            roce=roce,
            debt_to_equity=de,
            promoter_holding=promoter,
            fii_holding=fii_holding,
            dii_holding=None, # YF doesn't split FII and DII clearly
            dividend_yield=div_yield,
            ebitda_margin=ebitda_margin,
            price_change_3m=None, # Require historical data fetch, omitted for speed
            price_change_1y=None, 
            rsi=None,
            updated_at=datetime.now(timezone.utc)
        )
        records.append(stock_record)
        
    logger.info(f"Successfully processed {len(records)} valid stock records. Saving to database...")
    
    with get_session() as session:
        # Do not delete, just append the new ones
        session.bulk_save_objects(records)
        session.commit()
        
    logger.info("Stock universe updated successfully!")

if __name__ == "__main__":
    asyncio.run(populate_universe())
