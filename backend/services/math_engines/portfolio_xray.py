from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class AssetAllocationResponse(BaseModel):
    allocation: Dict[str, float]

class PortfolioRiskMetricsResponse(BaseModel):
    average_return: Optional[float] = None
    volatility: Optional[float] = None

def calculate_asset_allocation(portfolio_holdings: List[Dict[str, Any]]) -> AssetAllocationResponse:
    """
    Calculate asset allocation percentages from a list of portfolio holdings.
    
    Args:
        portfolio_holdings: List of dicts, e.g., [{'asset_class': 'Equity', 'value': 1000}, ...]
        
    Returns:
        Dict mapping asset classes to their percentage allocation in the portfolio.
    """
    allocation = {}
    total_value = sum(h.get('value', 0.0) for h in portfolio_holdings)
    
    if total_value <= 0:
        return AssetAllocationResponse(allocation=allocation)
        
    for holding in portfolio_holdings:
        ac = holding.get('asset_class', 'Unknown')
        allocation[ac] = allocation.get(ac, 0.0) + holding.get('value', 0.0)
        
    for ac in allocation:
        allocation[ac] = round((allocation[ac] / total_value) * 100.0, 2)
        
    return AssetAllocationResponse(allocation=allocation)

def calculate_portfolio_risk_metrics(portfolio_returns: List[float]) -> PortfolioRiskMetricsResponse:
    """
    Calculate basic risk metrics for a portfolio given historical returns.
    
    Args:
        portfolio_returns: List of historical returns (e.g., monthly or daily)
        
    Returns:
        Dict with 'average_return' and 'volatility' (standard deviation).
    """
    import statistics
    
    if not portfolio_returns:
        return PortfolioRiskMetricsResponse()
        
    avg_return = statistics.mean(portfolio_returns)
    volatility = statistics.stdev(portfolio_returns) if len(portfolio_returns) > 1 else 0.0
    
    return PortfolioRiskMetricsResponse(
        average_return=round(avg_return, 4),
        volatility=round(volatility, 4)
    )
