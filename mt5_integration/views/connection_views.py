from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from ..services import mt5_service  # Import shared instance
from ..serializers import MT5ConnectionSerializer
import logging

# Configure logging
logger = logging.getLogger('api_requests')

@csrf_exempt
@api_view(['POST'])
def connect_mt5(request):
    """Connect to MT5 terminal using official method"""
    serializer = MT5ConnectionSerializer(data=request.data)
    
    if serializer.is_valid():
        account = serializer.validated_data['account']
        password = serializer.validated_data.get('password', '')
        server = serializer.validated_data.get('server', 'MetaQuotes-Demo')
        
        if password == '':
            password = None
        
        success, error = mt5_service.connect(account, password, server)
        
        if success:
            return Response({
                'status': 'success', 
                'message': 'MT5 connected successfully',
                'account': account
            })
        else:
            # error can be tuple like (code, message) per MetaTrader5 API
            code = None
            desc = None
            if isinstance(error, tuple) and len(error) >= 1:
                code = error[0]
                desc = error[1] if len(error) > 1 else None
            else:
                code = error
            error_description = desc or mt5_service.get_error_description(code)
            return Response({
                'status': 'error', 
                'message': 'Failed to connect to MT5',
                'error_code': code,
                'error_description': error_description
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def disconnect_mt5(request):
    """Disconnect from MT5 terminal"""
    mt5_service.disconnect()
    return Response({'status': 'success', 'message': 'MT5 disconnected successfully'})

@api_view(['GET'])
def get_account_info(request):
    """Get account information"""
    logger.info("Account Info API called")
    
    if not mt5_service.connected:
        logger.warning("Account Info API failed: Not connected to MT5")
        return Response({'status': 'error', 'message': 'Not connected to MT5'}, 
                      status=status.HTTP_400_BAD_REQUEST)
    
    account_info = mt5_service.get_account_info()
    logger.info(f"Account info retrieved: {account_info}")
    return Response({'status': 'success', 'data': account_info})