from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from ..services import mt5_service, asian_range_service  # Import shared instances
import logging

# Configure logging
logger = logging.getLogger('api_requests')

@api_view(['GET'])
def get_asian_range(request):
    """Get Asian session range data"""
    symbol = request.GET.get('symbol', 'XAUUSD')
    
    logger.info(f"Asian Range API called for symbol: {symbol}")
    
    if not mt5_service.connected:
        logger.warning(f"Asian Range API failed: Not connected to MT5")
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    logger.info(f"Calculating Asian range for {symbol}...")
    range_data = asian_range_service.calculate_asian_range(symbol)
    
    if range_data['success']:
        logger.info(f"Asian range calculation successful: {range_data}")
        return Response({
            'status': 'success', 
            'data': range_data
        })
    else:
        logger.warning(f"Asian range calculation failed: {range_data['error']}")
        return Response({
            'status': 'error', 
            'message': range_data['error']
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def test_asian_range(request):
    """Test endpoint to see formatted Asian range output"""
    symbol = request.GET.get('symbol', 'XAUUSD')
    
    if not mt5_service.connected:
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    range_data = asian_range_service.calculate_asian_range(symbol)
    formatted_output = asian_range_service.format_range_output(range_data)
    
    return Response({
        'status': 'success' if range_data['success'] else 'error',
        'formatted_output': formatted_output,
        'data': range_data
    })