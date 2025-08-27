from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import MetaTrader5 as mt5
from datetime import datetime
from django.utils import timezone
from ..services import mt5_service  # Import shared instance

@api_view(['GET'])
def get_server_time(request):
    """Get MT5 server time"""
    if not mt5_service.connected:
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        server_time = mt5.symbol_info_tick("XAUUSD").time
        return Response({
            'status': 'success',
            'server_time': datetime.fromtimestamp(server_time).isoformat(),
            'local_time': timezone.now().isoformat()
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_symbol_info(request):
    """Get information about a specific symbol"""
    symbol = request.GET.get('symbol', 'XAUUSD')
    
    if not mt5_service.connected:
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        info = mt5.symbol_info(symbol)
        if info:
            return Response({
                'status': 'success',
                'data': info._asdict()
            })
        else:
            return Response({
                'status': 'error',
                'message': f'Symbol {symbol} not found'
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_mt5_version(request):
    """Get MT5 version information"""
    try:
        version_info = {
            'version': mt5.version(),
            'build': mt5.__version__,
            'author': mt5.__author__,
            'connected': mt5.initialize() if not mt5.initialize() else True
        }
        return Response({
            'status': 'success',
            'data': version_info
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)