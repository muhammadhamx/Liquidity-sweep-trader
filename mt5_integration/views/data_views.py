from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from ..services import mt5_service  # Import shared instance
from ..serializers import SymbolSerializer, TimeframeSerializer

@api_view(['GET'])
def get_symbols(request):
    """Get all available symbols"""
    if not mt5_service.connected:
        return Response({'status': 'error', 'message': 'Not connected to MT5'}, 
                      status=status.HTTP_400_BAD_REQUEST)
    
    symbols = mt5_service.get_symbols()
    return Response({'status': 'success', 'data': symbols})

@api_view(['POST'])
def get_rates(request):
    """Get historical rates for a symbol"""
    if not mt5_service.connected:
        return Response({'status': 'error', 'message': 'Not connected to MT5'}, 
                      status=status.HTTP_400_BAD_REQUEST)
    
    serializer = TimeframeSerializer(data=request.data)
    if serializer.is_valid():
        symbol = serializer.validated_data['symbol']
        timeframe = serializer.validated_data['timeframe']
        count = serializer.validated_data['count']
        
        rates = mt5_service.get_rates(symbol, timeframe, count)
        
        if rates:
            return Response({'status': 'success', 'data': rates})
        else:
            return Response({'status': 'error', 'message': 'Failed to get rates'}, 
                          status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def get_current_price(request):
    """Get current price for a symbol"""
    if not mt5_service.connected:
        return Response({'status': 'error', 'message': 'Not connected to MT5'}, 
                      status=status.HTTP_400_BAD_REQUEST)
    
    serializer = SymbolSerializer(data=request.data)
    if serializer.is_valid():
        symbol = serializer.validated_data['symbol']
        price = mt5_service.get_current_price(symbol)
        
        if price:
            return Response({'status': 'success', 'data': price})
        else:
            return Response({'status': 'error', 'message': 'Failed to get price'}, 
                          status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_open_orders(request):
    """Get all open orders"""
    if not mt5_service.connected:
        return Response({'status': 'error', 'message': 'Not connected to MT5'}, 
                      status=status.HTTP_400_BAD_REQUEST)
    
    orders = mt5_service.get_open_orders()
    return Response({'status': 'success', 'data': orders})