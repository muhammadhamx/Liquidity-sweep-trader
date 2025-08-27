import threading
import time
from datetime import datetime, timedelta
import logging
import requests
import json
from typing import Dict, Optional, List, Any
from django.utils import timezone
from ..models import TradingSession, SystemLog, TradeSignal, TradeExecution, TradeManagement, EconomicNews
from .signal_detection_service import SignalDetectionService
from .mt5_service import MT5Service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auto_trading.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("auto_trading")

class AutoTradingService:
    """
    Fully automated trading service that continuously monitors the market
    and executes trades based on the Asian Liquidity Sweep strategy.
    """
    
    def __init__(self, mt5_service: MT5Service, signal_service: SignalDetectionService):
        self.mt5_service = mt5_service
        self.signal_service = signal_service
        self.running = False
        self.thread = None
        self.monitor_interval = 1  # 1 second during active periods, adjusted dynamically
        self.symbol = "XAUUSD"
        self.daily_trade_count = 0
        self.daily_loss_count = 0
        self.max_daily_trades = 3
        self.max_daily_losses = 2
        self.last_gpt_call_time = {}  # Track last GPT call time by state
        self.gpt_cooldown = 60  # Seconds between GPT calls for same state
        self.last_log_time = timezone.now()
        self.log_interval = 60  # Log status every minute
        
    def start(self, symbol: str = "XAUUSD"):
        """Start the automated trading service"""
        if self.running:
            logger.warning("Auto trading service is already running")
            return False
            
        self.symbol = symbol
        self.running = True
        self.reset_daily_counters()
        
        # Log startup
        logger.info(f"Starting auto trading service for {symbol}")
        self._log_system_event("AUTO_START", f"Auto trading service started for {symbol}")
        
        # Start monitoring thread
        self.thread = threading.Thread(target=self._monitoring_loop)
        self.thread.daemon = True
        self.thread.start()
        
        return True
        
    def stop(self):
        """Stop the automated trading service"""
        if not self.running:
            logger.warning("Auto trading service is not running")
            return False
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
            
        logger.info("Auto trading service stopped")
        self._log_system_event("AUTO_STOP", "Auto trading service stopped")
        return True
        
    def status(self) -> Dict:
        """Get current status of the auto trading service"""
        current_session = self.signal_service.current_session
        session_state = current_session.current_state if current_session else "NO_SESSION"
        
        return {
            "running": self.running,
            "symbol": self.symbol,
            "session_state": session_state,
            "daily_trades": self.daily_trade_count,
            "daily_losses": self.daily_loss_count,
            "max_daily_trades": self.max_daily_trades,
            "max_daily_losses": self.max_daily_losses,
            "monitor_interval": self.monitor_interval,
            "last_update": timezone.now().isoformat()
        }
        
    def reset_daily_counters(self):
        """Reset daily trade and loss counters"""
        # Only reset if it's a new trading day
        now = timezone.now()
        today = now.date()
        
        # Get last trade date
        last_trade = TradeExecution.objects.order_by('-execution_time').first()
        last_trade_date = last_trade.execution_time.date() if last_trade else None
        
        if last_trade_date != today:
            self.daily_trade_count = 0
            self.daily_loss_count = 0
            logger.info(f"Daily counters reset: new trading day {today}")
            
    def _monitoring_loop(self):
        """Main monitoring loop that runs continuously"""
        while self.running:
            try:
                # Dynamic interval adjustment based on market activity and session state
                self._adjust_monitoring_interval()
                
                # Periodic status logging
                self._periodic_logging()
                
                # Check if we should be trading (market hours, not weekend)
                if not self._is_trading_time():
                    time.sleep(60)  # Sleep longer during non-trading hours
                    continue
                    
                # Check daily limits
                if self._daily_limits_reached():
                    time.sleep(60)  # Sleep longer if daily limits reached
                    continue
                
                # Initialize session if needed
                self._ensure_session()
                
                # Execute one step of the trading strategy based on current state
                self._execute_strategy_step()
                
                # Sleep for the monitoring interval
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}", exc_info=True)
                self._log_system_event("ERROR", f"Monitoring error: {str(e)}")
                time.sleep(5)  # Sleep on error to prevent rapid error loops
    
    def _adjust_monitoring_interval(self):
        """Dynamically adjust monitoring interval based on market conditions and state"""
        current_session = self.signal_service.current_session
        if not current_session:
            self.monitor_interval = 5  # Default interval when no session
            return
            
        state = current_session.current_state
        now = timezone.now()
        
        # Faster monitoring during active states
        if state in ['SWEPT', 'CONFIRMED', 'ARMED']:
            self.monitor_interval = 1  # 1 second during critical states
        elif state == 'IN_TRADE':
            self.monitor_interval = 2  # 2 seconds while in trade
        elif state == 'COOLDOWN':
            self.monitor_interval = 10  # 10 seconds during cooldown
        else:  # IDLE
            # Check if we're in an active trading session (London/NY)
            hour_utc = now.hour
            if 7 <= hour_utc <= 16:  # London/NY hours (7:00-16:00 UTC)
                self.monitor_interval = 2  # 2 seconds during active hours
            else:
                self.monitor_interval = 5  # 5 seconds during less active hours
    
    def _periodic_logging(self):
        """Log status periodically to keep track of system health"""
        now = timezone.now()
        if (now - self.last_log_time).total_seconds() >= self.log_interval:
            status = self.status()
            logger.info(f"Auto trading status: {json.dumps(status)}")
            self.last_log_time = now
    
    def _is_trading_time(self) -> bool:
        """Check if current time is valid for trading"""
        now = timezone.now()
        
        # Check for weekend (Saturday=5, Sunday=6)
        if now.weekday() >= 5:
            return False
            
        # Check for market hours (forex is 24/5)
        # We'll continue to analyze the market 24/5, but only execute trades during Asian session
        
        return True
        
    def _is_asian_session(self) -> bool:
        """Check if current time is within Asian trading session hours"""
        now = timezone.now()
        
        # Convert to UTC if needed
        # now_utc = now.astimezone(timezone.utc)
        
        # Asian session hours: approximately 00:00-08:00 UTC
        hour = now.hour
        return 0 <= hour < 8
    
    def _daily_limits_reached(self) -> bool:
        """Check if daily trade or loss limits have been reached"""
        if self.daily_trade_count >= self.max_daily_trades:
            logger.info(f"Daily trade limit reached: {self.daily_trade_count}/{self.max_daily_trades}")
            return True
            
        if self.daily_loss_count >= self.max_daily_losses:
            logger.info(f"Daily loss limit reached: {self.daily_loss_count}/{self.max_daily_losses}")
            return True
            
        return False
    
    def _ensure_session(self):
        """Ensure a trading session exists for today"""
        if not self.signal_service.current_session:
            logger.info("Initializing new trading session")
            result = self.signal_service.initialize_session(self.symbol)
            if result.get('success'):
                logger.info(f"Session initialized: {result}")
                self._log_system_event("SESSION_INIT", "Trading session initialized")
            else:
                logger.error(f"Failed to initialize session: {result}")
                self._log_system_event("ERROR", f"Session initialization failed: {result}")
    
    def _execute_strategy_step(self):
        """Execute one step of the trading strategy based on current state"""
        current_session = self.signal_service.current_session
        if not current_session:
            return
            
        state = current_session.current_state
        
        # Execute appropriate action based on current state
        if state == 'IDLE':
            self._handle_idle_state()
        elif state == 'SWEPT':
            self._handle_swept_state()
        elif state == 'CONFIRMED':
            self._handle_confirmed_state()
        elif state == 'ARMED':
            self._handle_armed_state()
        elif state == 'IN_TRADE':
            self._handle_in_trade_state()
        elif state == 'COOLDOWN':
            self._handle_cooldown_state()
    
    def _handle_idle_state(self):
        """Handle IDLE state: look for sweeps"""
        result = self.signal_service.detect_sweep(self.symbol)

        # Log sweep detection attempts for debugging
        if result.get('success'):
            if result.get('sweep_detected'):
                logger.info(f"Sweep detected: {result}")
                self._log_system_event("SWEEP_DETECTED", f"Sweep detected: {result.get('sweep_direction')} at {result.get('sweep_price')}")

                # Call GPT for sweep validation
                self._call_gpt_for_validation('SWEPT', result)
            else:
                # Log when no sweep is detected (for debugging)
                current_price = result.get('current_price', 0)
                asian_high = result.get('asian_high', 0)
                asian_low = result.get('asian_low', 0)
                logger.debug(f"No sweep detected - Price: {current_price:.2f}, Range: {asian_low:.2f}-{asian_high:.2f}")
        else:
            logger.warning(f"Sweep detection failed: {result.get('error', 'Unknown error')}")
    
    def _handle_swept_state(self):
        """Handle SWEPT state: look for reversal confirmation"""
        result = self.signal_service.confirm_reversal(self.symbol)
        
        if result.get('success') and result.get('confirmed'):
            logger.info(f"Reversal confirmed: {result}")
            self._log_system_event("REVERSAL_CONFIRMED", f"Reversal confirmed at {timezone.now().isoformat()}")
            
            # Call GPT for reversal validation
            self._call_gpt_for_validation('CONFIRMED', result)
    
    def _handle_confirmed_state(self):
        """Handle CONFIRMED state: check confluence and generate signal"""
        # First check confluence
        conf_result = self.signal_service.check_confluence(self.symbol)
        
        if not conf_result.get('success') or not conf_result.get('confluence_passed'):
            logger.info(f"Confluence check failed: {conf_result}")
            return
            
        # Check for time-boxed retest (3 M5 bars = 15 minutes)
        now = timezone.now()  # Use timezone-aware datetime
        confirmation_time = self.signal_service.current_session.confirmation_time

        # Ensure both datetimes are timezone-aware for comparison
        if confirmation_time:
            if timezone.is_naive(confirmation_time):
                confirmation_time = timezone.make_aware(confirmation_time)

            if (now - confirmation_time) > timedelta(minutes=15):
                logger.info("Retest window expired (15 minutes). Entering cooldown.")
                self.signal_service.current_session.current_state = 'COOLDOWN'
                self.signal_service.current_session.save()
                self._log_system_event("RETEST_EXPIRED", "Retest window expired. Entering cooldown.")
                return
            
        # Check for retest of entry zone
        asian_mid = float(self.signal_service.current_session.asian_range_midpoint)

        # Try to get M5 data with fallback strategies
        m5_data = None
        for attempt in range(3):  # Try 3 times with different time ranges
            time_range = 20 + (attempt * 10)  # 20, 30, 40 minutes
            m5_data = self.mt5_service.get_historical_data(self.symbol, 'M5', now - timedelta(minutes=time_range), now)
            if m5_data is not None and len(m5_data) > 0:
                break

        if m5_data is None or len(m5_data) == 0:
            # Check if it's weekend or market closed
            if now.weekday() >= 5:  # Weekend
                logger.debug("No M5 data available - Market closed (Weekend)")
            else:
                logger.warning("No M5 data available for retest check - Market may be closed or connection issue")
            return
            
        # Define retest band (midpoint ± 5 pips)
        pip = 0.1  # For XAUUSD
        band = 5 * pip
        touched = ((m5_data['low'] <= asian_mid + band) & (m5_data['high'] >= asian_mid - band)).any()
        
        if not touched:
            # Still waiting for retest
            return
            
        # Generate signal once retest touched
        signal_result = self.signal_service.generate_trade_signal(self.symbol)
        
        if signal_result.get('success'):
            logger.info(f"Trade signal generated: {signal_result}")
            self._log_system_event("SIGNAL_GENERATED", f"Trade signal generated: {signal_result.get('signal_type')} at {signal_result.get('entry_price')}")
            
            # Call GPT for entry/SL/TP validation
            self._call_gpt_for_validation('ARMED', signal_result)
            
            # Double-check confluence right before arming
            conf2 = self.signal_service.check_confluence(self.symbol)
            if not conf2.get('confluence_passed'):
                logger.warning(f"Confluence failed at arming: {conf2}")
                return
    
    def _handle_armed_state(self):
        """Handle ARMED state: execute trade"""
        # Only execute trades during Asian session
        if not self._is_asian_session():
            logger.info("Trade signal ready but outside Asian session hours. Waiting for Asian session.")
            self._log_system_event("TRADE_DELAYED", "Trade execution delayed - outside Asian session hours")
            return
            
        # Calculate position size based on risk management
        position_size = self._calculate_position_size()
        if position_size <= 0:
            logger.warning("Calculated position size too small, skipping trade")
            self._log_system_event("TRADE_SKIPPED", "Position size too small based on risk calculation")
            return
            
        # Execute the trade with calculated position size
        result = self.signal_service.execute_trade(self.symbol, volume=position_size)
        
        if result.get('success'):
            logger.info(f"Trade executed: {result} with position size {position_size}")
            self._log_system_event("TRADE_EXECUTED", f"Trade executed: {result.get('order')} with size {position_size}")
            
            # Update daily trade count
            self.daily_trade_count += 1
            
            # Call GPT for trade management plan
            self._call_gpt_for_validation('IN_TRADE', result)
            
    def _calculate_position_size(self) -> float:
        """Calculate position size based on account balance and risk management"""
        try:
            # Get account info
            account_info = self.mt5_service.get_account_info()
            if not account_info:
                logger.error("Failed to get account info for position sizing")
                return 0.01  # Fallback to minimum size
                
            # Get current signal
            current_session = self.signal_service.current_session
            if not current_session:
                return 0.01
                
            active_signals = TradeSignal.objects.filter(
                session=current_session,
                status="ACTIVE"
            ).order_by('-created_at')
            
            if not active_signals.exists():
                logger.warning("No active signal found for position sizing")
                return 0.01
                
            signal = active_signals.first()
            
            # Calculate risk amount (1% of account balance)
            balance = float(account_info.get('balance', 0))
            risk_percent = 1.0  # 1% risk per trade
            risk_amount = balance * (risk_percent / 100)
            
            # Calculate pip value
            # For XAUUSD, 1 pip is typically 0.1 (not 0.0001 as in forex)
            pip_value = 0.1
            if self.symbol == "XAUUSD":
                # For gold, pip value calculation is different
                # Approximate value: 0.01 lot = ~$1 per 0.1 pip movement
                pip_value_per_lot = 10  # $10 per 0.1 pip for 0.1 lot
            else:
                # For forex pairs, would need different calculation
                pip_value_per_lot = 10  # Default assumption
            
            # Calculate stop loss in pips
            entry = float(signal.entry_price)
            stop_loss = float(signal.stop_loss)
            direction = signal.signal_type
            
            if direction == "BUY":
                sl_pips = (entry - stop_loss) / pip_value
            else:  # SELL
                sl_pips = (stop_loss - entry) / pip_value
                
            if sl_pips <= 0:
                logger.error(f"Invalid stop loss calculation: {sl_pips} pips")
                return 0.01
                
            # Calculate position size
            position_size = risk_amount / (sl_pips * pip_value_per_lot)
            
            # Round to 2 decimal places (standard for MT5)
            position_size = round(position_size, 2)
            
            # Enforce minimum and maximum position sizes
            min_size = 0.01
            max_size = 0.5  # Limit maximum position size
            
            position_size = max(min_size, min(position_size, max_size))
            
            logger.info(f"Calculated position size: {position_size} lots (Risk: ${risk_amount}, SL: {sl_pips} pips)")
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}", exc_info=True)
            return 0.01  # Default to minimum size on error
    
    def _handle_in_trade_state(self):
        """Handle IN_TRADE state: manage trade"""
        result = self.signal_service.manage_in_trade(self.symbol)
        
        # Check if trade is closed
        if result.get('trade_closed'):
            logger.info(f"Trade closed: {result}")
            self._log_system_event("TRADE_CLOSED", f"Trade closed: {result}")
            
            # Update loss counter if needed
            if result.get('profit', 0) < 0:
                self.daily_loss_count += 1
                
            # Move to cooldown state
            self.signal_service.current_session.current_state = 'COOLDOWN'
            self.signal_service.current_session.save()
            
            # Call GPT for trade review
            self._call_gpt_for_validation('COOLDOWN', result)
    
    def _handle_cooldown_state(self):
        """Handle COOLDOWN state: wait for cooldown period then reset"""
        current_session = self.signal_service.current_session
        now = timezone.now()
        
        # Check if cooldown period has elapsed (30 minutes)
        updated_at = current_session.updated_at
        if updated_at:
            if timezone.is_naive(updated_at):
                updated_at = timezone.make_aware(updated_at)

            if (now - updated_at) > timedelta(minutes=30):
                logger.info("Cooldown period complete. Resetting to IDLE.")
                current_session.current_state = 'IDLE'
                current_session.save()
                self._log_system_event("COOLDOWN_COMPLETE", "Cooldown period complete. Reset to IDLE.")
    
    def _call_gpt_for_validation(self, state: str, data: Dict):
        """Call GPT API for validation at key decision points"""
        now = timezone.now()
        
        # Check cooldown to avoid excessive API calls
        if state in self.last_gpt_call_time:
            time_since_last_call = (now - self.last_gpt_call_time[state]).total_seconds()
            if time_since_last_call < self.gpt_cooldown:
                logger.debug(f"Skipping GPT call for {state} (cooldown: {time_since_last_call}s < {self.gpt_cooldown}s)")
                return
        
        # Prepare GPT request based on state
        try:
            # This would be replaced with actual GPT API integration
            logger.info(f"Calling GPT for {state} validation")
            
            # Record this call time
            self.last_gpt_call_time[state] = now
            
            # TODO: Implement actual GPT API call
            # For now, just log that we would make the call
            self._log_system_event("GPT_VALIDATION", f"GPT validation for {state}: {json.dumps(data)[:100]}...")
            
        except Exception as e:
            logger.error(f"Error calling GPT API: {str(e)}", exc_info=True)
            self._log_system_event("ERROR", f"GPT API error: {str(e)}")
    
    def _log_system_event(self, event_type: str, description: str):
        """Log system event to database"""
        try:
            SystemLog.objects.create(
                level='INFO',
                component='auto_trading',
                message=f"{event_type}: {description}",
                timestamp=timezone.now()
            )
        except Exception as e:
            logger.error(f"Error logging system event: {str(e)}")