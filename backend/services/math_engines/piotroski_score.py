def calculate_piotroski_score(
    net_income_current: float,
    operating_cash_flow_current: float,
    roa_current: float,
    roa_previous: float,
    long_term_debt_current: float,
    long_term_debt_previous: float,
    current_ratio_current: float,
    current_ratio_previous: float,
    shares_outstanding_current: float,
    shares_outstanding_previous: float,
    gross_margin_current: float,
    gross_margin_previous: float,
    asset_turnover_current: float,
    asset_turnover_previous: float
) -> int:
    """
    Calculates the Piotroski F-Score (0-9) to determine the financial strength of a company.
    
    Scores are awarded based on:
    1. Profitability (Net income, Operating Cash Flow, ROA, Cash flow vs Net income)
    2. Leverage, Liquidity and Source of Funds (Long term debt, Current ratio, Shares outstanding)
    3. Operating Efficiency (Gross margin, Asset turnover)
    """
    score = 0
    
    # Profitability
    if net_income_current > 0:
        score += 1
    if operating_cash_flow_current > 0:
        score += 1
    if roa_current > roa_previous:
        score += 1
    if operating_cash_flow_current > net_income_current:
        score += 1
        
    # Leverage, Liquidity, and Source of Funds
    if long_term_debt_current < long_term_debt_previous:
        score += 1
    if current_ratio_current > current_ratio_previous:
        score += 1
    if shares_outstanding_current <= shares_outstanding_previous:
        score += 1
        
    # Operating Efficiency
    if gross_margin_current > gross_margin_previous:
        score += 1
    if asset_turnover_current > asset_turnover_previous:
        score += 1
        
    return score
