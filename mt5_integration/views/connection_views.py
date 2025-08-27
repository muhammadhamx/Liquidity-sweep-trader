from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from ..services import mt5_service  # Import shared instance
import logging
import os

# Configure logging
logger = logging.getLogger('api_requests')

@csrf_exempt
@api_view(['POST'])
def connect_mt5(request):
    """Connect to MT5 terminal using environment credentials (automatic)"""
    # Use environment variables for connection
    login = int(os.environ.get('MT5_LOGIN', 0))
    password = os.environ.get('MT5_PASSWORD', '')
    server = os.environ.get('MT5_SERVER', 'MetaQuotes-Demo')

    if not login or not password:
        return Response({
            'status': 'error',
            'message': 'MT5 credentials not configured in environment variables'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if already connected
    if mt5_service.connected:
        return Response({
            'status': 'success',
            'message': 'MT5 already connected',
            'account': mt5_service.account or login
        })

    # Initialize and connect
    success = mt5_service.initialize_mt5()
    if not success:
        return Response({
            'status': 'error',
            'message': 'Failed to initialize MT5'
        }, status=status.HTTP_400_BAD_REQUEST)

    connected, error = mt5_service.connect(login, password, server)

    if connected:
        return Response({
            'status': 'success',
            'message': 'MT5 connected successfully',
            'account': login
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

@csrf_exempt
@api_view(['POST'])
def disconnect_mt5(request):
    """Disconnect from MT5 terminal"""
    mt5_service.disconnect()
    return Response({'status': 'success', 'message': 'MT5 disconnected successfully'})

@api_view(['GET'])
def get_connection_status(request):
    """Get current MT5 connection status"""
    logger.info("Connection Status API called")

    if mt5_service.connected:
        account_info = mt5_service.get_account_info()
        return Response({
            'status': 'success',
            'connected': True,
            'account': mt5_service.account,
            'account_info': account_info
        })
    else:
        return Response({
            'status': 'success',
            'connected': False,
            'account': None,
            'account_info': None
        })

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

def connection_dashboard(request):
    """Serve the connection dashboard HTML page"""
    return render(request, 'connection_dashboard.html')