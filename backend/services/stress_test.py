from typing import List, Dict, Any
from helpers import _yf_fetch_info, _yf_price

def get_sector(company_name: str) -> str:
    if not company_name: return 'Other'
    name = company_name.lower()
    if any(x in name for x in ['infosys', 'tcs', 'wipro', 'tech', 'software', 'hcl', 'infy']): return 'IT'
    if any(x in name for x in ['bank', 'hdfc', 'icici', 'kotak', 'sbi', 'axis']): return 'Banking'
    if any(x in name for x in ['fmcg', 'itc', 'nestle', 'brit', 'hindustan unilever', 'hul', 'godrej', 'marico']): return 'FMCG'
    if any(x in name for x in ['auto', 'tata motors', 'maruti', 'mahindra', 'bajaj auto', 'eicher']): return 'Auto'
    if any(x in name for x in ['pharma', 'sun', 'cipla', 'dr reddy', 'lupin', 'divis', 'apolo']): return 'Pharma'
    if any(x in name for x in ['oil', 'reliance', 'ongc', 'bpcl', 'hpcl', 'ioc']): return 'Oil'
    if any(x in name for x in ['aviation', 'indigo', 'spicejet']): return 'Aviation'
    if any(x in name for x in ['nbfc', 'bajaj finance', 'cholamandalam', 'shriram', 'muthoot']): return 'NBFC'
    if any(x in name for x in ['infra', 'larsen', 'l&t', 'gmr', 'irb']): return 'Infra'
    if any(x in name for x in ['psu', 'power grid', 'ntpc', 'coal india', 'sail', 'bhel']): return 'PSU'
    if any(x in name for x in ['defence', 'hal', 'bel', 'mazagon', 'cochin']): return 'Defence'
    return 'Other'

SCENARIOS_DEF = {
    "nifty_crash": {
        "name": "NIFTY_CRASH",
        "nifty_shock": -20.0,
        "sectors": {}
    },
    "oil_shock": {
        "name": "OIL_SHOCK",
        "nifty_shock": -5.0,
        "sectors": {"Oil": -15.0, "Aviation": -25.0, "IT": 5.0}
    },
    "rate_hike": {
        "name": "RATE_HIKE",
        "nifty_shock": -5.0,
        "sectors": {"NBFC": -20.0, "Banking": -5.0, "Infra": -10.0}
    },
    "fii_exodus": {
        "name": "FII_EXODUS",
        "nifty_shock": -12.0,
        "sectors": {}
    },
    "global_recession": {
        "name": "GLOBAL_RECESSION",
        "nifty_shock": -25.0,
        "sectors": {"IT": -15.0, "Pharma": 5.0}
    },
    "policy_shock": {
        "name": "POLICY_SHOCK",
        "nifty_shock": -18.0,
        "sectors": {"PSU": -30.0, "Defence": 10.0}
    },
    "currency_crash": {
        "name": "CURRENCY_CRASH",
        "nifty_shock": -10.0,
        "sectors": {"IT": 12.0, "Pharma": 8.0, "Auto": -5.0}
    },
    "custom": {
        "name": "CUSTOM",
        "nifty_shock": -15.0,
        "sectors": {}
    }
}

def run_stress_test(holdings, scenarios: List[str]) -> List[Dict[str, Any]]:
    # Enrich holdings with current price, beta, and sector
    enriched = []
    total_portfolio_value = 0.0
    
    for h in holdings:
        ticker = h.ticker.upper()
        if ticker in ["CASH", "INR"]:
            # Cash holding
            price = 1.0
            beta = 0.0
            sector = "Cash"
            value = h.shares
        else:
            price = _yf_price(h.ticker)
            if price == 0:
                price = h.buy_price
            info = _yf_fetch_info(h.ticker)
            beta = info.get("beta", 1.0)
            if beta is None:
                beta = 1.0
            sector = get_sector(h.company_name)
            value = h.shares * price
            
        enriched.append({
            "ticker": h.ticker,
            "company_name": h.company_name,
            "shares": h.shares,
            "price": price,
            "value": value,
            "beta": beta,
            "sector": sector
        })
        total_portfolio_value += value

    if total_portfolio_value == 0:
        return []

    results = []
    for sc_key in scenarios:
        sc_key_lower = sc_key.lower()
        if sc_key_lower not in SCENARIOS_DEF:
            continue
            
        scenario = SCENARIOS_DEF[sc_key_lower]
        nifty_shock = scenario["nifty_shock"]
        sector_shocks = scenario["sectors"]
        
        scenario_holdings = []
        total_impact_inr = 0.0
        
        for e in enriched:
            if e["sector"] == "Cash":
                impact_pct = 0.0
                impact_inr = 0.0
            else:
                base_impact = e["beta"] * nifty_shock
                sector_adj = sector_shocks.get(e["sector"], 0.0)
                impact_pct = base_impact + sector_adj
                impact_inr = e["value"] * (impact_pct / 100.0)
                
            total_impact_inr += impact_inr
            
            scenario_holdings.append({
                "ticker": e["ticker"],
                "impact_pct": impact_pct,
                "impact_inr": impact_inr
            })
            
        # Sort holdings worst to best (most negative to positive)
        scenario_holdings.sort(key=lambda x: x["impact_inr"])
            
        total_impact_pct = (total_impact_inr / total_portfolio_value) * 100.0 if total_portfolio_value > 0 else 0.0
        
        results.append({
            "name": scenario["name"],
            "impact_pct": total_impact_pct,
            "impact_inr": total_impact_inr,
            "holdings": scenario_holdings
        })
        
    return results
