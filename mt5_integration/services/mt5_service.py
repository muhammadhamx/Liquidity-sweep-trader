import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time as dt_time, timedelta
import time as time_module
from typing import Dict, Tuple, Optional, Any
import pytz

class MT5Service:
    def __init__(self):
        self.connected = False
        self.account = None
    
    def initialize_mt5(self) -> bool:
        """Initialize MT5 connection with proper error handling"""
        try:
            # First, try to shutdown if already initialized
            try:
                mt5.shutdown()
            except:
                pass
            
            # Initialize MT5 (try default first, then common Windows paths)
            init_ok = mt5.initialize()
            if not init_ok:
                # Try typical installation paths on Windows
                candidate_paths = [
                    r"C:\\Program Files\\MetaTrader 5\\terminal64.exe",
                    r"C:\\Program Files\\MetaTrader 5\\terminal.exe",
                    r"C:\\Program Files (x86)\\MetaTrader 5\\terminal64.exe",
                    r"C:\\Program Files (x86)\\MetaTrader 5\\terminal.exe",
                ]
                for path in candidate_paths:
                    try:
                        if mt5.initialize(path=path):
                            init_ok = True
                            print(f"✅ MT5 initialized using path: {path}")
                            break
                    except Exception:
                        continue
            
            if not init_ok:
                error = mt5.last_error()
                print(f"❌ MT5 initialize failed, error: {error}")
                return False
            
            print("✅ MT5 initialized successfully")
            self.connected = True
            return True
            
        except Exception as e:
            print(f"❌ MT5 initialization error: {e}")
            return False
    
    def connect(self, account: int, password: Optional[str] = None, server: str = "MetaQuotes-Demo") -> Tuple[bool, Optional[int]]:
        """Connect to MT5 account"""
        if not self.connected:
            success = self.initialize_mt5()
            if not success:
                return False, mt5.last_error()
        
        try:
            # Connect to trade account
            if password:
                authorized = mt5.login(login=account, password=password, server=server)
            else:
                authorized = mt5.login(login=account)
            
            if authorized:
                self.account = account
                print(f"✅ Connected to account #{account}")
                return True, None
            else:
                error = mt5.last_error()
                print(f"❌ Login failed, error code: {error}")
                mt5.shutdown()
                return False, error
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False, None
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            self.account = None
            print("✅ Disconnected from MT5")
    
    def get_historical_data(self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime) -> Optional[pd.DataFrame]:
        """Get historical data for specified time period"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return None

        timeframes = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1
        }

        tf = timeframes.get(timeframe.upper(), mt5.TIMEFRAME_M5)

        try:
            # Ensure symbol is selected/visible before fetching rates
            info = mt5.symbol_info(symbol)
            if info is None or not info.visible:
                if not mt5.symbol_select(symbol, True):
                    print(f"❌ Failed to select symbol {symbol}")
                    return None

            # Ensure MT5 receives naive UTC datetimes
            st = start_time.astimezone(pytz.UTC).replace(tzinfo=None) if hasattr(start_time, 'tzinfo') and start_time.tzinfo else start_time
            et = end_time.astimezone(pytz.UTC).replace(tzinfo=None) if hasattr(end_time, 'tzinfo') and end_time.tzinfo else end_time

            # First try copy_rates_range
            rates = mt5.copy_rates_range(symbol, tf, st, et)

            # If no data, try alternative method with copy_rates_from_pos
            if rates is None or len(rates) == 0:
                # Calculate how many bars we need (approximate)
                time_diff = et - st
                if timeframe.upper() == 'M1':
                    bars_needed = int(time_diff.total_seconds() / 60) + 10
                elif timeframe.upper() == 'M5':
                    bars_needed = int(time_diff.total_seconds() / 300) + 10
                elif timeframe.upper() == 'H1':
                    bars_needed = int(time_diff.total_seconds() / 3600) + 5
                else:
                    bars_needed = 100

                # Limit to reasonable number
                bars_needed = min(bars_needed, 1000)

                # Try getting recent data
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars_needed)

                if rates is not None and len(rates) > 0:
                    # Filter to requested time range
                    df_temp = pd.DataFrame(rates)
                    df_temp['time'] = pd.to_datetime(df_temp['time'], unit='s')

                    # Convert start/end times to pandas datetime for comparison
                    start_pd = pd.to_datetime(st)
                    end_pd = pd.to_datetime(et)

                    # Filter by time range
                    mask = (df_temp['time'] >= start_pd) & (df_temp['time'] <= end_pd)
                    rates_filtered = df_temp[mask]

                    if len(rates_filtered) > 0:
                        return rates_filtered.reset_index(drop=True)

            if rates is None or len(rates) == 0:
                # Check if market is closed
                current_time = datetime.utcnow()
                if current_time.weekday() >= 5:  # Weekend
                    print(f"📅 Market closed (Weekend) - No {symbol} {timeframe} data available")
                else:
                    print(f"⚠️ No data returned for {symbol} {timeframe} (Market may be closed or no data in range)")
                return None

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df

        except Exception as e:
            print(f"❌ Error fetching historical data for {symbol} {timeframe}: {e}")
            return None
    
    def get_asian_session_data(self, symbol: str = "XAUUSD") -> Dict:
        """
        Calculate Asian session data (00:00-06:00 UTC)
        Returns: high, low, midpoint, range_size, grade, risk_multiplier
        """
        print(f"\n{'='*50}")
        print("CALCULATING ASIAN SESSION RANGE")
        print(f"{'='*50}")
        
        try:
            # Calculate UTC window for today
            now_utc = datetime.utcnow()
            today_utc = now_utc.date()
            start_time = datetime.combine(today_utc, dt_time(0, 0))   # 00:00 UTC
            end_time = datetime.combine(today_utc, dt_time(6, 0))     # 06:00 UTC
            
            print(f"📅 Fetching Asian session data for {symbol}")
            print(f"⏰ Time range (UTC): {start_time} to {end_time}")
            
            # Get M5 data for Asian session
            df = self.get_historical_data(symbol, "M5", start_time, end_time)
            
            if df is None or len(df) == 0:
                print("⚠️ No data available for Asian session")
                return {
                    'success': False,
                    'error': 'No data available for Asian session',
                    'symbol': symbol
                }
            
            # Calculate Asian range
            high = df['high'].max()
            low = df['low'].min()
            midpoint = (high + low) / 2
            range_pips = round((high - low) * 10, 1)  # XAUUSD: 1 pip = 0.1
            
            # Apply grading logic
            grade, risk_multiplier = self._grade_range(range_pips)
            
            print(f"✅ Asian range calculated: {range_pips}pips ({grade})")
            
            return {
                'success': True,
                'symbol': symbol,
                'high': high,
                'low': low,
                'midpoint': midpoint,
                'range_pips': range_pips,
                'grade': grade,
                'risk_multiplier': risk_multiplier,
                'start_time': start_time,
                'end_time': end_time,
                'timezone': 'UTC',
                'data_points': len(df)
            }
            
        except Exception as e:
            print(f"❌ Error in get_asian_session_data: {e}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol
            }
    
    def _grade_range(self, range_pips: float) -> Tuple[str, float]:
        """Grade the Asian range and determine risk multiplier"""
        if range_pips < 30:
            return "TIGHT", 0.5  # half risk
        elif 30 <= range_pips <= 150:
            return "NORMAL", 1.0  # full risk
        else:
            return "WIDE", 1.0  # full risk but modified targets
    
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """Get current price for a symbol"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return None
        
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                print(f"❌ Symbol {symbol} not found in Market Watch. Attempting to select...")
                if not mt5.symbol_select(symbol, True):
                    print(f"❌ Unable to select symbol {symbol}.")
                    return None
                info = mt5.symbol_info(symbol)
                if info is None:
                    return None
            if not info.visible:
                # Try to make the symbol visible
                if not mt5.symbol_select(symbol, True):
                    print(f"❌ Symbol {symbol} is not visible and could not be selected.")
                    return None
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"⚠️ No tick data for {symbol}. Market may be closed or no data available.")
                return None
            return {
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'last': tick.last,
                'volume': tick.volume,
                'time': pd.to_datetime(tick.time, unit='s').isoformat()
            }
        except Exception as e:
            print(f"❌ Error getting current price: {e}")
            return None
    
    def get_account_info(self):
        """Get account information"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return None
        
        try:
            account_info = mt5.account_info()
            if account_info is None:
                print("⚠️ No account info available")
                return None
            
            return account_info._asdict()
            
        except Exception as e:
            print(f"❌ Error getting account info: {e}")
            return None
    
    def get_symbols(self):
        """Get all available symbols"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return []
        
        try:
            symbols = mt5.symbols_get()
            if symbols is None:
                print("⚠️ No symbols available")
                return []
            
            return [symbol.name for symbol in symbols]
            
        except Exception as e:
            print(f"❌ Error getting symbols: {e}")
            return []
    
    def get_rates(self, symbol: str, timeframe: str, count: int = 100):
        """Get historical rates for a symbol"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return None
        
        try:
            timeframes = {
                'M1': mt5.TIMEFRAME_M1,
                'M5': mt5.TIMEFRAME_M5,
                'M15': mt5.TIMEFRAME_M15,
                'H1': mt5.TIMEFRAME_H1,
                'H4': mt5.TIMEFRAME_H4,
                'D1': mt5.TIMEFRAME_D1
            }
            
            tf = timeframes.get(timeframe.upper(), mt5.TIMEFRAME_M5)
            
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None or len(rates) == 0:
                print(f"⚠️ No data returned for {symbol} {timeframe}")
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df.to_dict('records')
            
        except Exception as e:
            print(f"❌ Error getting rates: {e}")
            return None
    
    def get_open_orders(self):
        """Get all open orders"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return []
        
        try:
            orders = mt5.orders_get()
            if orders is None:
                return []
            
            return [order._asdict() for order in orders]
            
        except Exception as e:
            print(f"❌ Error getting open orders: {e}")
            return []
    
    def get_positions(self):
        """Get all open positions"""
        if not self.connected:
            print("❌ Not connected to MT5")
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            return [position._asdict() for position in positions]
            
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            return []
    
    def close_position(self, position_id: int):
        """Close a specific position"""
        if not self.connected:
            return {'success': False, 'error': 'Not connected to MT5'}
        
        try:
            position = mt5.positions_get(ticket=position_id)
            if not position:
                return {'success': False, 'error': 'Position not found'}
            
            position = position[0]
            
            # Prepare close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": position_id,
                "price": mt5.symbol_info_tick(position.symbol).bid if position.type == 0 else mt5.symbol_info_tick(position.symbol).ask,
                "deviation": 20,
                "magic": 234000,
                "comment": "API Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'error': f"Close failed: {result.comment} (code: {result.retcode})"
                }
            
            return {'success': True, 'message': 'Position closed successfully'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def close_all_positions(self):
        """Close all open positions"""
        if not self.connected:
            return {'success': False, 'error': 'Not connected to MT5'}
        
        try:
            positions = mt5.positions_get()
            if not positions:
                return {'success': True, 'message': 'No positions to close'}
            
            closed_count = 0
            errors = []
            
            for position in positions:
                result = self.close_position(position.ticket)
                if result['success']:
                    closed_count += 1
                else:
                    errors.append(f"Position {position.ticket}: {result['error']}")
            
            return {
                'success': True,
                'closed_count': closed_count,
                'total_positions': len(positions),
                'errors': errors
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_server_time(self):
        """Get server time"""
        if not self.connected:
            return None
        
        try:
            server_time = mt5.symbol_info_tick("EURUSD")
            if server_time:
                return pd.to_datetime(server_time.time, unit='s').isoformat()
            return None
        except:
            return None
    
    def get_symbol_info(self, symbol: str):
        """Get symbol information"""
        if not self.connected:
            return None
        
        try:
            info = mt5.symbol_info(symbol)
            if info:
                return info._asdict()
            return None
        except:
            return None
    
    def get_mt5_version(self):
        """Get MT5 version"""
        try:
            return mt5.version()
        except:
            return None
    
    def get_error_description(self, error_code):
        """Get human-readable error description"""
        error_descriptions = {
            1: "General error",
            10013: "Invalid account",
            10015: "Invalid password", 
            10016: "Invalid server",
            10021: "Not connected",
            10027: "Timeout",
            10028: "Invalid parameters",
            10029: "No history data",
            10030: "Not enough memory"
        }
        return error_descriptions.get(error_code, f"Unknown error: {error_code}")
 