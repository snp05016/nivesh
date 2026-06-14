"""Test AI analysis pipeline on the server."""
import sys, os, asyncio
sys.path.insert(0, '.')
from pathlib import Path
_tg = Path('.') / 'tradingagents-core'
if _tg.exists() and str(_tg) not in sys.path:
    sys.path.insert(0, str(_tg))

errors = []

# Test 1: Quant engine
print('=== Test 1: QuantEngine ===')
try:
    from services.quant_engine import QuantitativeEngine
    qe = QuantitativeEngine('BAJFINANCE')
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(qe.run_full_pipeline())
    print(f'Quant OK: regime={result["market_regime"]}, conf={result["calibrated_confidence"]}')
except Exception as e:
    errors.append(f'QuantEngine: {e}')
    print(f'Quant FAILED: {e}')
    import traceback
    traceback.print_exc()

# Test 2: Orchestrator imports
print()
print('=== Test 2: Orchestrator imports ===')
try:
    from services.orchestrator import analyze, build_ta_config, _normalize_response
    print('Orchestrator imports OK')
except Exception as e:
    errors.append(f'Orchestrator import: {e}')
    print(f'Orchestrator import FAILED: {e}')
    import traceback
    traceback.print_exc()

# Test 3: Config building
print()
print('=== Test 3: Config building ===')
try:
    config = build_ta_config('standard')
    print(f'Standard: max_recur_limit={config.get("max_recur_limit")}, recursion_limit={config.get("recursion_limit")}')
    config_x = build_ta_config('extreme')
    print(f'Extreme: max_recur_limit={config_x.get("max_recur_limit")}, recursion_limit={config_x.get("recursion_limit")}')
except Exception as e:
    errors.append(f'Config: {e}')
    print(f'Config FAILED: {e}')

# Test 4: Test _normalize_response with quant_payload
print()
print('=== Test 4: _normalize_response with quant_payload ===')
try:
    from services.orchestrator import _normalize_response
    sample = {"signal": "HOLD", "confidence_pct": 55}
    quant = {
        "market_regime": "Transition / Macro-Driven",
        "calibrated_confidence": 0.42,
        "conformal_target_upper_3m": 8000.0,
        "conformal_target_lower_3m": 6500.0,
        "quantitative_drivers": {"Fundamental Health (F-Score)": 0.1},
        "tail_risk_flags": {"high_pledge_danger": False},
    }
    normalized = _normalize_response(sample, "standard", quant)
    print(f'Normalized confidence: {normalized.get("confidence_pct")}')
    print(f'Calibration block present: {"confidence_calibration" in normalized}')
    print(f'Target bounds present: {"target_price_bounds" in normalized}')
except Exception as e:
    errors.append(f'_normalize_response: {e}')
    print(f'Normalize FAILED: {e}')
    import traceback
    traceback.print_exc()

print()
if errors:
    print(f'{len(errors)} ERRORS FOUND:')
    for e in errors:
        print(f'  - {e}')
else:
    print('ALL TESTS PASSED')
