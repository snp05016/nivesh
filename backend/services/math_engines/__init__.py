"""Math engines package — uniform inference protocol."""
from services.math_engines.protocol import InferenceEngine, EngineRegistry

# Import and register concrete engines
from services.math_engines.conformal_prediction import ConformalPredictionEngine
from services.math_engines.minsky_risk import MinskyRiskEngine
from services.math_engines.dtw_pattern_matching import DTWPatternEngine

# Statistical calibration engines (Tier A)
from services.math_engines.calibration_metrics import CalibrationMetricsEngine
from services.math_engines.venn_abers import VennAbersEngine
from services.math_engines.information_coefficient import InformationCoefficientEngine

# Deterministic modifier engines (Tier B)
from services.math_engines.currency_commodity import CurrencyCommodityEngine
from services.math_engines.monte_carlo_bootstrap import MonteCarloBootstrapEngine
from services.math_engines.signal_agreement_engine import SignalAgreementEngine

# Auto-register engines
EngineRegistry.register(ConformalPredictionEngine)
EngineRegistry.register(MinskyRiskEngine)
EngineRegistry.register(DTWPatternEngine)

# Calibration engines
EngineRegistry.register(CalibrationMetricsEngine)
EngineRegistry.register(VennAbersEngine)
EngineRegistry.register(InformationCoefficientEngine)

# Modifier engines
EngineRegistry.register(CurrencyCommodityEngine)
EngineRegistry.register(MonteCarloBootstrapEngine)
EngineRegistry.register(SignalAgreementEngine)
