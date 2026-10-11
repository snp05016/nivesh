import calendar
import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class CapitalGainsResponse(BaseModel):
    STCG: float
    LTCG: float

class Transaction:
    def __init__(self, date: datetime.date, txn_type: str, units: float, price: float):
        self.date = date
        self.txn_type = txn_type.upper() # 'BUY' or 'SELL'
        self.units = float(units)
        self.price = float(price)

def _add_months(d: datetime.date, months: int) -> datetime.date:
    """Calendar-month addition, clamped to month end (31 Jan + 1 -> 28/29 Feb)."""
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    return datetime.date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def calculate_capital_gains(transactions: List[Transaction], long_term_months: int = 12) -> CapitalGainsResponse:
    """
    Calculate STCG and LTCG using the FIFO (First-In-First-Out) method.
    
    Args:
        transactions: List of Transaction objects (buys and sells)
        long_term_months: Holding must exceed this many calendar months to be Long Term
            (default 12: listed equity is LTCG only if held *more than* 12 months)
        
    Returns:
        Dict with 'STCG' (Short Term Capital Gains) and 'LTCG' (Long Term Capital Gains)
    """
    buys = []
    stcg = 0.0
    ltcg = 0.0
    
    # Sort transactions by date (oldest first)
    sorted_txns = sorted(transactions, key=lambda t: t.date)
    
    for txn in sorted_txns:
        if txn.txn_type == 'BUY':
            buys.append({"date": txn.date, "units": txn.units, "price": txn.price})
        elif txn.txn_type == 'SELL':
            units_to_sell = txn.units
            
            while units_to_sell > 1e-6 and buys:
                oldest_buy = buys[0]
                units_sold_from_this_buy = min(oldest_buy["units"], units_to_sell)
                
                # Calculate gain
                buy_value = units_sold_from_this_buy * oldest_buy["price"]
                sell_value = units_sold_from_this_buy * txn.price
                gain = sell_value - buy_value
                
                # Check if long term or short term
                # Calendar months, not days: a 12-month hold spanning 29 Feb is 366
                # days but still not "more than 12 months".
                if txn.date > _add_months(oldest_buy["date"], long_term_months):
                    ltcg += gain
                else:
                    stcg += gain
                
                # Update remaining units
                units_to_sell -= units_sold_from_this_buy
                oldest_buy["units"] -= units_sold_from_this_buy
                
                # Remove the buy transaction if fully depleted
                if oldest_buy["units"] < 1e-6:
                    buys.pop(0)
                    
            if units_to_sell > 1e-6:
                raise ValueError(f"Invalid transaction sequence: Attempted to sell {txn.units} but only enough buys for the difference. Unsold remainder: {units_to_sell}")
                
    return CapitalGainsResponse(
        STCG=round(stcg, 4),
        LTCG=round(ltcg, 4)
    )
