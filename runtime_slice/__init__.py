"""Minimal local-only contract slice; no external service integrations."""

from .clock import Clock, VirtualClock
from .backtest import BacktestEngine, BacktestResult, ParameterSweep
from .data_provider import HistoricalDataProvider
from .errors import (
    ContractValidationError, DecimalValidationError, IsolationViolationError,
    OrderIdentityError, ReadinessDeniedError, TimestampValidationError,
    UnknownOrderStateError,
)
from .kernel_models import AccountSnapshot, BacktestSettings, EquityPoint, OrderResponse, Position, SymbolFilters, Trade
from .protocols import AccountProvider, ConfigProvider, FilterProvider, KlineProvider, OrderTransport, PositionProvider, RecoveryStore, ResultWriter
from .lifecycle import InMemoryCandidateStore
from .models import Candidate, OrderIdentity, OrderIntent, OtoOrderIntent, RiskResult, Signal
from .order_safety import FillPolicy, OcoSafetyResult, PendingOcoStateMachine, retry_identity, safe_oco_quantity
from .recovery import InMemoryOrderRecovery, PendingOcoRecovery, ReadinessState
from .registry import PluginRegistry
from .performance import PerformanceAnalyzer, PerformanceMetrics, TradeRecord
from .risk_v1 import AccountSnapshot, BacktestRiskAdapter, LiveRiskAdapter, RiskCalculatorV1, SymbolFilters
from .strategy import BaseStrategy, DeterministicStrategy, InMemoryContextBuilder
from .step2 import Kline, Step2Decision, Step2VolumeEvaluator

__all__ = [
    "Candidate",
    "Clock",
    "OrderIdentity",
    "OrderIntent",
    "OtoOrderIntent",
    "RiskResult",
    "Signal",
    "VirtualClock",
]
