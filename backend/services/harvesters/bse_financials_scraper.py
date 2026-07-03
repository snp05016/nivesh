import logging
import requests
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class BalanceSheetResponse(BaseModel):
    scrip_code: str
    year: str
    statement_type: str
    raw_data: Dict[str, Any]

class FinancialResultsResponse(BaseModel):
    scrip_code: str
    period: str
    results: Dict[str, Any]

def fetch_raw_balance_sheet(scrip_code: str, year: Optional[str] = None) -> BalanceSheetResponse:
    """
    Fetches the raw balance sheet for a given BSE scrip code.
    
    Args:
        scrip_code (str): The BSE scrip code for the company.
        year (str, optional): The financial year to fetch data for. If None, fetches the latest.
        
    Returns:
        BalanceSheetResponse: A BalanceSheetResponse containing raw balance sheet data.
    """
    logger.info(f"Fetching raw balance sheet for scrip_code: {scrip_code}, year: {year}")
    
    url = f"https://api.bseindia.com/BseIndiaAPI/api/FinancialResults/w?scripcode={scrip_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.bseindia.com/'
    }
    
    fetched_data = {}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        fetched_data = response.json()
    except Exception as e:
        logger.error(f"Error fetching balance sheet for {scrip_code}: {e}")
        
    raw_data = {
        "scrip_code": scrip_code,
        "year": year or "latest",
        "statement_type": "balance_sheet",
        "raw_data": fetched_data
    }
    
    return BalanceSheetResponse(**raw_data)

def fetch_financial_results(scrip_code: str, period: str = "Annual") -> FinancialResultsResponse:
    """
    Fetches other financial results (e.g., P&L, Cash Flow) for the given scrip code.
    
    Args:
        scrip_code (str): The BSE scrip code.
        period (str): "Annual" or "Quarterly".
        
    Returns:
        FinancialResultsResponse: A FinancialResultsResponse containing the financial results.
    """
    logger.info(f"Fetching {period} financial results for scrip_code: {scrip_code}")
    
    url = f"https://api.bseindia.com/BseIndiaAPI/api/FinancialResults/w?scripcode={scrip_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.bseindia.com/'
    }
    
    fetched_results = {}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        try:
            fetched_results = response.json()
        except Exception:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            fetched_results = {"html_text": soup.get_text()[:1000]}
    except Exception as e:
        logger.error(f"Error fetching {period} financial results for {scrip_code}: {e}")
    
    raw_data = {
        "scrip_code": scrip_code,
        "period": period,
        "results": fetched_results
    }
    
    return FinancialResultsResponse(**raw_data)
