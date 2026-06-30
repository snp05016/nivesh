import requests
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class OptionData(BaseModel):
    oi: int
    volume: int
    ltp: float

class StrikeData(BaseModel):
    CE: Optional[OptionData] = None
    PE: Optional[OptionData] = None

class CleanOIVolumeResponse(BaseModel):
    symbol: str = ""
    timestamp: str = ""
    underlying_value: float = 0.0
    expiries: List[str] = []
    strikes: Dict[float, Dict[str, StrikeData]] = {}

class NSEOptionChainHarvester:
    """
    Harvester for polling NSE Option Chain endpoints to fetch live OI and volume.
    """
    BASE_URL = "https://www.nseindia.com"
    API_URL = "https://www.nseindia.com/api/option-chain-indices?symbol="

    def __init__(self):
        self.session = requests.Session()
        # NSE requires standard browser headers to allow requests
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        })
        self._initialize_session()

    def _initialize_session(self) -> None:
        """Initialize session by hitting the base URL to get required cookies."""
        try:
            self.session.get(self.BASE_URL, timeout=10)
        except Exception as e:
            logger.error(f"Failed to initialize NSE session: {e}")

    def fetch_option_chain(self, symbol: str = "NIFTY") -> Optional[Dict[str, Any]]:
        """
        Fetch the live option chain for a given index symbol (e.g., NIFTY, BANKNIFTY).
        """
        url = f"{self.API_URL}{symbol}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Error fetching option chain for {symbol}: {e}. Retrying session initialization...")
            # Sometimes session expires or gets blocked, try to re-initialize once
            self._initialize_session()
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as retry_e:
                logger.error(f"Retry failed for {symbol}: {retry_e}")
                return None

    def get_clean_oi_volume_data(self, symbol: str = "NIFTY") -> CleanOIVolumeResponse:
        """
        Fetch and extract clean Open Interest (OI) and Volume data.
        Returns a structured dictionary with call and put data per strike price and expiry.
        """
        raw_data = self.fetch_option_chain(symbol)
        if not raw_data or 'records' not in raw_data:
            return CleanOIVolumeResponse()

        strikes = {}

        for item in raw_data['records'].get('data', []):
            strike = item.get('strikePrice')
            expiry = item.get('expiryDate')
            
            if strike not in strikes:
                strikes[strike] = {}
                
            strikes[strike][expiry] = StrikeData(
                CE=OptionData(
                    oi=item.get('CE', {}).get('openInterest', 0),
                    volume=item.get('CE', {}).get('totalTradedVolume', 0),
                    ltp=item.get('CE', {}).get('lastPrice', 0),
                ) if 'CE' in item else None,
                PE=OptionData(
                    oi=item.get('PE', {}).get('openInterest', 0),
                    volume=item.get('PE', {}).get('totalTradedVolume', 0),
                    ltp=item.get('PE', {}).get('lastPrice', 0),
                ) if 'PE' in item else None
            )

        return CleanOIVolumeResponse(
            symbol=symbol,
            timestamp=raw_data['records'].get('timestamp', ''),
            underlying_value=raw_data['records'].get('underlyingValue', 0),
            expiries=raw_data['records'].get('expiryDates', []),
            strikes=strikes
        )

def get_live_oi_volume(symbol: str = "NIFTY") -> CleanOIVolumeResponse:
    """
    Convenience function to fetch live OI and volume data for a given symbol.
    """
    harvester = NSEOptionChainHarvester()
    return harvester.get_clean_oi_volume_data(symbol)
