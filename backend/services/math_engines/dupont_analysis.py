def calculate_dupont_analysis(
    net_income: float,
    sales: float,
    total_assets: float,
    total_equity: float
) -> dict:
    """
    Performs DuPont Analysis to break down Return on Equity (ROE).
    ROE = Profit Margin * Total Asset Turnover * Equity Multiplier
    """
    if sales == 0 or total_assets == 0 or total_equity == 0:
        raise ValueError("Sales, total assets, and total equity must be non-zero.")
        
    profit_margin = net_income / sales
    asset_turnover = sales / total_assets
    equity_multiplier = total_assets / total_equity
    
    roe = profit_margin * asset_turnover * equity_multiplier
    
    return {
        "profit_margin": profit_margin,
        "asset_turnover": asset_turnover,
        "equity_multiplier": equity_multiplier,
        "roe": roe
    }
