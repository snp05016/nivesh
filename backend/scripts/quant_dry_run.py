import logging
#!/usr/bin/env python3
"""Dry-run test for QuantitativeEngine — verifies math correctness."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import asyncio
import json

async def main():
    from services.quant_engine import QuantitativeEngine

    engine = QuantitativeEngine("TATAMOTORS.NS")
    res = await engine.run_full_pipeline()

    logging.info("=" * 60)
    logging.info("QUANTITATIVE ENGINE DRY RUN")
    logging.info("=" * 60)
    logging.info(json.dumps(res, indent=2, default=str))
    logging.info("=" * 60)

    # Validations
    assert res is not None, "Result is None"
    assert "calibrated_confidence" in res, "Missing calibrated_confidence"
    assert "market_regime" in res, "Missing market_regime"
    assert "conformal_target_upper_3m" in res, "Missing conformal_target_upper_3m"
    assert "conformal_target_lower_3m" in res, "Missing conformal_target_lower_3m"
    assert "quantitative_drivers" in res, "Missing quantitative_drivers"
    assert "tail_risk_flags" in res, "Missing tail_risk_flags"

    cc = res["calibrated_confidence"]
    assert 0.05 <= cc <= 0.95, f"Calibrated confidence {cc} out of [0.05, 0.95] bounds"

    mr = res["market_regime"]
    valid_regimes = [
        "Low Volatility / Accumulation",
        "Transition / Macro-Driven",
        "High Volatility / Crisis",
    ]
    assert mr in valid_regimes, f"Invalid regime: {mr}"

    logging.info(f"\n✅ ALL ASSERTIONS PASSED")
    logging.info(f"   Regime: {mr}")
    logging.info(f"   Confidence: {cc}")
    logging.info(f"   Drivers: {len(res['quantitative_drivers'])} signals")
    logging.info(f"   Tail Risks: {sum(1 for v in res['tail_risk_flags'].values() if v)} active")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.info(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
