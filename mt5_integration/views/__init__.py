from .connection_views import *
from .data_views import *
from .trade_views import *
from .asian_range_views import *
from .utility_views import *
from .signal_views import *
from .auto_trading_views import *

__all__ = [
    # Connection views
    'connect_mt5',
    'disconnect_mt5',
    'get_connection_status',
    'get_account_info',
    'connection_dashboard',
    
    # Data views
    'get_symbols',
    'get_rates',
    'get_current_price',
    'get_open_orders',
    
    # Trade views
    'place_trade',
    'get_positions',
    'close_position',
    'close_all_positions',
    
    # Asian range views
    'get_asian_range',
    'test_asian_range',
    
    # Signal detection views
    'initialize_session',
    'detect_sweep',
    'confirm_reversal',
    'generate_signal',
    'check_confluence',
    'get_session_status',
    'run_full_analysis',
    'run_strategy_once',
    
    # Auto trading views
    'start_auto_trading',
    'stop_auto_trading',
    'get_auto_trading_status',
    'reset_daily_counters',
    'update_trading_parameters',
    
    # Utility views
    'get_server_time',
    'get_symbol_info',
    'get_mt5_version',
]