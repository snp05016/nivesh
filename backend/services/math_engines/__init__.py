"""Math engines package — uniform inference protocol."""
from services.math_engines.protocol import InferenceEngine, EngineRegistry

# Import and register concrete engines
from services.math_engines.conformal_prediction import ConformalPredictionEngine
from services.math_engines.minsky_risk import MinskyRiskEngine
from services.math_engines.dtw_pattern_matching import DTWPatternEngine

# Auto-register engines
EngineRegistry.register(ConformalPredictionEngine)
EngineRegistry.register(MinskyRiskEngine)
EngineRegistry.register(DTWPatternEngine)
