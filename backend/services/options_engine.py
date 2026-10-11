"""
Options Payoff Engine — calculates multi-leg option strategy P&L curves.

AGENTS.md §3.2: All business logic lives in services/. No DB queries here.
AGENTS.md §5.1: Indian numbering system (Lakhs/Crores) for all currency output.
"""

from typing import List, Tuple, Dict, Optional
import math
from helpers import format_indian_currency

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NUM_PRICE_POINTS = 100           # resolution of payoff curve
PRICE_RANGE_PCT = 0.20           # ±20% around spot


# ---------------------------------------------------------------------------
# Single-leg payoff
# ---------------------------------------------------------------------------

def _leg_payoff(leg: dict, underlying: float) -> float:
    """
    Compute P&L for a single option leg at a given underlying price.

    Args:
        leg: {"type": "CALL"|"PUT", "position": "LONG"|"SHORT", "strike": float, "premium": float,
              "quantity": float (optional, total units = lots x lot size; default 1 = per share)}
        underlying: current underlying asset price

    Returns:
        P&L in INR for the leg's quantity (negative = loss)
    """
    opt_type = leg["type"].upper()
    position = leg["position"].upper()
    strike = float(leg["strike"])
    premium = float(leg["premium"])
    qty = float(leg.get("quantity", 1.0))

    if opt_type == "CALL":
        payoff = max(0.0, underlying - strike)
    elif opt_type == "PUT":
        payoff = max(0.0, strike - underlying)
    else:
        raise ValueError(f"Invalid option type: {opt_type}. Must be CALL or PUT.")

    if position == "LONG":
        return (payoff - premium) * qty
    elif position == "SHORT":
        return (premium - payoff) * qty
    else:
        raise ValueError(f"Invalid position: {position}. Must be LONG or SHORT.")


# ---------------------------------------------------------------------------
# Payoff vector generator
# ---------------------------------------------------------------------------

def compute_payoff_vector(
    spot_price: float,
    legs: List[dict],
    num_points: int = NUM_PRICE_POINTS,
    range_pct: float = PRICE_RANGE_PCT,
) -> List[dict]:
    """
    Generate the P&L payoff curve for a multi-leg options strategy.

    Args:
        spot_price: current underlying price
        legs: list of leg dicts, each with type, position, strike, premium
        num_points: number of price points in the curve
        range_pct: price range as a fraction of spot (±range_pct)

    Returns:
        List of {"underlying_price": float, "pnl": float} dicts
    """
    if not legs:
        return []

    price_min = spot_price * (1.0 - range_pct)
    price_max = spot_price * (1.0 + range_pct)
    step = (price_max - price_min) / (num_points - 1) if num_points > 1 else 1.0

    payoff_vector = []
    for i in range(num_points):
        price = price_min + step * i
        total_pnl = sum(_leg_payoff(leg, price) for leg in legs)
        payoff_vector.append({
            "underlying_price": round(price, 2),
            "pnl": round(total_pnl, 4),
        })

    return payoff_vector


# ---------------------------------------------------------------------------
# Breakeven finder
# ---------------------------------------------------------------------------

def _exact_breakevens(candidates: List[float], vals: List[float], up_slope: float) -> List[float]:
    """Zero crossings of the piecewise-linear P&L given its values at S=0 and each strike."""
    breakevens = []
    for s1, s2, v1, v2 in zip(candidates, candidates[1:], vals, vals[1:]):
        if v1 * v2 <= 0 and not (v1 == 0 and v2 == 0):
            breakevens.append(round(s1 + (s2 - s1) * v1 / (v1 - v2), 2))
    # Ray beyond the top strike: v + up_slope * (S - K) = 0
    k, v = candidates[-1], vals[-1]
    if up_slope != 0 and v * up_slope < 0:
        breakevens.append(round(k - v / up_slope, 2))
    return sorted(set(breakevens))


# ---------------------------------------------------------------------------
# Unified compute — returns complete result dict
# ---------------------------------------------------------------------------

