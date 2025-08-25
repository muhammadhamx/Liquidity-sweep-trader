import MetaTrader5 as mt5
from datetime import datetime
from typing import Dict, Optional, Tuple

class TradeService:
    def __init__(self, mt5_service=None):
        self.mt5_service = mt5_service
        self.connected = False if mt5_service is None else mt5_service.connected
    
    def place_market_order(self, symbol: str, trade_type: str, volume: float, 
                         stop_loss: float = 0.0, take_profit: float = 0.0,
                         deviation: int = 20, comment: str = "API Trade") -> Dict:
        """
        Place a market order
        """
        try:
            # Check connection
            if not self.connected and self.mt5_service:
                self.connected = self.mt5_service.connected
            
            if not self.connected:
                return {
                    'success': False,
                    'error': 'Not connected to MT5',
                    'order_id': None
                }
            
            # Prepare the trade request
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return {
                    'success': False,
                    'error': f"Symbol {symbol} not found",
                    'order_id': None
                }
            
            if not symbol_info.visible:
                return {
                    'success': False,
                    'error': f"Symbol {symbol} is not visible",
                    'order_id': None
                }
            
            # Get current tick data
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {
                    'success': False,
                    'error': f"No tick data available for {symbol}",
                    'order_id': None
                }
            
            # Determine order type and price
            if trade_type.upper() == 'BUY':
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
            elif trade_type.upper() == 'SELL':
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
            else:
                return {
                    'success': False,
                    'error': f"Invalid trade type: {trade_type}",
                    'order_id': None
                }
            
            # Prepare the request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": deviation,
                "magic": 234000,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            # Add stop loss and take profit if provided
            if stop_loss > 0:
                    request["sl"] = stop_loss
            
            if take_profit > 0:
                    request["tp"] = take_profit
            
            # Send the order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'error': f"Order failed: {result.comment} (code: {result.retcode})",
                    'order_id': None,
                    'retcode': result.retcode
                }
            
            return {
                'success': True,
                'order_id': result.order,
                'price': result.price,
                'volume': result.volume,
                'comment': result.comment,
                'retcode': result.retcode
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Exception occurred: {str(e)}",
                'order_id': None
            }
    
    def place_pending_order(self, symbol: str, trade_type: str, volume: float,
                          price: float, stop_loss: float = 0.0, take_profit: float = 0.0,
                          deviation: int = 20, comment: str = "API Pending Order") -> Dict:
        """
        Place a pending order
        """
        try:
            if not self.connected and self.mt5_service:
                self.connected = self.mt5_service.connected
            
            if not self.connected:
                return {
                    'success': False,
                    'error': 'Not connected to MT5',
                    'order_id': None
                }
            
            # Validate symbol
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return {
                    'success': False,
                    'error': f"Symbol {symbol} not found",
                    'order_id': None
                }
            
            # Determine order type
            if trade_type.upper() == 'BUY_LIMIT':
                order_type = mt5.ORDER_TYPE_BUY_LIMIT
            elif trade_type.upper() == 'SELL_LIMIT':
                order_type = mt5.ORDER_TYPE_SELL_LIMIT
            elif trade_type.upper() == 'BUY_STOP':
                order_type = mt5.ORDER_TYPE_BUY_STOP
            elif trade_type.upper() == 'SELL_STOP':
                order_type = mt5.ORDER_TYPE_SELL_STOP
            else:
                return {
                    'success': False,
                    'error': f"Invalid pending order type: {trade_type}",
                    'order_id': None
                }
            
            # Prepare the request
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": deviation,
                "magic": 234000,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            # Add stop loss and take profit if provided
            if stop_loss > 0:
                request["sl"] = stop_loss
            
            if take_profit > 0:
                request["tp"] = take_profit
            
            # Send the order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'error': f"Pending order failed: {result.comment} (code: {result.retcode})",
                    'order_id': None,
                    'retcode': result.retcode
                }
            
            return {
                'success': True,
                'order_id': result.order,
                'price': result.price,
                'volume': result.volume,
                'comment': result.comment,
                'retcode': result.retcode
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Exception occurred: {str(e)}",
                'order_id': None
            }
    
    def modify_order(self, order_id: int, price: float, stop_loss: float = 0.0, 
                    take_profit: float = 0.0) -> Dict:
        """
        Modify an existing order
        """
        try:
            if not self.connected and self.mt5_service:
                self.connected = self.mt5_service.connected
            
            if not self.connected:
                return {
                    'success': False,
                    'error': 'Not connected to MT5'
                }
            
            # Get the order
            orders = mt5.orders_get(ticket=order_id)
            if not orders:
                return {
                    'success': False,
                    'error': f"Order {order_id} not found"
                }
            
            order = orders[0]
            
            # Prepare modification request
            request = {
                "action": mt5.TRADE_ACTION_MODIFY,
                "symbol": order.symbol,
                "volume": order.volume,
                "type": order.type,
                "position": order_id,
                "price": price,
                "deviation": 20,
                "magic": order.magic,
                "comment": order.comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            # Add stop loss and take profit if provided
            if stop_loss > 0:
                request["sl"] = stop_loss
            
            if take_profit > 0:
                request["tp"] = take_profit
            
            # Send the modification
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'error': f"Order modification failed: {result.comment} (code: {result.retcode})"
                }
            
            return {
                'success': True,
                'message': 'Order modified successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Exception occurred: {str(e)}"
            }
    
    def cancel_order(self, order_id: int) -> Dict:
        """
        Cancel a pending order
        """
        try:
            if not self.connected and self.mt5_service:
                self.connected = self.mt5_service.connected
            
            if not self.connected:
                return {
                    'success': False,
                    'error': 'Not connected to MT5'
                }
            
            # Prepare cancellation request
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order_id,
            }
            
            # Send the cancellation
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'error': f"Order cancellation failed: {result.comment} (code: {result.retcode})"
                }
            
            return {
                'success': True,
                'message': 'Order cancelled successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Exception occurred: {str(e)}"
            }
    
    def get_open_positions(self, symbol: Optional[str] = None) -> Dict:
        """Return all open positions, optionally filtered by symbol."""
        try:
            if not self.connected and self.mt5_service:
                self.connected = self.mt5_service.connected
            if not self.connected:
                return {'success': False, 'error': 'Not connected to MT5'}

            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()
            if positions is None:
                return {'success': True, 'positions': []}

            positions_list = []
            for p in positions:
                d = p._asdict()
                positions_list.append({
                    'ticket': d.get('ticket'),
                    'symbol': d.get('symbol'),
                    'type': d.get('type'),
                    'price_open': d.get('price_open'),
                    'price_current': d.get('price_current'),
                    'volume': d.get('volume'),
                    'profit': d.get('profit'),
                    'sl': d.get('sl'),
                    'tp': d.get('tp'),
                    'time': d.get('time'),
                })
            return {'success': True, 'positions': positions_list}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def close_position(self, position_id: int, deviation: int = 20) -> Dict:
        """Close a single open position by sending an opposite market order."""
        try:
            if not self.connected and self.mt5_service:
                self.connected = self.mt5_service.connected
            if not self.connected:
                return {'success': False, 'error': 'Not connected to MT5'}

            positions = mt5.positions_get(ticket=position_id)
            if positions is None or len(positions) == 0:
                return {'success': False, 'error': f'Position {position_id} not found'}
            pos = positions[0]

            symbol = pos.symbol
            volume = pos.volume
            # Determine opposite order type
            if pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid if mt5.symbol_info_tick(symbol) else 0
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask if mt5.symbol_info_tick(symbol) else 0

            if price == 0:
                return {'success': False, 'error': 'No tick price available'}

            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': volume,
                'type': order_type,
                'position': position_id,
                'price': price,
                'deviation': deviation,
                'magic': 234000,
                'comment': 'API Close',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_FOK,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'error': f"Close failed: {result.comment} (code: {result.retcode})", 'retcode': result.retcode}
            return {'success': True, 'message': 'Position closed', 'retcode': result.retcode}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_order_history(self, symbol: str = None, start_date: datetime = None, 
                         end_date: datetime = None) -> Dict:
        """
        Get order history
        """
        try:
            if not self.connected and self.mt5_service:
                self.connected = self.mt5_service.connected
            
            if not self.connected:
                return {
                    'success': False,
                    'error': 'Not connected to MT5',
                    'data': []
                }
            
            # Get history deals
            deals = mt5.history_deals_get(start_date, end_date)
            if deals is None:
                return {
                    'success': True,
                    'data': []
                }
            
            # Filter by symbol if specified
            if symbol:
                deals = [deal for deal in deals if deal.symbol == symbol]
            
            # Convert to list of dictionaries
            deals_data = [deal._asdict() for deal in deals]
            
            return {
                'success': True,
                'data': deals_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Exception occurred: {str(e)}",
                'data': []
            }