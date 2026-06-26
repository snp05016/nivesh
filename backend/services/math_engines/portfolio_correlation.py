import logging
"""
Portfolio Correlation Matrix and Optimization.

Provides deterministic Pearson correlation and mean-variance optimization, replacing qualitative AI diversification advice with reproducible math (Task 29).
"""
import numpy as np

def compute_returns(prices: dict[str, list[float]]) -> dict[str, list[float]]:
    """Convert a dictionary of prices to daily percentage returns.
    
    Args:
        prices: A dictionary mapping ticker symbols to lists of historical prices.
        
    Returns:
        A dictionary mapping ticker symbols to lists of daily percentage returns.
    """
    result = {}
    for ticker, p in prices.items():
        if len(p) < 2:
            result[ticker] = []
            continue
        result[ticker] = [(p[i] - p[i - 1]) / p[i - 1] for i in range(1, len(p))]
    return result

def compute_correlation_matrix(prices: dict[str, list[float]]) -> dict:
    """Compute Pearson correlation matrix for portfolio holdings.

    Calculates the pairwise Pearson correlation coefficients between the daily returns 
    of all valid tickers in the provided prices dictionary.

    Args:
        prices: A dictionary mapping ticker symbols to lists of historical prices.

    Returns:
        A dictionary containing the correlation 'matrix', a 'diversification_score', 
        the 'average_abs_correlation', a list of 'pairs' correlations, and 'advice'.
    """
    returns = compute_returns(prices)
    tickers = [t for t, r in returns.items() if len(r) > 5]
    if len(tickers) < 2:
        return {"matrix": {}, "diversification_score": 1.0, "pairs": []}

    n = len(tickers)
    matrix = {}
    corr_sum = 0.0
    pair_count = 0
    pairs = []

    for i in range(n):
        for j in range(i + 1, n):
            t1, t2 = tickers[i], tickers[j]
            min_len = min(len(returns[t1]), len(returns[t2]))
            if min_len < 5:
                continue
            r1, r2 = returns[t1][-min_len:], returns[t2][-min_len:]
            corr = float(np.corrcoef(r1, r2)[0, 1])
            corr = max(-1.0, min(1.0, corr if not np.isnan(corr) else 0))
            matrix.setdefault(t1, {})[t2] = corr
            matrix.setdefault(t2, {})[t1] = corr
            corr_sum += abs(corr)
            pair_count += 1
            pairs.append({"ticker1": t1, "ticker2": t2, "correlation": round(corr, 4)})

    avg_corr = corr_sum / pair_count if pair_count else 0
    diversification = round(1.0 - avg_corr, 4)

    return {
        "matrix": matrix,
        "diversification_score": diversification,
        "average_abs_correlation": round(avg_corr, 4),
        "pairs": pairs,
        "advice": _diversification_advice(diversification),
    }

def optimize_portfolio_weights(
    prices: dict[str, list[float]], risk_aversion: float = 1.0
) -> dict:
    """Calculate optimal portfolio weights using mean-variance optimization.

    Uses scipy's SLSQP minimization to find the weights that maximize the Sharpe ratio 
    (or a similar objective depending on risk aversion) for the portfolio.

    Args:
        prices: A dictionary mapping ticker symbols to lists of historical prices.
        risk_aversion: A float representing the investor's risk aversion coefficient.

    Returns:
        A dictionary containing the optimal 'weights', 'expected_annual_return', 
        'expected_annual_volatility', and 'sharpe_ratio'.
    """
    returns = compute_returns(prices)
    tickers = [t for t, r in returns.items() if len(r) > 5]
    n = len(tickers)
    if n == 0:
        return {"weights": {}, "expected_return": 0.0, "expected_volatility": 0.0}

    mean_ret = np.array([np.mean(returns[t][-63:]) * 252 for t in tickers])  # annualized
    data = np.array([returns[t][-63:] for t in tickers])
    cov = np.cov(data)

    try:
        from scipy.optimize import minimize

        # Objective function for minimization: lambda * variance - expected_return
        def objective(w):
            return 0.5 * risk_aversion * w @ cov @ w - mean_ret @ w

        # Constraints: weights sum to 1. Bounds: weights are between 0 and 1
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 1.0) for _ in range(n)]
        w0 = np.ones(n) / n
        result = minimize(objective, w0, bounds=bounds, constraints=constraints, method="SLSQP")
        if result.success:
            weights = {tickers[i]: round(result.x[i], 6) for i in range(n)}
        else:
            weights = {t: round(1 / n, 6) for t in tickers}
    except ImportError:
        weights = {t: round(1 / n, 6) for t in tickers}

    port_return = float(mean_ret @ np.array([weights[t] for t in tickers]))
    port_vol = float(np.sqrt(np.array([weights[t] for t in tickers]) @ cov @ np.array([weights[t] for t in tickers])))

    return {
        "weights": weights,
        "expected_annual_return": round(port_return, 4),
        "expected_annual_volatility": round(port_vol, 4),
        "sharpe_ratio": round(port_return / port_vol, 4) if port_vol > 0 else 0.0,
    }

def _diversification_advice(score: float) -> str:
    """Generate qualitative diversification advice based on the calculated score.

    Args:
        score: The diversification score derived from average absolute correlation.

    Returns:
        A qualitative advice string based on established score thresholds.
    """
    if score >= 0.7:
        return "Well-diversified portfolio"
    elif score >= 0.4:
        return "Moderately diversified — consider adding uncorrelated assets"
    else:
        return "Highly correlated holdings — risk concentration warning"

if __name__ == "__main__":
    test_prices = {
        "A": [100, 101, 102, 103, 104],
        "B": [200, 198, 196, 194, 192],
        "C": [50, 51, 52, 53, 54],
    }
    logging.info(compute_correlation_matrix(test_prices))
    logging.info(optimize_portfolio_weights(test_prices))
