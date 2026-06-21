"""
Signal agreement engine — InferenceEngine wrapper around the existing
signal_agreement.py 4-vector cosine agreement function.

Delegates to services.math_engines.signal_agreement.compute_signal_agreement()
and exposes its output through the EngineRegistry protocol.
"""
from __future__ import annotations
from typing import Any

from services.math_engines.protocol import InferenceEngine


class SignalAgreementEngine(InferenceEngine):

    @classmethod
    def name(cls) -> str:
        return "signal_agreement"

    @classmethod
    def tags(cls) -> set[str]:
        return {"confidence_modifier", "quantitative"}

    def compute(self, ticker: str, data: dict, session: Any = None) -> dict:
        """Run 4-vector signal agreement.

        data keys:
          - technical_signal (float, default 0.0): -1 to +1
          - fundamental_signal (float, default 0.0): -1 to +1
          - sentiment_signal (float, default 0.0): -1 to +1
          - macro_signal (float, default 0.0): -1 to +1
          - weights (dict, optional): custom weights
        """
        from services.math_engines.signal_agreement import compute_signal_agreement

        try:
            result = compute_signal_agreement(
                technical_signal=float(data.get("technical_signal", 0.0)),
                fundamental_signal=float(data.get("fundamental_signal", 0.0)),
                sentiment_signal=float(data.get("sentiment_signal", 0.0)),
                macro_signal=float(data.get("macro_signal", 0.0)),
                weights=data.get("weights"),
            )
            return {"status": "ok", "output": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
