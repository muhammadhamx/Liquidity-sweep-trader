from .mt5_service import MT5Service
from .trade_service import TradeService
from .asian_range_service import AsianRangeService
from .signal_detection_service import SignalDetectionService

# Create shared instances
mt5_service = MT5Service()
trade_service = TradeService(mt5_service)
asian_range_service = AsianRangeService(mt5_service)
signal_detection_service = SignalDetectionService(mt5_service)

__all__ = [
    'mt5_service',
    'trade_service', 
    'asian_range_service',
    'signal_detection_service',
    'MT5Service',
    'TradeService',
    'AsianRangeService',
    'SignalDetectionService'
]