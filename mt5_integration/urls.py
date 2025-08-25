from django.urls import path
from .views import (
    connect_mt5, disconnect_mt5, get_account_info,
    get_symbols, get_rates, get_current_price, get_open_orders,
    place_trade, get_positions, close_position, close_all_positions,
    get_asian_range, test_asian_range,
    get_server_time, get_symbol_info, get_mt5_version,
    # Signal detection views
    initialize_session, detect_sweep, confirm_reversal, generate_signal,
    check_confluence, get_session_status, run_full_analysis
    , run_strategy_once
)

urlpatterns = [
    # Connection endpoints
    path('connect/', connect_mt5, name='connect-mt5'),
    path('disconnect/', disconnect_mt5, name='disconnect-mt5'),
    path('account-info/', get_account_info, name='account-info'),
    
    # Data endpoints
    path('symbols/', get_symbols, name='symbols'),
    path('rates/', get_rates, name='rates'),
    path('current-price/', get_current_price, name='current-price'),
    path('open-orders/', get_open_orders, name='open-orders'),
    
    # Trade endpoints
    path('place-trade/', place_trade, name='place-trade'),
    path('positions/', get_positions, name='get-positions'),
    path('close-position/<int:position_id>/', close_position, name='close-position'),
    path('close-all-positions/', close_all_positions, name='close-all-positions'),
    
    # Asian range endpoints
    path('asian-range/', get_asian_range, name='asian-range'),
    path('test-asian-range/', test_asian_range, name='test-asian-range'),
    
    # Signal detection endpoints
    path('signal/initialize-session/', initialize_session, name='initialize-session'),
    path('signal/detect-sweep/', detect_sweep, name='detect-sweep'),
    path('signal/confirm-reversal/', confirm_reversal, name='confirm-reversal'),
    path('signal/generate-signal/', generate_signal, name='generate-signal'),
    path('signal/check-confluence/', check_confluence, name='check-confluence'),
    path('signal/session-status/', get_session_status, name='session-status'),
    path('signal/run-analysis/', run_full_analysis, name='run-analysis'),
    path('signal/run-once/', run_strategy_once, name='run-strategy-once'),
    
    # Utility endpoints
    path('server-time/', get_server_time, name='server-time'),
    path('symbol-info/', get_symbol_info, name='symbol-info'),
    path('version/', get_mt5_version, name='mt5-version'),
]