import requests
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class NavDataResponse(BaseModel):
    category: str
    scheme_code: str
    isin_div_payout_growth: str
    isin_div_reinvestment: str
    scheme_name: str
    net_asset_value: str
    date: str

AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

def fetch_amfi_nav_data(url: str = AMFI_NAV_URL) -> str:
    """
    Fetches the latest NAV data from AMFI.
    """
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text

def parse_amfi_nav_data(nav_data: str) -> List[NavDataResponse]:
    """
    Parses the AMFI NAV data text into a list of dictionaries.
    """
    parsed_data = []
    lines = nav_data.splitlines()
    
    current_category = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # It's a category header if it doesn't contain a semicolon
        if ';' not in line:
            current_category = line
            continue
            
        parts = line.split(';')
        
        # Skip the header row
        if parts[0] == "Scheme Code":
            continue
            
        if len(parts) >= 6:
            scheme_data = NavDataResponse(
                category=current_category,
                scheme_code=parts[0],
                isin_div_payout_growth=parts[1],
                isin_div_reinvestment=parts[2],
                scheme_name=parts[3],
                net_asset_value=parts[4],
                date=parts[5]
            )
            parsed_data.append(scheme_data)
            
    return parsed_data

def get_latest_nav() -> List[NavDataResponse]:
    """
    Convenience function to fetch and parse the latest NAV data.
    """
    raw_data = fetch_amfi_nav_data()
    return parse_amfi_nav_data(raw_data)
