from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from ..services import mt5_service, signal_detection_service
from ..models import TradingSession, LiquiditySweep, TradeSignal

@csrf_exempt
@api_view(['POST'])
def initialize_session(request):
    """Initialize a new trading session"""
    if not mt5_service.connected:
        return Response({
            'status': 'error',
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', 'XAUUSD')
    result = signal_detection_service.initialize_session(symbol)
    
    if result['success']:
        return Response({
            'status': 'success',
            'data': result
        })
    else:
        return Response({
            'status': 'error',
            'message': result['error']
        }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def detect_sweep(request):
    """Detect Asian session liquidity sweep"""
    if not mt5_service.connected:
        return Response({
            'status': 'error',
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', 'XAUUSD')
    # Ensure session exists
    if not signal_detection_service.current_session:
        signal_detection_service.initialize_session(symbol)
    result = signal_detection_service.detect_sweep(symbol)
    
    if result['success']:
        return Response({
            'status': 'success',
            'data': result
        })
    else:
        return Response({
            'status': 'error',
            'message': result['error']
        }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def confirm_reversal(request):
    """Confirm reversal after sweep detection"""
    if not mt5_service.connected:
        return Response({
            'status': 'error',
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', 'XAUUSD')
    # Guard: must have sweep first
    if not signal_detection_service.current_session or signal_detection_service.current_session.current_state != 'SWEPT':
        return Response({'status': 'error', 'message': 'Sweep not detected yet'}, status=status.HTTP_400_BAD_REQUEST)
    result = signal_detection_service.confirm_reversal(symbol)
    
    if result['success']:
        return Response({
            'status': 'success',
            'data': result
        })
    else:
        return Response({
            'status': 'error',
            'message': result['error']
        }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def generate_signal(request):
    """Generate trade signal after confirmation"""
    if not mt5_service.connected:
        return Response({
            'status': 'error',
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', 'XAUUSD')
    # Guard: must be confirmed first
    if not signal_detection_service.current_session or signal_detection_service.current_session.current_state != 'CONFIRMED':
        return Response({'status': 'error', 'message': 'Reversal not confirmed yet'}, status=status.HTTP_400_BAD_REQUEST)
    result = signal_detection_service.generate_trade_signal(symbol)
    
    if result['success']:
        return Response({
            'status': 'success',
            'data': result
        })
    else:
        return Response({
            'status': 'error',
            'message': result['error']
        }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def check_confluence(request):
    """Check confluence factors before trade execution"""
    if not mt5_service.connected:
        return Response({
            'status': 'error',
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', 'XAUUSD')
    result = signal_detection_service.check_confluence(symbol)
    
    if result['success']:
        return Response({
            'status': 'success',
            'data': result
        })
    else:
        return Response({
            'status': 'error',
            'message': result['error']
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_session_status(request):
    """Get current session status"""
    today = timezone.now().date()
    
    session = TradingSession.objects.filter(
        session_date=today,
        session_type='ASIAN'
    ).first()
    
    if not session:
        return Response({
            'status': 'success',
            'data': {
                'session_exists': False,
                'state': 'NO_SESSION'
            }
        })
    
    # Get related data
    sweeps = LiquiditySweep.objects.filter(session=session).order_by('-sweep_time')
    signals = TradeSignal.objects.filter(session=session).order_by('-created_at')
    
    return Response({
        'status': 'success',
        'data': {
            'session_exists': True,
            'session_id': session.id,
            'state': session.current_state,
            'session_date': session.session_date,
            'asian_range_high': session.asian_range_high,
            'asian_range_low': session.asian_range_low,
            'asian_range_midpoint': session.asian_range_midpoint,
            'asian_range_size': session.asian_range_size,
            'sweep_direction': session.sweep_direction,
            'sweep_time': session.sweep_time,
            'confirmation_time': session.confirmation_time,
            'armed_time': session.armed_time,
            'sweeps_count': sweeps.count(),
            'signals_count': signals.count(),
            'latest_sweep': {
                'direction': sweeps.first().sweep_direction,
                'price': sweeps.first().sweep_price,
                'time': sweeps.first().sweep_time
            } if sweeps.exists() else None,
            'latest_signal': {
                'type': signals.first().signal_type,
                'entry_price': signals.first().entry_price,
                'stop_loss': signals.first().stop_loss,
                'take_profit_1': signals.first().take_profit_1,
                'take_profit_2': signals.first().take_profit_2,
                'volume': signals.first().volume
            } if signals.exists() else None
        }
    })

@api_view(['POST'])
def run_full_analysis(request):
    """Run complete analysis workflow - now state-aware like auto mode"""
    if not mt5_service.connected:
        return Response({
            'status': 'error',
            'message': 'Not connected to MT5'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    symbol = request.data.get('symbol', 'XAUUSD')
    
    # Step 1: Initialize session
    session_result = signal_detection_service.initialize_session(symbol)
    if not session_result['success']:
        return Response({
            'status': 'error',
            'message': f"Session initialization failed: {session_result['error']}"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get current session state
    current_state = signal_detection_service.current_session.current_state if signal_detection_service.current_session else 'IDLE'
    
    # Step 2: Detect sweep only if IDLE
    if current_state == 'IDLE':
        sweep_result = signal_detection_service.detect_sweep(symbol)
        if not sweep_result['success']:
            return Response({
                'status': 'error',
                'message': f"Sweep detection failed: {sweep_result['error']}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not sweep_result['sweep_detected']:
            return Response({
                'status': 'success',
                'data': {
                    'workflow_step': 'SWEEP_DETECTION',
                    'sweep_detected': False,
                    'current_price': sweep_result['current_price'],
                    'asian_high': sweep_result['asian_high'],
                    'asian_low': sweep_result['asian_low'],
                    'threshold': sweep_result['threshold']
                }
            })
        current_state = 'SWEPT'
    
    # Step 3: Confirm reversal if SWEPT
    if current_state == 'SWEPT':
        reversal_result = signal_detection_service.confirm_reversal(symbol)
        if not reversal_result['success']:
            return Response({
                'status': 'error',
                'message': f"Reversal confirmation failed: {reversal_result['error']}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not reversal_result['confirmed']:
            return Response({
                'status': 'success',
                'data': {
                    'workflow_step': 'REVERSAL_CONFIRMATION',
                    'sweep_detected': True,
                    'reversal_confirmed': False,
                    'reason': reversal_result['reason']
                }
            })
        current_state = 'CONFIRMED'
    
    # Step 4: Check confluence if CONFIRMED
    if current_state == 'CONFIRMED':
        confluence_result = signal_detection_service.check_confluence(symbol)
        if not confluence_result['success']:
            return Response({
                'status': 'error',
                'message': f"Confluence check failed: {confluence_result['error']}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not confluence_result['confluence_passed']:
            return Response({
                'status': 'success',
                'data': {
                    'workflow_step': 'CONFLUENCE_CHECK',
                    'sweep_detected': True,
                    'reversal_confirmed': True,
                    'confluence_passed': False,
                    'spread_ok': confluence_result['spread_ok'],
                    'auction_blackout': confluence_result['auction_blackout']
                }
            })
        
        # Step 5: Generate signal
        signal_result = signal_detection_service.generate_trade_signal(symbol)
        if not signal_result['success']:
            return Response({
                'status': 'error',
                'message': f"Signal generation failed: {signal_result['error']}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'status': 'success',
            'data': {
                'workflow_step': 'SIGNAL_GENERATED',
                'sweep_detected': True,
                'reversal_confirmed': True,
                'confluence_passed': True,
                'signal_generated': True,
                'signal_data': {
                    'signal_type': signal_result['signal_type'],
                    'entry_price': signal_result['entry_price'],
                    'stop_loss': signal_result['stop_loss'],
                    'take_profit_1': signal_result['take_profit_1'],
                    'take_profit_2': signal_result['take_profit_2'],
                    'volume': signal_result['volume']
                }
            }
        })
    
    # If already ARMED or IN_TRADE, return current state
    if current_state in ['ARMED', 'IN_TRADE']:
        return Response({
            'status': 'success',
            'data': {
                'workflow_step': f'ALREADY_{current_state}',
                'sweep_detected': True,
                'reversal_confirmed': True,
                'confluence_passed': True,
                'current_state': current_state
            }
        })
    
    # Any other state fallback
    return Response({
        'status': 'error',
        'message': f'Unhandled state: {current_state}'
    }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
def run_strategy_once(request):
    """End-to-end execution per client's rule chain."""
    if not mt5_service.connected:
        return Response({'status':'error','message':'Not connected to MT5'}, status=status.HTTP_400_BAD_REQUEST)
    symbol = request.data.get('symbol', 'XAUUSD')
    result = signal_detection_service.run_strategy_once(symbol)
    code = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
    return Response({'status': 'success' if result.get('success') else 'error', 'data': result}, status=code)
