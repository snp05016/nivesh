"""Liquidity risk engine — Almgren-Chriss Square-Root Law (§7.2)."""
from __future__ import annotations
import numpy as np
from typing import Any, List, Dict, Optional
from pydantic import BaseModel

class SquareRootImpactResponse(BaseModel):
    impact_pct: float
    mkt_impact_pct: float
    spread_pct: float
    participation_rate: float
    effective_volume: int

class HoldingLiquidityLoss(BaseModel):
    ticker: str
    value: float
    impact_pct: float
    loss_inr: float
    participation_rate: float

class PortfolioLiquidityLossResponse(BaseModel):
    total_liquidity_loss_inr: float
    total_liquidity_loss_pct: float
    total_portfolio_value: float
    holdings: List[HoldingLiquidityLoss]
    volume_suppression: float

def square_root_impact(
    shares_held: float,
    avg_daily_volume: float,
    daily_volatility: float,
    base_spread_bps: float = 0.001,
    gamma: float = 0.2,
    volume_suppression: float = 1.0,
) -> SquareRootImpactResponse:
    """Almgren-Chriss square-root law for liquidation impact.
    
    ΔP = base_spread + γ * σ * sqrt(Q / V)
    
    Args:
        shares_held: quantity to liquidate (Q)
        avg_daily_volume: average daily volume (V)
        daily_volatility: daily return standard deviation (σ)
        base_spread_bps: base bid-ask spread fraction (e.g., 0.001 = 10 bps)
        gamma: universal market impact constant (0.1-0.3 for equities)
        volume_suppression: crisis modifier (0.4 = 60% volume drop)
    
    Returns:
        dict with impact_pct, total_cost_pct, effective_volume
    """
    effective_volume = avg_daily_volume * volume_suppression
    if effective_volume <= 0:
        effective_volume = 1e6  # fallback
    
    participation_rate = shares_held / effective_volume
    impact = gamma * daily_volatility * np.sqrt(participation_rate)
    total_impact_pct = base_spread_bps + float(impact)
    
    return SquareRootImpactResponse(
        impact_pct=round(total_impact_pct * 100, 4),
        mkt_impact_pct=round(float(impact) * 100, 4),
        spread_pct=round(base_spread_bps * 100, 4),
        participation_rate=round(float(participation_rate), 6),
        effective_volume=int(effective_volume),
    )

def portfolio_liquidity_loss(
    holdings: list[dict[str, Any]],
    volume_suppression: float = 0.4,
    gamma: float = 0.2,
) -> PortfolioLiquidityLossResponse:
    """Aggregate liquidity penalty across portfolio.
    
    Each holding dict must have: shares, price, avg_daily_volume, volatility, spread_bps
    
    Returns dict with total_liquidity_loss_inr, total_liquidity_loss_pct,
    and per-holding breakdown.
    """
    total_loss_inr = 0.0
    total_value = 0.0
    per_holding = []
    
    for h in holdings:
        shares = float(h.get("shares", 0))
        price = float(h.get("price", 0))
        value = shares * price
        total_value += value
        
        adv = float(h.get("avg_daily_volume", 1e6))
        vol = float(h.get("volatility", 0.02))
        spread = float(h.get("spread_bps", 0.001))
        
        result = square_root_impact(
            shares_held=shares,
            avg_daily_volume=adv,
            daily_volatility=vol,
            base_spread_bps=spread,
            gamma=gamma,
            volume_suppression=volume_suppression,
        )
        
        loss_inr = value * (result.impact_pct / 100)
        total_loss_inr += loss_inr
        
        per_holding.append(HoldingLiquidityLoss(
            ticker=h.get("ticker", ""),
            value=round(value, 2),
            impact_pct=result.impact_pct,
            loss_inr=round(loss_inr, 2),
            participation_rate=result.participation_rate,
        ))
    
    return PortfolioLiquidityLossResponse(
        total_liquidity_loss_inr=round(total_loss_inr, 2),
        total_liquidity_loss_pct=round((total_loss_inr / total_value * 100), 4) if total_value > 0 else 0.0,
        total_portfolio_value=round(total_value, 2),
        holdings=per_holding,
        volume_suppression=volume_suppression,
    )

def liquidity_score(total_impact_pct: float) -> float:
    """Map total liquidity impact % to a 0-100 score.
    Lower impact → higher score (better liquidity).
    """
    return max(0.0, min(100.0, 100.0 - total_impact_pct * 20))
