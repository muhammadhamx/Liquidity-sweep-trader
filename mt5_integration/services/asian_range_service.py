from datetime import datetime, time, timedelta
import pandas as pd
from typing import Dict, Tuple
from .mt5_service import MT5Service

class AsianRangeService:
    def __init__(self, mt5_service: MT5Service):
        self.mt5_service = mt5_service
    
    def calculate_asian_range(self, symbol: str = "XAUUSD") -> Dict:
        """
        Calculate Asian session range with comprehensive data
        """
        print(f"\n{'='*50}")
        print("CALCULATING ASIAN SESSION RANGE")
        print(f"{'='*50}")
        
        # Get Asian session data
        result = self.mt5_service.get_asian_session_data(symbol)
        
        if not result['success']:
            return result
        
        # Get current price for context
        current_price = self.mt5_service.get_current_price(symbol)
        
        # Add additional metrics
        result.update({
            'current_price': current_price,
            'timestamp': datetime.now().isoformat(),
            'analysis': self._generate_analysis(result)
        })
        
        return result
    
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