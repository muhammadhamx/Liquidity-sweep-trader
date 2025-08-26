from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from ..services import mt5_service, trade_service  # Import shared instances
from ..serializers import TradeExecutionSerializer
import logging

# Configure logging
logger = logging.getLogger('api_requests')

@csrf_exempt
@api_view(['POST'])
def place_trade(request):
    """Place a market order"""
    if not mt5_service.connected:
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = TradeExecutionSerializer(data=request.data)
    
    if serializer.is_valid():
        symbol = serializer.validated_data['symbol']
        trade_type = serializer.validated_data['trade_type']
        volume = serializer.validated_data['volume']
        stop_loss = serializer.validated_data.get('stop_loss', 0)
        take_profit = serializer.validated_data.get('take_profit', 0)
        deviation = serializer.validated_data.get('deviation', 20)
        comment = serializer.validated_data.get('comment', 'API Trade')
        
        result = trade_service.place_market_order(
            symbol=symbol,
            trade_type=trade_type,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            deviation=deviation,
            comment=comment
        )
        
        if result['success']:
            return Response({
                'status': 'success',
                'message': 'Trade executed successfully',
                'data': result
            })
        else:
            return Response({
                'status': 'error',
                'message': result['error'],
                'data': result
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_positions(request):
    """Get all open positions"""
    if not mt5_service.connected:
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.GET.get('symbol', None)
    result = trade_service.get_open_positions(symbol)
    
    if result['success']:
        return Response({
            'status': 'success',
            'data': result
        })
    else:
        return Response({
            'status': 'error',
            'message': result['error'],
            'data': result
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def close_position(request, position_id):
    """Close a specific position"""
    if not mt5_service.connected:
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    deviation = request.data.get('deviation', 20)
    result = trade_service.close_position(position_id, deviation)
    
    if result['success']:
        return Response({
            'status': 'success',
            'message': 'Position closed successfully',
            'data': result
        })
    else:
        return Response({
            'status': 'error',
            'message': result['error'],
            'data': result
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def close_all_positions(request):
    """Close all open positions"""
    if not mt5_service.connected:
        return Response({
            'status': 'error', 
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', None)
    positions_result = trade_service.get_open_positions(symbol)
    
    if not positions_result['success']:
        return Response({
            'status': 'error',
            'message': positions_result['error'],
            'data': positions_result
        }, status=status.HTTP_400_BAD_REQUEST)
    
    closed_positions = []
    errors = []
    
    for position in positions_result['positions']:
        result = trade_service.close_position(position['ticket'])
        if result['success']:
            closed_positions.append({
                'ticket': position['ticket'],
                'symbol': position['symbol'],
                'result': result
            })
        else:
            errors.append({
                'ticket': position['ticket'],
                'symbol': position['symbol'],
                'error': result['error']
            })
    
    return Response({
        'status': 'success',
        'message': f"Closed {len(closed_positions)} positions, {len(errors)} errors",
        'data': {
            'closed_positions': closed_positions,
            'errors': errors
        }
    })