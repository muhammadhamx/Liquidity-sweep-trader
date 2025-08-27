import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
from django.utils import timezone
from typing import Dict, Optional, Tuple
from ..models import TradingSession, LiquiditySweep, ConfluenceCheck, TradeSignal, MarketData
from .mt5_service import MT5Service
import pytz
from .trade_service import TradeService
import logging

logger = logging.getLogger(__name__)

class SignalDetectionService:
    def __init__(self, mt5_service: MT5Service):
        self.mt5_service = mt5_service
        self.current_session = None
        self._trade_service = TradeService(mt5_service)
        self.test_mode = False  # Enable for testing outside Asian session

    def enable_test_mode(self):
        """Enable test mode for trading outside Asian session hours"""
        self.test_mode = True
        logger.info("Test mode enabled - trading allowed outside Asian session")

    def disable_test_mode(self):
        """Disable test mode - normal Asian session restrictions apply"""
        self.test_mode = False
        logger.info("Test mode disabled - normal Asian session restrictions apply")

    def initialize_session(self, symbol: str = "XAUUSD") -> Dict:
        """Initialize a new trading session"""
        today = timezone.now().date()
        
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
        logger.debug(f"detect_sweep called for {symbol}")

        if not self.current_session:
            logger.debug("No active session")
            return {'success': False, 'error': 'No active session'}

        logger.debug(f"Current session state: {self.current_session.current_state}")
        if self.current_session.current_state != 'IDLE':
            return {'success': False, 'error': f'Invalid state: {self.current_session.current_state}'}

        # Get Asian range data
        logger.debug("Getting Asian range data")
        asian_data = self.mt5_service.get_asian_session_data(symbol)
        logger.debug(f"Asian data: {asian_data}")
        if not asian_data.get('success'):
            return {'success': False, 'error': 'Failed to get Asian range data'}

        # Get current price
        logger.debug("Getting current price")
        current_price_data = self.mt5_service.get_current_price(symbol)
        logger.debug(f"Current price data: {current_price_data}")
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
            # If an opposite-side sweep already happened this session → COOLDOWN
            if self.current_session.sweep_direction and self.current_session.sweep_direction != sweep_direction:
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.save()
                return {
                    'success': False,
                    'sweep_detected': True,
                    'direction': sweep_direction,
                    'price': sweep_price,
                    'threshold': sweep_threshold_pips,
                    'session_state': 'COOLDOWN',
                    'reason': 'Both sides swept; entering cooldown'
                }

            # Create sweep record
            sweep = LiquiditySweep.objects.create(
                session=self.current_session,
                symbol=symbol,
                sweep_direction=sweep_direction,
                sweep_price=sweep_price,
                sweep_threshold=sweep_threshold_pips,
                sweep_time=timezone.now()
            )
            
            # Update session state
            self.current_session.current_state = 'SWEPT'
            self.current_session.sweep_direction = sweep_direction
            self.current_session.sweep_time = timezone.now()
            # Store the threshold in pips
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
        
        # Get recent M5 data with fallback strategies
        end_time = timezone.now()

        m5_data = None
        for attempt in range(3):  # Try 3 times with different time ranges
            time_range = 30 + (attempt * 15)  # 30, 45, 60 minutes
            start_time = end_time - timedelta(minutes=time_range)
            m5_data = self.mt5_service.get_historical_data(symbol, "M5", start_time, end_time)
            if m5_data is not None and len(m5_data) > 0:
                break

        if m5_data is None or len(m5_data) == 0:
            # Check if it's weekend or market closed
            if end_time.weekday() >= 5:  # Weekend
                return {'success': False, 'error': 'Market closed (Weekend) - No M5 data available'}
            else:
                return {'success': False, 'error': 'No M5 data available - Market may be closed'}
        
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
        
        # Update session state to CONFIRMED and start retest window (3 M5 bars)
        self.current_session.current_state = 'CONFIRMED'
        self.current_session.confirmation_time = timezone.now()
        self.current_session.save()
        
        return {
            'success': True,
            'confirmed': True,
            'session_state': 'CONFIRMED',
            'retest_window_minutes': 15,  # 3×M5
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
        
        # Calculate position size with accurate point/contract
        account_info = self.mt5_service.get_account_info()
        if not account_info:
            return {'success': False, 'error': 'Failed to get account info'}
        equity = account_info['equity']
        # Risk % by Asian range grade
        base_risk = 0.01
        grade = (self.current_session.asian_range_grade or 'NORMAL').upper()
        risk_map = {
            'TIGHT': 0.005,   # 0.5%
            'NORMAL': 0.01,   # 1.0%
            'WIDE': 0.01      # 1.0% (can downshift if desired)
        }
        risk_pct = risk_map.get(grade, base_risk)
        risk_amount = equity * risk_pct
        stop_distance = abs(entry_price - stop_loss)
        # Derive tick size/value from MT5 symbol info
        info = mt5.symbol_info(symbol)
        if info is None:
            return {'success': False, 'error': 'Symbol info unavailable for sizing'}
        # In many brokers for XAUUSD: point=0.01 or 0.1; tick_value per lot applies
        point = info.point
        # Fallback tick_value if missing
        tick_value = getattr(info, 'trade_tick_value', 1.0) or 1.0
        contract_size = getattr(info, 'trade_contract_size', 100.0) or 100.0
        # Monetary risk per 1 lot for stop_distance:
        # approx_value_per_lot = (stop_distance / point) * tick_value
        approx_value_per_lot = (stop_distance / max(point, 1e-9)) * tick_value
        if approx_value_per_lot <= 0:
            return {'success': False, 'error': 'Invalid sizing parameters'}
        volume = max(0.01, round(risk_amount / approx_value_per_lot, 2))  # lots rounded
        
        # Create trade signal
        # Risk percentage stored for traceability
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
            risk_percentage=risk_pct * 100.0,
            state='CONFIRMED'
        )
        
        # Update session state
        self.current_session.current_state = 'ARMED'
        self.current_session.armed_time = timezone.now()
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

    def execute_trade(self, symbol: str = "XAUUSD", volume: float = None) -> Dict:
        """Execute the ARMED signal as a market order (opposite of sweep) with SL/TP.
        
        Args:
            symbol: The trading symbol
            volume: Optional volume override (if None, uses the signal's volume)
        """
        if not self.current_session or self.current_session.current_state != 'ARMED':
            return {'success': False, 'error': 'No armed signal to execute'}
        
        signal = TradeSignal.objects.filter(session=self.current_session).order_by('-created_at').first()
        if not signal:
            return {'success': False, 'error': 'No signal found'}
        
        # Use provided volume if specified, otherwise use signal's volume
        trade_volume = volume if volume is not None else float(signal.volume)
        
        result = self._trade_service.place_market_order(
            symbol=symbol,
            trade_type=signal.signal_type,
            volume=trade_volume,
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
        # Persist execution
        try:
            from ..models import TradeExecution
            TradeExecution.objects.create(
                signal=signal,
                order_id=result.get('order_id') or 0,
                execution_price=result.get('price') or signal.entry_price,
                execution_time=timezone.now(),
                status='EXECUTED'
            )
        except Exception:
            pass
        return {'success': True, 'order': result, 'session_state': 'IN_TRADE'}

    def check_confluence(self, symbol: str = "XAUUSD") -> Dict:
        """HTF bias (D1/H4), spread gate, and news blackout integration."""
        if not self.current_session:
            return {'success': False, 'error': 'No active session'}
        # Spread gate
        tick = self.mt5_service.get_current_price(symbol)
        if not tick:
            return {'success': False, 'error': 'No tick data'}
        spread = (tick['ask'] - tick['bid']) * 10  # XAUUSD pips
        spread_ok = spread <= 2.0
        # HTF bias from H4 and D1: simple MA bias proxy using close vs SMA
        end = timezone.now()
        d1 = self.mt5_service.get_historical_data(symbol, 'D1', end - timedelta(days=60), end)
        h4 = self.mt5_service.get_historical_data(symbol, 'H4', end - timedelta(days=30), end)
        def _bias(df: Optional[pd.DataFrame]) -> str:
            if df is None or len(df) < 20:
                return 'UNKNOWN'
            close = df['close']
            sma = close.rolling(window=20).mean()
            if close.iloc[-1] > sma.iloc[-1] * 1.001:
                return 'BULL'
            if close.iloc[-1] < sma.iloc[-1] * 0.999:
                return 'BEAR'
            return 'RANGE'
        bias_d1 = _bias(d1)
        bias_h4 = _bias(h4)
        # Gate: bias alignment not strictly required but RANGE+countertrend can fail
        bias_gate = True
        if self.current_session.sweep_direction == 'UP' and bias_d1 == 'BULL' and bias_h4 == 'BULL':
            # fading strong HTF uptrend is riskier
            bias_gate = True  # still allow, but could set to False if strict
        if self.current_session.sweep_direction == 'DOWN' and bias_d1 == 'BEAR' and bias_h4 == 'BEAR':
            bias_gate = True
        # News blackout
        news_blackout = False
        buffer_minutes = 30
        try:
            from ..models import EconomicNews
            now = timezone.now()
            window_start = now - timedelta(minutes=buffer_minutes)
            window_end = now + timedelta(minutes=buffer_minutes)
            qs = EconomicNews.objects.filter(severity__in=['HIGH', 'CRITICAL'], release_time__gte=window_start, release_time__lte=window_end)
            news_blackout = qs.exists()
            if qs.exists():
                # use max buffer found
                buffer_minutes = max([n.buffer_minutes for n in qs]) if qs else buffer_minutes
        except Exception:
            pass
        confluence_passed = spread_ok and (not news_blackout) and bias_gate
        # Persist a confluence record for H4 and D1
        try:
            from ..models import ConfluenceCheck
            ConfluenceCheck.objects.create(
                session=self.current_session,
                timeframe='H4', bias=bias_h4,
                spread=spread, news_risk=news_blackout,
                news_buffer_minutes=buffer_minutes, passed=confluence_passed
            )
            ConfluenceCheck.objects.create(
                session=self.current_session,
                timeframe='D1', bias=bias_d1,
                spread=spread, news_risk=news_blackout,
                news_buffer_minutes=buffer_minutes, passed=confluence_passed
            )
        except Exception:
            pass
        return {
            'success': True,
            'confluence_passed': confluence_passed,
            'spread_ok': spread_ok,
            'bias_h4': bias_h4,
            'bias_d1': bias_d1,
            'auction_blackout': news_blackout
        }

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
            # 5) Time-boxed retest window (3 M5 bars)
            now = timezone.now()
            if self.current_session.confirmation_time and (now - self.current_session.confirmation_time) > timedelta(minutes=15):
                # Expired retest window
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.save()
                return {'success': False, 'stage': 'RETEST', 'no_trade': True, 'reason': 'Retest window expired (3 M5 bars). Entering cooldown.'}
            # Check retest: price revisits entry zone (midpoint ± 5 pips) in-window
            asian_mid = float(self.current_session.asian_range_midpoint)

            # Try to get M5 data with fallback strategies
            m5 = None
            for attempt in range(3):  # Try 3 times with different time ranges
                time_range = 20 + (attempt * 10)  # 20, 30, 40 minutes
                m5 = self.mt5_service.get_historical_data(symbol, 'M5', now - timedelta(minutes=time_range), now)
                if m5 is not None and len(m5) > 0:
                    break

            if m5 is None or len(m5) == 0:
                # Check if it's weekend or market closed
                if now.weekday() >= 5:  # Weekend
                    return {'success': False, 'stage': 'RETEST', 'no_trade': True, 'reason': 'Market closed (Weekend) - No M5 data for retest'}
                else:
                    return {'success': False, 'stage': 'RETEST', 'no_trade': True, 'reason': 'No M5 data for retest - Market may be closed'}
            # Define retest band
            pip = 0.1
            band = 5 * pip
            touched = ((m5['low'] <= asian_mid + band) & (m5['high'] >= asian_mid - band)).any()
            if not touched:
                return {'success': False, 'stage': 'RETEST', 'no_trade': True, 'reason': 'Awaiting retest of entry zone (midpoint ± 5 pips)'}
            # 6) Generate signal once retest touched
            sig = self.generate_trade_signal(symbol)
            if not sig.get('success'):
                return {'success': False, 'stage': 'SIGNAL', 'error': sig.get('error', 'signal failed')}
            # Optional: M1/M5 latest recheck of spread/news right before arming
            conf2 = self.check_confluence(symbol)
            if not conf2.get('confluence_passed'):
                return {'success': False, 'stage': 'CONFLUENCE', 'no_trade': True, 'reason': 'Confluence failed at arming', 'details': conf2}
            state = 'ARMED'

        # 6) Execute order if ARMED
        if state == 'ARMED':
            exe = self.execute_trade(symbol)
            if not exe.get('success'):
                return {'success': False, 'stage': 'EXECUTE', 'error': exe.get('error', 'execution failed'), 'data': exe.get('data')}
            # After execution, do one management step
            tm = self.manage_in_trade(symbol)
            return {'success': True, 'stage': 'DONE', 'order': exe['order'], 'session_state': 'IN_TRADE', 'management': tm}

        # If already IN_TRADE, return current state
        if state == 'IN_TRADE':
            # Perform one step of trade management
            tm = self.manage_in_trade(symbol)
            return {'success': True, 'stage': 'ALREADY_IN_TRADE', 'session_state': 'IN_TRADE', 'management': tm}

        # Any other state fallback
        return {'success': False, 'stage': 'UNKNOWN', 'error': f'Unhandled state: {state}'}

    def manage_in_trade(self, symbol: str = "XAUUSD") -> Dict:
        """
        Comprehensive trade management with multiple exit strategies:
        1. Move SL to breakeven at +0.5R
        2. Implement trailing stop based on ATR or M1 swings
        3. Hard exits for session end, news events, or timeout
        4. Partial profit taking at TP1 (midpoint)
        5. Track trade performance and update state machine
        """
        from ..models import TradeManagement, TradeExecution
        
        try:
            # Validate we're in a trade
            if not self.current_session or self.current_session.current_state != 'IN_TRADE':
                return {'success': False, 'reason': 'Not in trade'}
                
            # Get the active signal
            signal = TradeSignal.objects.filter(session=self.current_session).order_by('-created_at').first()
            if not signal:
                return {'success': False, 'reason': 'No signal found'}
                
            # Get open position for the symbol
            pos_resp = self._trade_service.get_open_positions(symbol)
            if not pos_resp.get('success'):
                # Position might be closed already
                executions = TradeExecution.objects.filter(signal=signal).order_by('-execution_time')
                if executions.exists():
                    # Check if we need to transition to COOLDOWN
                    self.current_session.current_state = 'COOLDOWN'
                    self.current_session.save()
                    return {
                        'success': True, 
                        'trade_closed': True,
                        'reason': 'Position already closed',
                        'profit': executions.first().profit if executions.first().profit else 0
                    }
                return {'success': False, 'reason': 'No open positions and no execution record'}
                
            positions = pos_resp.get('positions', [])
            if not positions:
                # Same as above - position might be closed
                executions = TradeExecution.objects.filter(signal=signal).order_by('-execution_time')
                if executions.exists():
                    self.current_session.current_state = 'COOLDOWN'
                    self.current_session.save()
                    return {
                        'success': True, 
                        'trade_closed': True,
                        'reason': 'Position already closed',
                        'profit': executions.first().profit if executions.first().profit else 0
                    }
                return {'success': False, 'reason': 'No open positions'}
                
            # Get position details
            pos = positions[0]
            entry = float(signal.entry_price)
            sl = float(signal.stop_loss)
            tp1 = float(signal.take_profit1) if signal.take_profit1 else None
            tp2 = float(signal.take_profit2) if signal.take_profit2 else None
            
            # Calculate R distance (risk)
            r_dist = abs(entry - sl)
            
            # Get current price
            tick = self.mt5_service.get_current_price(symbol)
            if not tick:
                return {'success': False, 'reason': 'No tick data available'}
                
            price = tick['bid'] if signal.signal_type == 'SELL' else tick['ask']
            
            # Calculate current profit in R
            current_r = (price - entry) / r_dist if signal.signal_type == 'BUY' else (entry - price) / r_dist
            
            # Initialize actions list to track what we did
            actions = []
            trade_closed = False
            
            # 1. Move to breakeven at +0.5R (if not already done)
            reached_half_r = (price >= entry + 0.5 * r_dist) if signal.signal_type == 'BUY' else (price <= entry - 0.5 * r_dist)
            if reached_half_r and not TradeManagement.objects.filter(
                execution__signal=signal, action_type='MOVE_BE'
            ).exists():
                new_sl = entry
                mod = self._trade_service.modify_position_sl_tp(
                    pos['ticket'], 
                    sl=new_sl, 
                    tp=pos.get('tp') or 0
                )
                actions.append({'action': 'MOVE_BE', 'result': mod})
                
                # Record this management action
                exec_obj = TradeExecution.objects.filter(signal=signal).order_by('-execution_time').first()
                if exec_obj:
                    TradeManagement.objects.create(
                        execution=exec_obj,
                        action_type='MOVE_BE',
                        old_value=sl,
                        new_value=new_sl,
                        action_time=datetime.now(),
                        reason='+0.5R reached'
                    )
            
            # 2. Implement trailing stop based on ATR or M1 swings (if beyond +1R)
            reached_one_r = (price >= entry + 1.0 * r_dist) if signal.signal_type == 'BUY' else (price <= entry - 1.0 * r_dist)
            if reached_one_r and not TradeManagement.objects.filter(
                execution__signal=signal, action_type='TRAILING'
            ).exists():
                # Get ATR for trailing stop calculation
                now = datetime.now()
                m1_data = self.mt5_service.get_historical_data(symbol, 'M1', now - timedelta(hours=1), now)
                
                if m1_data is not None and len(m1_data) > 0:
                    # Calculate ATR (simple version)
                    m1_data['tr'] = m1_data['high'] - m1_data['low']
                    atr = m1_data['tr'].mean()
                    
                    # Set trailing stop at 1.3 x ATR from current price
                    new_sl = price - (1.3 * atr) if signal.signal_type == 'BUY' else price + (1.3 * atr)
                    
                    # Ensure new SL is better than breakeven
                    if (signal.signal_type == 'BUY' and new_sl > entry) or (signal.signal_type == 'SELL' and new_sl < entry):
                        mod = self._trade_service.modify_position_sl_tp(
                            pos['ticket'], 
                            sl=new_sl, 
                            tp=pos.get('tp') or 0
                        )
                        actions.append({'action': 'TRAILING', 'result': mod})
                        
                        # Record this management action
                        exec_obj = TradeExecution.objects.filter(signal=signal).order_by('-execution_time').first()
                        if exec_obj:
                            TradeManagement.objects.create(
                                execution=exec_obj,
                                action_type='TRAILING',
                                old_value=entry,  # Previous SL was at breakeven
                                new_value=new_sl,
                                action_time=datetime.now(),
                                reason='+1R reached, trailing by 1.3xATR'
                            )
            
            # 3. Hard exit conditions
            
            # 3.1 Session time limits (exit after Asian session ends)
            now_utc = timezone.now().astimezone(pytz.UTC).replace(tzinfo=None)
            sess_start = datetime.combine(now_utc.date(), time(0, 0))
            sess_end = datetime.combine(now_utc.date(), time(6, 0))
            
            if now_utc >= sess_end or now_utc < sess_start:
                close_res = self._trade_service.close_position(pos['ticket'])
                actions.append({'action': 'CLOSE_SESSION_END', 'result': close_res})
                trade_closed = True
            
            # 3.2 News/auction blackout periods
            conf = self.check_confluence(symbol)
            if conf.get('auction_blackout'):
                close_res = self._trade_service.close_position(pos['ticket'])
                actions.append({'action': 'CLOSE_NEWS', 'result': close_res})
                trade_closed = True
            
            # 3.3 Trade timeout (max 4 hours in trade)
            exec_obj = TradeExecution.objects.filter(signal=signal).order_by('-execution_time').first()
            if exec_obj and (timezone.now() - exec_obj.execution_time).total_seconds() > 4 * 60 * 60:
                close_res = self._trade_service.close_position(pos['ticket'])
                actions.append({'action': 'CLOSE_TIMEOUT', 'result': close_res})
                trade_closed = True
            
            # 4. Partial profit taking at TP1 (if not already done)
            if tp1 and not TradeManagement.objects.filter(
                execution__signal=signal, action_type='PARTIAL_TP'
            ).exists():
                reached_tp1 = (price >= tp1) if signal.signal_type == 'BUY' else (price <= tp1)
                
                if reached_tp1:
                    # Close half position at TP1
                    volume = float(pos['volume'])
                    half_volume = volume / 2
                    
                    # Close partial position
                    partial_close = self._trade_service.close_partial_position(
                        pos['ticket'], 
                        volume=half_volume
                    )
                    actions.append({'action': 'PARTIAL_TP', 'result': partial_close})
                    
                    # Record this management action
                    if exec_obj:
                        TradeManagement.objects.create(
                            execution=exec_obj,
                            action_type='PARTIAL_TP',
                            old_value=volume,
                            new_value=half_volume,
                            action_time=datetime.now(),
                            reason='TP1 reached, closed half position'
                        )
            
            # 5. Update state if trade is closed
            if trade_closed:
                self.current_session.current_state = 'COOLDOWN'
                self.current_session.save()
                
                # Get profit information if available
                profit = None
                if 'profit' in pos:
                    profit = pos['profit']
                
                return {
                    'success': True,
                    'trade_closed': True,
                    'actions': actions,
                    'profit': profit,
                    'current_r': current_r
                }
            
            # Return success with actions taken
            return {
                'success': True,
                'actions': actions,
                'current_r': current_r,
                'trade_closed': False
            }
            
        except Exception as e:
            import traceback
            return {
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def _calculate_sweep_threshold(self, asian_data: Dict) -> float:
        """Calculate dynamic sweep threshold"""
        range_pips = asian_data['range_pips']
        
        # Base threshold: max(min_floor_pips, 9% of Asia range)
        # Make floor configurable via session grade or a default of 10 pips
        min_floor_pips = 10  # TODO: pull from settings or per-broker config (10–15)
        base_threshold = max(min_floor_pips, range_pips * 0.09)
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
        """HTF bias (D1/H4), spread gate, and news blackout integration."""
        if not self.current_session:
            return {'success': False, 'error': 'No active session'}
        # Spread gate
        tick = self.mt5_service.get_current_price(symbol)
        if not tick:
            return {'success': False, 'error': 'No tick data'}
        spread = (tick['ask'] - tick['bid']) * 10  # XAUUSD pips
        spread_ok = spread <= 2.0
        # HTF bias from H4 and D1: simple MA bias proxy using close vs SMA
        end = timezone.now()
        d1 = self.mt5_service.get_historical_data(symbol, 'D1', end - timedelta(days=60), end)
        h4 = self.mt5_service.get_historical_data(symbol, 'H4', end - timedelta(days=30), end)
        def _bias(df: Optional[pd.DataFrame]) -> str:
            if df is None or len(df) < 20:
                return 'UNKNOWN'
            close = df['close']
            sma = close.rolling(window=20).mean()
            if close.iloc[-1] > sma.iloc[-1] * 1.001:
                return 'BULL'
            if close.iloc[-1] < sma.iloc[-1] * 0.999:
                return 'BEAR'
            return 'RANGE'
        bias_d1 = _bias(d1)
        bias_h4 = _bias(h4)
        # Gate: bias alignment not strictly required but RANGE+countertrend can fail
        bias_gate = True
        if self.current_session.sweep_direction == 'UP' and bias_d1 == 'BULL' and bias_h4 == 'BULL':
            bias_gate = True
        if self.current_session.sweep_direction == 'DOWN' and bias_d1 == 'BEAR' and bias_h4 == 'BEAR':
            bias_gate = True
        # News blackout
        news_blackout = False
        buffer_minutes = 30
        try:
            from ..models import EconomicNews
            now = timezone.now()
            window_start = now - timedelta(minutes=buffer_minutes)
            window_end = now + timedelta(minutes=buffer_minutes)
            qs = EconomicNews.objects.filter(severity__in=['HIGH', 'CRITICAL'], release_time__gte=window_start, release_time__lte=window_end)
            news_blackout = qs.exists()
            if qs.exists():
                buffer_minutes = max([n.buffer_minutes for n in qs]) if qs else buffer_minutes
        except Exception:
            pass
        confluence_passed = spread_ok and (not news_blackout) and bias_gate
        # Persist confluence records
        try:
            ConfluenceCheck.objects.create(
                session=self.current_session,
                timeframe='H4', bias=bias_h4,
                spread=spread, news_risk=bool(news_blackout),
                news_buffer_minutes=buffer_minutes, passed=confluence_passed
            )
            ConfluenceCheck.objects.create(
                session=self.current_session,
                timeframe='D1', bias=bias_d1,
                spread=spread, news_risk=bool(news_blackout),
                news_buffer_minutes=buffer_minutes, passed=confluence_passed
            )
        except Exception:
            pass
        return {
            'success': True,
            'confluence_passed': confluence_passed,
            'spread_ok': spread_ok,
            'bias_h4': bias_h4,
            'bias_d1': bias_d1,
            'auction_blackout': bool(news_blackout)
        }
