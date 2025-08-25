import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
from typing import Dict, Optional, Tuple
from ..models import TradingSession, LiquiditySweep, ConfluenceCheck, TradeSignal, MarketData
from .mt5_service import MT5Service
import pytz
from .trade_service import TradeService

class SignalDetectionService:
    def __init__(self, mt5_service: MT5Service):
        self.mt5_service = mt5_service
        self.current_session = None
        self._trade_service = TradeService(mt5_service)
        
    def initialize_session(self, symbol: str = "XAUUSD") -> Dict:
        """Initialize a new trading session"""
        today = datetime.now().date()
        
        # Check if session already exists
        existing_session = TradingSession.objects.filter(
            session_date=today,
            session_type='ASIAN'
        ).first()
        
        if existing_session:
            self.current_session = existing_session
            return {
                'success': True,
                'message': 'Session already exists',
                'session_id': existing_session.id,
                'state': existing_session.current_state
            }
        
        # Create new session and populate Asian range
        asian_data = self.mt5_service.get_asian_session_data(symbol)
        session_kwargs = {
            'session_date': today,
            'session_type': 'ASIAN',
            'current_state': 'IDLE'
        }
        if asian_data and asian_data.get('success'):
            session_kwargs.update({
                'asian_range_high': asian_data['high'],
                'asian_range_low': asian_data['low'],
                'asian_range_midpoint': asian_data['midpoint'],
                'asian_range_size': asian_data['range_pips'],
                'asian_range_grade': asian_data['grade']
            })
        session = TradingSession.objects.create(**session_kwargs)
        
        self.current_session = session
        
        return {
            'success': True,
            'message': 'New session created',
            'session_id': session.id,
            'state': 'IDLE'
        }
    
    def detect_sweep(self, symbol: str = "XAUUSD") -> Dict:
        """Detect Asian session liquidity sweep"""
        if not self.current_session:
            return {'success': False, 'error': 'No active session'}
        
        if self.current_session.current_state != 'IDLE':
            return {'success': False, 'error': f'Invalid state: {self.current_session.current_state}'}
        
        # Get Asian range data
        asian_data = self.mt5_service.get_asian_session_data(symbol)
        if not asian_data['success']:
            return {'success': False, 'error': 'Failed to get Asian range data'}
        
        # Get current price
        current_price_data = self.mt5_service.get_current_price(symbol)
        if not current_price_data:
            return {'success': False, 'error': 'Failed to get current price'}
        
        current_price = current_price_data['bid']  # Use bid for conservative approach
        
        # Calculate dynamic sweep threshold (in pips, convert to price)
        sweep_threshold_pips = self._calculate_sweep_threshold(asian_data)
        pip_value = 0.1  # XAUUSD: 1 pip = $0.10
        sweep_threshold_price = sweep_threshold_pips * pip_value
        
        # Check for sweep
        sweep_direction = None
        sweep_price = None
        
        # Check upper sweep
        if current_price > float(asian_data['high']) + sweep_threshold_price:
            sweep_direction = 'UP'
            sweep_price = current_price
        # Check lower sweep
        elif current_price < float(asian_data['low']) - sweep_threshold_price:
            sweep_direction = 'DOWN'
            sweep_price = current_price
        
        if sweep_direction:
            # Create sweep record
            sweep = LiquiditySweep.objects.create(
                session=self.current_session,
                symbol=symbol,
                sweep_direction=sweep_direction,
                sweep_price=sweep_price,
                sweep_threshold=sweep_threshold_pips,
                sweep_time=datetime.now()
            )
            
            # Update session state
            self.current_session.current_state = 'SWEPT'
            self.current_session.sweep_direction = sweep_direction
            self.current_session.sweep_time = datetime.now()
            # Store the threshold in pips (variable name was incorrect before)
            self.current_session.sweep_threshold = sweep_threshold_pips
            self.current_session.save()
            
            return {
                'success': True,
                'sweep_detected': True,
                'direction': sweep_direction,
                'price': sweep_price,
                'threshold': sweep_threshold_pips,
                'session_state': 'SWEPT',
                'sweep_id': sweep.id
            }
        
        return {
            'success': True,
            'sweep_detected': False,
            'current_price': current_price,
            'asian_high': asian_data['high'],
            'asian_low': asian_data['low'],
            'threshold': sweep_threshold_pips
        }
    
    def confirm_reversal(self, symbol: str = "XAUUSD") -> Dict:
        """Confirm reversal after sweep detection"""
        if not self.current_session or self.current_session.current_state != 'SWEPT':
            return {'success': False, 'error': 'Invalid state for reversal confirmation'}
        
        # Get recent M5 data
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=30)
        
        m5_data = self.mt5_service.get_historical_data(symbol, "M5", start_time, end_time)
        if m5_data is None or len(m5_data) == 0:
            return {'success': False, 'error': 'No M5 data available'}
        
        # Get Asian range
        asian_data = self.mt5_service.get_asian_session_data(symbol)
        if not asian_data['success']:
            return {'success': False, 'error': 'Failed to get Asian range data'}
        
        # Check if price closed back inside Asian range
        latest_close = m5_data.iloc[-1]['close']
        asian_high = asian_data['high']
        asian_low = asian_data['low']
        
        if not (asian_low <= latest_close <= asian_high):
            return {
                'success': True,
                'confirmed': False,
                'reason': 'Price not back inside Asian range',
                'latest_close': latest_close,
                'asian_range': f"{asian_low} - {asian_high}"
            }
        
        # Check displacement (body >= 1.3 × ATR)
        latest_candle = m5_data.iloc[-1]
        body_size = abs(latest_candle['close'] - latest_candle['open'])
        
        # Calculate ATR
        atr = self._calculate_atr(m5_data, period=14)
        displacement_threshold = atr * 1.3
        
        if body_size < displacement_threshold:
            return {
                'success': True,
                'confirmed': False,
                'reason': 'Insufficient displacement',
                'body_size': body_size,
                'displacement_threshold': displacement_threshold
            }
        
        # Check M1 CHOCH (Change of Character)
        m1_data = self.mt5_service.get_historical_data(symbol, "M1", start_time, end_time)
        if m1_data is not None and len(m1_data) > 0:
            choch_detected = self._detect_choch(m1_data, self.current_session.sweep_direction)
            if not choch_detected:
                return {
                    'success': True,
                    'confirmed': False,
                    'reason': 'M1 CHOCH not detected'
                }
        
        # Update session state
        self.current_session.current_state = 'CONFIRMED'
        self.current_session.confirmation_time = datetime.now()
        self.current_session.save()
        
        return {
            'success': True,
            'confirmed': True,
            'session_state': 'CONFIRMED',
            'body_size': body_size,
            'atr': atr,
            'displacement_threshold': displacement_threshold
        }
    
    def generate_trade_signal(self, symbol: str = "XAUUSD") -> Dict:
        """Generate trade signal after confirmation"""
        if not self.current_session or self.current_session.current_state != 'CONFIRMED':
            return {'success': False, 'error': 'Invalid state for signal generation'}
        
        # Get latest sweep
        sweep = LiquiditySweep.objects.filter(session=self.current_session).order_by('-sweep_time').first()
        if not sweep:
            return {'success': False, 'error': 'No sweep found for session'}
        
        # Calculate entry, SL, TP levels
        current_price_data = self.mt5_service.get_current_price(symbol)
        if not current_price_data:
            return {'success': False, 'error': 'Failed to get current price'}
        
        current_price = current_price_data['ask'] if sweep.sweep_direction == 'UP' else current_price_data['bid']
        
        # Calculate levels based on sweep direction
        if sweep.sweep_direction == 'UP':
            # Sweep was UP, so we want to SELL (fade the sweep)
            signal_type = 'SELL'
            entry_price = current_price
            stop_loss = sweep.sweep_price + 0.0005  # 5 pips above sweep
            take_profit_1 = self.current_session.asian_range_midpoint
            take_profit_2 = self.current_session.asian_range_low - 0.0002  # 2 pips below Asian low
        else:
            # Sweep was DOWN, so we want to BUY (fade the sweep)
            signal_type = 'BUY'
            entry_price = current_price
            stop_loss = sweep.sweep_price - 0.0005  # 5 pips below sweep
            take_profit_1 = self.current_session.asian_range_midpoint
            take_profit_2 = self.current_session.asian_range_high + 0.0002  # 2 pips above Asian high
        
        # Calculate position size (1% risk)
        account_info = self.mt5_service.get_account_info()
        if not account_info:
            return {'success': False, 'error': 'Failed to get account info'}
        
        equity = account_info['equity']
        risk_amount = equity * 0.01  # 1% risk
        stop_distance = abs(entry_price - stop_loss)
        point_value = 0.1  # XAUUSD: 1 pip = $0.10
        volume = risk_amount / (stop_distance * 10000 * point_value)  # Convert to lots
        
        # Create trade signal
        signal = TradeSignal.objects.create(
            session=self.current_session,
            sweep=sweep,
            symbol=symbol,
            signal_type=signal_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            volume=volume,
            risk_percentage=1.0,
            state='CONFIRMED'
        )
        
        # Update session state
        self.current_session.current_state = 'ARMED'
        self.current_session.armed_time = datetime.now()
        self.current_session.save()
        
        return {
            'success': True,
            'signal_generated': True,
            'signal_id': signal.id,
            'signal_type': signal_type,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit_1': take_profit_1,
            'take_profit_2': take_profit_2,
            'volume': volume,
            'session_state': 'ARMED'
        }

    def execute_trade(self, symbol: str = "XAUUSD") -> Dict:
        """Execute the ARMED signal as a market order (opposite of sweep) with SL/TP."""
        if not self.current_session or self.current_session.current_state != 'ARMED':
            return {'success': False, 'error': 'No armed signal to execute'}
        signal = TradeSignal.objects.filter(session=self.current_session).order_by('-created_at').first()
        if not signal:
            return {'success': False, 'error': 'No signal found'}
        result = self._trade_service.place_market_order(
            symbol=symbol,
            trade_type=signal.signal_type,
            volume=float(signal.volume),
            stop_loss=float(signal.stop_loss),
            take_profit=float(signal.take_profit_1) if signal.take_profit_1 else 0.0,
            deviation=20,
            comment='ALS Bot'
        )
        if not result.get('success'):
            return {'success': False, 'error': result.get('error', 'order failed'), 'data': result}
        # Transition to IN_TRADE
        self.current_session.current_state = 'IN_TRADE'
        self.current_session.save()
        return {'success': True, 'order': result, 'session_state': 'IN_TRADE'}

    def run_strategy_once(self, symbol: str = "XAUUSD") -> Dict:
        """One-shot: detect → confirm → confluence → signal → execute, per client's rules."""
        # 1) Ensure session
        if not self.current_session:
            self.initialize_session(symbol)

        # If state machine progressed already, continue from the next step.
        state = self.current_session.current_state

        # 2) Detect sweep only if we're IDLE
        if state == 'IDLE':
            sweep = self.detect_sweep(symbol)
            if not sweep.get('success'):
                return {'success': False, 'stage': 'DETECT', 'error': sweep.get('error', 'detect failed')}
            if not sweep.get('sweep_detected'):
                return {'success': False, 'stage': 'DETECT', 'no_trade': True, 'reason': 'No sweep detected'}
            state = 'SWEPT'

        # 3) Confirm reversal if we're SWEPT
        if state == 'SWEPT':
            confirm = self.confirm_reversal(symbol)
            if not confirm.get('success') or not confirm.get('confirmed'):
                return {'success': False, 'stage': 'CONFIRM', 'no_trade': True, 'reason': confirm.get('reason', 'not confirmed')}
            state = 'CONFIRMED'

        # 4) Confluence guard if CONFIRMED
        if state == 'CONFIRMED':
            conf = self.check_confluence(symbol)
            if not conf.get('success') or not conf.get('confluence_passed'):
                return {'success': False, 'stage': 'CONFLUENCE', 'no_trade': True, 'reason': 'Confluence failed', 'details': conf}
            # 5) Generate signal
            sig = self.generate_trade_signal(symbol)
            if not sig.get('success'):
                return {'success': False, 'stage': 'SIGNAL', 'error': sig.get('error', 'signal failed')}
            state = 'ARMED'

        # 6) Execute order if ARMED
        if state == 'ARMED':
            exe = self.execute_trade(symbol)
            if not exe.get('success'):
                return {'success': False, 'stage': 'EXECUTE', 'error': exe.get('error', 'execution failed'), 'data': exe.get('data')}
            return {'success': True, 'stage': 'DONE', 'order': exe['order'], 'session_state': 'IN_TRADE'}

        # If already IN_TRADE, return current state
        if state == 'IN_TRADE':
            return {'success': True, 'stage': 'ALREADY_IN_TRADE', 'session_state': 'IN_TRADE'}

        # Any other state fallback
        return {'success': False, 'stage': 'UNKNOWN', 'error': f'Unhandled state: {state}'}
    
    def _calculate_sweep_threshold(self, asian_data: Dict) -> float:
        """Calculate dynamic sweep threshold"""
        range_pips = asian_data['range_pips']
        
        # Base threshold: max(10 pips, 7.5-10% of Asia range, 0.5 × ATR(H1))
        base_threshold = max(10, range_pips * 0.075)
        
        # For XAUUSD, prefer upper end (9-10%)
        if range_pips > 50:
            base_threshold = max(base_threshold, range_pips * 0.09)
        
        return round(base_threshold, 1)
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(data) < period:
            return 0.001  # Default ATR
        
        high = data['high']
        low = data['low']
        close = data['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        
        return atr if not pd.isna(atr) else 0.001
    
    def _detect_choch(self, data: pd.DataFrame, sweep_direction: str) -> bool:
        """Detect Change of Character on M1"""
        if len(data) < 3:
            return False
        
        # Simple CHOCH detection: look for reversal pattern
        if sweep_direction == 'UP':
            # Look for lower high after sweep
            recent_highs = data['high'].tail(5)
            if len(recent_highs) >= 2:
                return recent_highs.iloc[-1] < recent_highs.iloc[-2]
        else:
            # Look for higher low after sweep
            recent_lows = data['low'].tail(5)
            if len(recent_lows) >= 2:
                return recent_lows.iloc[-1] > recent_lows.iloc[-2]
        
        return False
    
    def check_confluence(self, symbol: str = "XAUUSD") -> Dict:
        """Check confluence factors before trade execution"""
        if not self.current_session:
            return {'success': False, 'error': 'No active session'}
        
        # Get current market conditions
        current_price_data = self.mt5_service.get_current_price(symbol)
        if not current_price_data:
            return {'success': False, 'error': 'Failed to get current price'}
        
        spread = current_price_data['ask'] - current_price_data['bid']
        spread_pips = spread * 10000  # Convert to pips
        
        # Check spread condition
        spread_ok = spread_pips <= 2.0
        
        # Check time conditions (avoid LBMA auctions)
        now = datetime.now()
        london_time = now.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Europe/London'))
        hour = london_time.hour
        minute = london_time.minute
        
        # LBMA auction blackouts: ±10-15 min around 10:30 & 15:00 London
        auction_blackout = (
            (hour == 10 and 15 <= minute <= 45) or
            (hour == 15 and 0 <= minute <= 30)
        )
        
        # Create confluence check record
        confluence = ConfluenceCheck.objects.create(
            session=self.current_session,
            timeframe='M5',
            bias='RANGE',  # Default, should be calculated from HTF
            spread=spread_pips,
            velocity_spike=False,  # Should be calculated
            news_risk=False,  # Should check economic calendar
            passed=spread_ok and not auction_blackout
        )
        
        return {
            'success': True,
            'confluence_passed': confluence.passed,
            'spread_ok': spread_ok,
            'spread_pips': spread_pips,
            'auction_blackout': auction_blackout,
            'confluence_id': confluence.id
        }
