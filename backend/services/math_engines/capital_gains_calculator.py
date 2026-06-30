import datetime
from typing import List, Dict, Any

class Transaction:
    def __init__(self, date: datetime.date, txn_type: str, units: float, price: float):
        self.date = date
        self.txn_type = txn_type.upper() # 'BUY' or 'SELL'
        self.units = float(units)
        self.price = float(price)

def calculate_capital_gains(transactions: List[Transaction], long_term_days: int = 365) -> Dict[str, float]:
    """
    Calculate STCG and LTCG using the FIFO (First-In-First-Out) method.
    
    Args:
        transactions: List of Transaction objects (buys and sells)
        long_term_days: Number of holding days to qualify as Long Term Capital Gains (default 365)
        
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
                holding_period = (txn.date - oldest_buy["date"]).days
                if holding_period > long_term_days:
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
                
    return {
        "STCG": round(stcg, 4),
        "LTCG": round(ltcg, 4)
    }