def compute_options_payoff(
    spot_price: float,
    legs: List[dict],
) -> dict:
    """
    Compute the complete payoff analysis for a multi-leg options strategy.

    AGENTS.md §5.1: All monetary output uses IndianFormatted strings.

    Returns:
        {
            "spot_price": float,
            "payoff_vector": [{underlying_price, pnl}, ...],
            "max_profit": float | None (None when unlimited),
            "max_loss": float | None (None when unlimited),
            "max_profit_formatted": str,
            "max_loss_formatted": str,
            "breakevens": [float, ...],
            "net_premium": float,
            "net_premium_formatted": str,
            "strategy_type": str,
            "pnl_basis": "per_share" | "position",
        }
    """
    if not legs:
        raise ValueError("At least one leg is required.")

    if spot_price <= 0:
        raise ValueError("Spot price must be positive.")

    # Validate legs
    for i, leg in enumerate(legs):
        if "type" not in leg or "position" not in leg or "strike" not in leg:
            raise ValueError(f"Leg {i} missing required fields: type, position, strike.")
        if leg["type"].upper() not in ("CALL", "PUT"):
            raise ValueError(f"Leg {i}: type must be CALL or PUT, got {leg.get('type')}.")
        if leg["position"].upper() not in ("LONG", "SHORT"):
            raise ValueError(f"Leg {i}: position must be LONG or SHORT, got {leg.get('position')}.")
        if float(leg.get("strike", 0)) <= 0:
            raise ValueError(f"Leg {i}: strike price must be positive.")
        leg.setdefault("premium", 0.0)  # premium defaults to 0 if not provided
        qty = float(leg.setdefault("quantity", 1.0))  # default 1 = per-share P&L
        if not (math.isfinite(qty) and qty > 0):
            raise ValueError(f"Leg {i}: quantity must be a positive number.")

    # Compute payoff vector
    payoff_vector = compute_payoff_vector(spot_price, legs)

    # Net premium (premium received minus premium paid), scaled by quantity
    net_premium = 0.0
    for leg in legs:
        premium = float(leg["premium"]) * float(leg["quantity"])
        if leg["position"].upper() == "SHORT":
            net_premium += premium
        else:
            net_premium -= premium
    net_premium = round(net_premium, 4)

    # Only calls can be unbounded: as price -> infinity the P&L slope is
    # (long call qty - short call qty). Put payoffs are capped at S = 0.
    up_slope = round(sum(
        float(l["quantity"]) * (1 if l["position"].upper() == "LONG" else -1)
        for l in legs if l["type"].upper() == "CALL"
    ), 6)
    unlimited_profit = up_slope > 0
    unlimited_loss = up_slope < 0

    # P&L is piecewise linear with kinks only at strikes, so its finite extremes
    # lie at S = 0 or at a strike (beyond the top strike the slope is up_slope).
    candidates = [0.0] + sorted({float(l["strike"]) for l in legs})
    vals = [sum(_leg_payoff(l, s) for l in legs) for s in candidates]
    max_profit_val = round(max(vals), 4)
    max_loss_val = round(min(vals), 4)

    max_profit = max_profit_val if not unlimited_profit else "Unlimited"
    max_loss = max_loss_val if not unlimited_loss else "Unlimited"

    # If max_profit/max_loss is a float and close to zero, handle
    max_profit_formatted = "Unlimited" if isinstance(max_profit, str) else format_indian_currency(float(max_profit))
    max_loss_formatted = "Unlimited" if isinstance(max_loss, str) else format_indian_currency(float(max_loss))

    # Exact breakevens (not limited to the ±20% chart window)
    breakevens = _exact_breakevens(candidates, vals, up_slope)

    # Determine strategy type heuristically
    num_legs = len(legs)
    strategy_type = _classify_strategy(legs)

    return {
        "spot_price": round(spot_price, 2),
        "payoff_vector": payoff_vector,
        "max_profit": max_profit if not isinstance(max_profit, str) else None,
        "max_profit_unlimited": isinstance(max_profit, str),
        "max_profit_formatted": max_profit_formatted,
        "max_loss": max_loss if not isinstance(max_loss, str) else None,
        "max_loss_unlimited": isinstance(max_loss, str),
        "max_loss_formatted": max_loss_formatted,
        "breakevens": breakevens,
        "net_premium": net_premium,
        "net_premium_formatted": format_indian_currency(net_premium),
        "num_legs": num_legs,
        "strategy_type": strategy_type,
        "pnl_basis": "per_share" if all(float(l["quantity"]) == 1.0 for l in legs) else "position",
    }


