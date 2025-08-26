from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..services.auto_trading_service import AutoTradingService
from ..services.gpt_service import GPTService
from ..services import mt5_service, signal_detection_service  # Import shared instances
import logging

# Configure logging
logger = logging.getLogger('api_requests')

# Initialize GPT service and auto trading service
gpt_service = GPTService()
auto_trading_service = AutoTradingService(mt5_service, signal_detection_service)

@api_view(['POST'])
def start_auto_trading(request):
    """Start the automated trading service"""
    logger.info("Auto Trading Start API called")
    
    # Log MT5 connection status
    logger.info(f"MT5 connection status: {'Connected' if mt5_service.connected else 'Not connected'}")
    
    if not mt5_service.connected:
        logger.warning("Auto Trading Start failed: Not connected to MT5")
        return Response({
            'status': 'error',
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', 'XAUUSD')
    logger.info(f"Starting auto trading for symbol: {symbol}")
    
    # Start the auto trading service
    result = auto_trading_service.start(symbol)
    
    if result:
        logger.info(f"Auto trading started successfully for {symbol}")
        return Response({
            'status': 'success',
            'message': f'Automated trading started for {symbol}',
            'data': auto_trading_service.status()
        })
    else:
        logger.warning(f"Failed to start auto trading for {symbol}")
        return Response({
            'status': 'error',
            'message': 'Failed to start automated trading',
            'data': auto_trading_service.status()
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def stop_auto_trading(request):
    """Stop the automated trading service"""
    result = auto_trading_service.stop()
    
    if result:
        return Response({
            'status': 'success',
            'message': 'Automated trading stopped',
            'data': auto_trading_service.status()
        })
    else:
        return Response({
            'status': 'error',
            'message': 'Failed to stop automated trading',
            'data': auto_trading_service.status()
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_auto_trading_status(request):
    """Get the current status of the automated trading service"""
    logger.info("Auto Trading Status API called")
    
    status_data = auto_trading_service.status()
    logger.info(f"Current auto trading status: {status_data}")
    
    # Check if we're in Asian session
    is_asian = auto_trading_service._is_asian_session() if hasattr(auto_trading_service, '_is_asian_session') else False
    logger.info(f"Current time is {'within' if is_asian else 'outside'} Asian session hours")
    
    return Response({
        'status': 'success',
        'data': status_data,
        'is_asian_session': is_asian
    })

@api_view(['POST'])
def reset_daily_counters(request):
    """Reset the daily trade and loss counters"""
    auto_trading_service.reset_daily_counters()
    
    return Response({
        'status': 'success',
        'message': 'Daily counters reset',
        'data': auto_trading_service.status()
    })

@api_view(['POST'])
def update_trading_parameters(request):
    """Update trading parameters like max daily trades, max daily losses, etc."""
    try:
        # Get parameters from request
        max_daily_trades = request.data.get('max_daily_trades')
        max_daily_losses = request.data.get('max_daily_losses')
        
        # Update parameters if provided
        if max_daily_trades is not None:
            auto_trading_service.max_daily_trades = int(max_daily_trades)
        
        if max_daily_losses is not None:
            auto_trading_service.max_daily_losses = int(max_daily_losses)
        
        return Response({
            'status': 'success',
            'message': 'Trading parameters updated',
            'data': auto_trading_service.status()
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Failed to update parameters: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)