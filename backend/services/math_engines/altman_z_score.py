from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class AltmanZScoreResponse(BaseModel):
    z_score: float

class AltmanZScoreInterpretationResponse(BaseModel):
    interpretation: str

def calculate_altman_z_score(
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    market_value_equity: float,
    sales: float,
    total_assets: float,
    total_liabilities: float
) -> float:
    """
    Calculates the Altman Z-Score for public manufacturing companies.
    
    Formula: Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
    A = Working Capital / Total Assets
    B = Retained Earnings / Total Assets
    C = EBIT / Total Assets
    D = Market Value of Equity / Total Liabilities
    E = Sales / Total Assets
    """
    if total_assets == 0 or total_liabilities == 0:
        raise ValueError("Total assets and total liabilities must be non-zero.")
        
    a = working_capital / total_assets
    b = retained_earnings / total_assets
    c = ebit / total_assets
    d = market_value_equity / total_liabilities
    e = sales / total_assets
    
    return AltmanZScoreResponse(z_score=1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e)

def interpret_altman_z_score(z_score: float) -> AltmanZScoreInterpretationResponse:
    """
    Interprets the Altman Z-Score.
    > 2.99: Safe Zone
    1.81 to 2.99: Grey Zone
    < 1.81: Distress Zone
    """
    if z_score > 2.99:
        return AltmanZScoreInterpretationResponse(interpretation="Safe")
    elif z_score >= 1.81:
        return AltmanZScoreInterpretationResponse(interpretation="Grey")
    else:
        return AltmanZScoreInterpretationResponse(interpretation="Distress")
