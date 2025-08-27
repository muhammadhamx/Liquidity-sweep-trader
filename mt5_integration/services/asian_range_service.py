from datetime import datetime, time, timedelta
from django.utils import timezone
import pandas as pd
from typing import Dict, Tuple, Any
import logging
# Import the base class, not the specific implementation
# This allows us to work with either MT5Service or MockMT5Service

logger = logging.getLogger('api_requests')

class AsianRangeService:
    def __init__(self, mt5_service: Any):
        self.mt5_service = mt5_service
    
    def calculate_asian_range(self, symbol: str = "XAUUSD") -> Dict:
        """
        Calculate Asian session range with comprehensive data
        """
        logger.info(f"Calculating Asian range for {symbol}")
        
        # Get Asian session data
        result = self.mt5_service.get_asian_session_data(symbol)
        
        if not result or not result.get('success', False):
            logger.warning(f"Failed to get Asian session data for {symbol}: {result.get('error', 'Unknown error')}")
            return result if result else {'success': False, 'error': 'Failed to get Asian session data'}
        
        try:
            # Get current price for context
            current_price = 0
            try:
                # Try to get current price if the method exists
                if hasattr(self.mt5_service, 'get_current_price'):
                    current_price = self.mt5_service.get_current_price(symbol)
                else:
                    # Fallback to get_symbol_info_tick if available
                    tick_info = self.mt5_service.get_symbol_info_tick(symbol)
                    if tick_info and 'bid' in tick_info:
                        current_price = tick_info['bid']
            except Exception as e:
                logger.warning(f"Error getting current price: {str(e)}")
                current_price = result.get('midpoint', 0)  # Fallback to midpoint
            
            # Add additional metrics
            result.update({
                'current_price': current_price,
                'timestamp': timezone.now().isoformat(),
                'timezone': 'UTC',
                'analysis': self._generate_analysis(result)
            })
            
            logger.info(f"Asian range calculation successful: {result}")
            return result
        except Exception as e:
            logger.error(f"Error in calculate_asian_range: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Error calculating Asian range: {str(e)}'}
    
    def _generate_analysis(self, range_data: Dict) -> str:
        """Generate analysis text based on range data"""
        grade = range_data['grade']
        range_pips = range_data['range_pips']
        
        if grade == "TIGHT":
            return f"Tight range ({range_pips} pips). Consider half risk (0.5%) and require extra confirmation. May need M5 mini-BOS."
        elif grade == "NORMAL":
            return f"Normal range ({range_pips} pips). Standard risk (1%) applies. Good trading conditions."
        else:
            return f"Wide range ({range_pips} pips). Need HTF confluence and moderated targets. Standard risk but careful position sizing."
    
    def format_range_output(self, range_data: Dict) -> str:
        """Format the range data for display"""
        if not range_data['success']:
            return "❌ Error: No Asian session data available"
        
        output = [
            f"\n📊 ASIAN SESSION ANALYSIS - {range_data['symbol']}",
            f"{'='*40}",
            f"📍 High: {range_data['high']:.2f}",
            f"📍 Low: {range_data['low']:.2f}",
            f"📍 Midpoint: {range_data['midpoint']:.2f}",
            f"📍 Range: {range_data['range_pips']} pips",
            f"📈 Grade: {range_data['grade']}",
            f"🎯 Risk Multiplier: {range_data['risk_multiplier']}",
            f"📅 Session: {range_data['start_time'].strftime('%H:%M')} - {range_data['end_time'].strftime('%H:%M')} UTC+3",
            f"📊 Data Points: {range_data['data_points']}",
            f"💡 Analysis: {range_data['analysis']}",
            f"{'='*40}"
        ]
        
        return "\n".join(output)