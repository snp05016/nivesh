"""Uniform inference engine protocol for all math engines."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Union
from pydantic import BaseModel

class InferenceEngine(ABC):
    """Every math engine implements this interface.
    
    Interface: compute(ticker, data, session) → Any
    - ticker: str — the stock symbol
    - data: dict — engine-specific input data (prices, fundamentals, etc.)
    - session: SQLAlchemy Session | None — optional DB access
    Returns: BaseModel or dict with at minimum {"status": "ok"|"error", "output": ...}
    """
    
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Human-readable engine name."""
        ...
    
    @classmethod
    @abstractmethod
    def tags(cls) -> set[str]:
        """Capability tags: confidence_modifier, risk_metric, valuation, technical, sentiment, etc."""
        ...
    
    @abstractmethod
    def compute(self, ticker: str, data: dict, session: Any = None) -> Any:
        """Execute the engine computation."""
        ...


class EngineRegistry:
    """Discover and filter inference engines by tag."""
    
    _engines: list[type[InferenceEngine]] = []
    
    @classmethod
    def register(cls, engine_class: type[InferenceEngine]) -> None:
        if engine_class not in cls._engines:
            cls._engines.append(engine_class)
    
    @classmethod
    def get_engines(cls, tag: str | None = None) -> list[type[InferenceEngine]]:
        if tag is None:
            return list(cls._engines)
        return [e for e in cls._engines if tag in e.tags()]
    
    @classmethod
    def run_all(cls, tag: str, ticker: str, data: dict, session: Any = None) -> list[Any]:
        """Run all engines matching a tag and return their results."""
        results = []
        for engine_cls in cls.get_engines(tag):
            try:
                result = engine_cls().compute(ticker, data, session)
                results.append({"engine": engine_cls.name(), "result": result})
            except Exception as exc:
                results.append({"engine": engine_cls.name(), "error": str(exc)})
        return results