# ---------------------------------------------------------------------------
# Strategy classification heuristic
# ---------------------------------------------------------------------------

def _classify_strategy(legs: List[dict]) -> str:
    """Classify the option strategy based on leg composition."""
    num_legs = len(legs)

    if num_legs == 1:
        leg = legs[0]
        t, p = leg["type"].upper(), leg["position"].upper()
        if t == "CALL" and p == "LONG":
            return "Long Call"
        if t == "CALL" and p == "SHORT":
            return "Short Call (Naked)"
        if t == "PUT" and p == "LONG":
            return "Long Put"
        if t == "PUT" and p == "SHORT":
            return "Short Put (Naked)"

    if num_legs == 2:
        sorted_legs = sorted(legs, key=lambda l: float(l["strike"]))
        l1, l2 = sorted_legs[0], sorted_legs[1]

        t1, p1, k1 = l1["type"].upper(), l1["position"].upper(), float(l1["strike"])
        t2, p2, k2 = l2["type"].upper(), l2["position"].upper(), float(l2["strike"])

        # Covered Call: long stock equivalent + short call (simulated as call spread)
        if t1 == "CALL" and p1 == "LONG" and t2 == "CALL" and p2 == "SHORT":
            return "Bull Call Spread" if k1 < k2 else "Bear Call Spread"
        if t1 == "CALL" and p1 == "SHORT" and t2 == "CALL" and p2 == "LONG":
            return "Bear Call Spread" if k1 < k2 else "Bull Call Spread"
        if t1 == "PUT" and p1 == "LONG" and t2 == "PUT" and p2 == "SHORT":
            return "Bear Put Spread" if k1 < k2 else "Bull Put Spread"
        if t1 == "PUT" and p1 == "SHORT" and t2 == "PUT" and p2 == "LONG":
            return "Bull Put Spread" if k1 < k2 else "Bear Put Spread"

        # Straddle: same strike, one call one put
        if abs(k1 - k2) < 0.01:
            if t1 != t2:
                if p1 == "LONG" and p2 == "LONG":
                    return "Long Straddle"
                if p1 == "SHORT" and p2 == "SHORT":
                    return "Short Straddle"

        # Strangle: different strikes
        if t1 != t2:
            if p1 == "LONG" and p2 == "LONG":
                return "Long Strangle"
            if p1 == "SHORT" and p2 == "SHORT":
                return "Short Strangle"

    if num_legs == 4:
        # Likely Iron Condor or Iron Butterfly
        sorted_legs = sorted(legs, key=lambda l: float(l["strike"]))
        ts = [l["type"].upper() for l in sorted_legs]
        ps = [l["position"].upper() for l in sorted_legs]
        ks = [float(l["strike"]) for l in sorted_legs]

        if len(set(ks)) <= 4:
            # Check for Iron Condor: OTM put spread + OTM call spread, all short
            puts = [l for l in sorted_legs if l["type"].upper() == "PUT"]
            calls = [l for l in sorted_legs if l["type"].upper() == "CALL"]
            if len(puts) == 2 and len(calls) == 2:
                put_positions = [l["position"].upper() for l in puts]
                call_positions = [l["position"].upper() for l in calls]
                if "SHORT" in put_positions and "LONG" in put_positions:
                    if "SHORT" in call_positions and "LONG" in call_positions:
                        return "Iron Condor"

    return f"Custom Strategy ({num_legs} legs)"
