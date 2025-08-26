import requests
import json
import logging
from datetime import datetime
from django.utils import timezone
from typing import Dict, Optional, List, Any
from ..models import GPTAnalysis, TradeSignal, TradingSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("gpt_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("gpt_service")

class GPTService:
    """
    Service for integrating with GPT API at key decision points in the trading workflow.
    Designed to minimize token usage by only calling at critical state transitions.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key
        self.api_url = api_url or "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4"  # Default model
        
    def validate_sweep(self, session_data: Dict, market_data: Dict) -> Dict:
        """
        Validate a detected sweep and get a second opinion on go/no-go decision.
        Called at SWEPT state transition.
        
        Args:
            session_data: Current trading session data including Asian range
            market_data: Current market data including sweep details
            
        Returns:
            Dict with validation result and reasoning
        """
        # Prepare prompt with structured data
        prompt = self._create_sweep_prompt(session_data, market_data)
        
        # Call GPT API
        response = self._call_gpt_api(prompt)
        
        # Parse and store response
        result = self._parse_sweep_response(response)
        
        # Store analysis in database
        self._store_analysis(
            analysis_type="SWEEP_VALIDATION",
            session_id=session_data.get('session_id'),
            prompt=prompt,
            response=response,
            result=result
        )
        
        return result
    
    def validate_reversal(self, session_data: Dict, market_data: Dict) -> Dict:
        """
        Validate a confirmed reversal and get exact entry, SL, TP zones.
        Called at CONFIRMED state transition.
        
        Args:
            session_data: Current trading session data
            market_data: Current market data including reversal details
            
        Returns:
            Dict with validation result and trade parameters
        """
        # Prepare prompt with structured data
        prompt = self._create_reversal_prompt(session_data, market_data)
        
        # Call GPT API
        response = self._call_gpt_api(prompt)
        
        # Parse and store response
        result = self._parse_reversal_response(response)
        
        # Store analysis in database
        self._store_analysis(
            analysis_type="REVERSAL_VALIDATION",
            session_id=session_data.get('session_id'),
            prompt=prompt,
            response=response,
            result=result
        )
        
        return result
    
    def validate_signal(self, session_data: Dict, signal_data: Dict) -> Dict:
        """
        Validate a generated trade signal and refine entry, SL, TP levels.
        Called at ARMED state transition.
        
        Args:
            session_data: Current trading session data
            signal_data: Generated trade signal data
            
        Returns:
            Dict with validation result and refined trade parameters
        """
        # Prepare prompt with structured data
        prompt = self._create_signal_prompt(session_data, signal_data)
        
        # Call GPT API
        response = self._call_gpt_api(prompt)
        
        # Parse and store response
        result = self._parse_signal_response(response)
        
        # Store analysis in database
        self._store_analysis(
            analysis_type="SIGNAL_VALIDATION",
            session_id=session_data.get('session_id'),
            prompt=prompt,
            response=response,
            result=result
        )
        
        return result
    
    def get_trade_management(self, session_data: Dict, trade_data: Dict) -> Dict:
        """
        Get trade management recommendations at key points (+0.5R, near timeout).
        Called during IN_TRADE state.
        
        Args:
            session_data: Current trading session data
            trade_data: Current trade data including profit/loss
            
        Returns:
            Dict with management recommendations
        """
        # Prepare prompt with structured data
        prompt = self._create_management_prompt(session_data, trade_data)
        
        # Call GPT API
        response = self._call_gpt_api(prompt)
        
        # Parse and store response
        result = self._parse_management_response(response)
        
        # Store analysis in database
        self._store_analysis(
            analysis_type="TRADE_MANAGEMENT",
            session_id=session_data.get('session_id'),
            prompt=prompt,
            response=response,
            result=result
        )
        
        return result
    
    def get_trade_review(self, session_data: Dict, trade_data: Dict) -> Dict:
        """
        Get a review of a completed trade with lessons learned.
        Called at COOLDOWN state transition.
        
        Args:
            session_data: Current trading session data
            trade_data: Completed trade data including profit/loss
            
        Returns:
            Dict with trade review and lessons learned
        """
        # Prepare prompt with structured data
        prompt = self._create_review_prompt(session_data, trade_data)
        
        # Call GPT API
        response = self._call_gpt_api(prompt)
        
        # Parse and store response
        result = self._parse_review_response(response)
        
        # Store analysis in database
        self._store_analysis(
            analysis_type="TRADE_REVIEW",
            session_id=session_data.get('session_id'),
            prompt=prompt,
            response=response,
            result=result
        )
        
        return result
    
    def _call_gpt_api(self, prompt: str) -> str:
        """
        Call GPT API with the given prompt.
        
        Args:
            prompt: The prompt to send to GPT
            
        Returns:
            The response from GPT
        """
        try:
            # For now, simulate API call to avoid actual costs during development
            logger.info(f"Would call GPT API with prompt: {prompt[:100]}...")
            
            # In production, uncomment this code to make actual API calls
            """
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a professional forex trading assistant specializing in XAU/USD analysis."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(data)
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"GPT API error: {response.status_code} - {response.text}")
                return f"API Error: {response.status_code}"
            """
            
            # Simulated response for development
            return f"Simulated GPT response for: {prompt[:50]}..."
            
        except Exception as e:
            logger.error(f"Error calling GPT API: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"
    
    def _store_analysis(self, analysis_type: str, session_id: int, prompt: str, response: str, result: Dict) -> None:
        """
        Store GPT analysis in database.
        
        Args:
            analysis_type: Type of analysis (SWEEP_VALIDATION, REVERSAL_VALIDATION, etc.)
            session_id: ID of the trading session
            prompt: The prompt sent to GPT
            response: The raw response from GPT
            result: The parsed result
        """
        try:
            session = TradingSession.objects.get(id=session_id)
            
            GPTAnalysis.objects.create(
                session=session,
                analysis_type=analysis_type,
                prompt=prompt,
                response=response,
                result_json=json.dumps(result),
                created_at=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Error storing GPT analysis: {str(e)}", exc_info=True)
    
    def _create_sweep_prompt(self, session_data: Dict, market_data: Dict) -> str:
        """Create prompt for sweep validation"""
        asian_high = session_data.get('asian_range_high', 'N/A')
        asian_low = session_data.get('asian_range_low', 'N/A')
        asian_mid = session_data.get('asian_range_midpoint', 'N/A')
        range_size = session_data.get('asian_range_size', 'N/A')
        range_grade = session_data.get('asian_range_grade', 'N/A')
        
        sweep_direction = market_data.get('sweep_direction', 'N/A')
        sweep_price = market_data.get('sweep_price', 'N/A')
        current_price = market_data.get('current_price', 'N/A')
        
        prompt = f"""
        As a professional XAU/USD trading advisor, validate this Asian session liquidity sweep:
        
        ASIAN RANGE DATA:
        - High: {asian_high}
        - Low: {asian_low}
        - Midpoint: {asian_mid}
        - Range Size: {range_size} pips
        - Grade: {range_grade}
        
        SWEEP DETAILS:
        - Direction: {sweep_direction}
        - Sweep Price: {sweep_price}
        - Current Price: {current_price}
        - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
        
        VALIDATION TASK:
        1. Confirm if this is a valid liquidity sweep beyond the Asian range
        2. Assess the quality of this setup (HIGH/MEDIUM/LOW)
        3. Provide a go/no-go recommendation with brief reasoning
        4. If no-go, explain specific concerns
        
        Format your response as JSON:
        {{
            "is_valid_sweep": true/false,
            "quality": "HIGH/MEDIUM/LOW",
            "recommendation": "GO/NO_GO",
            "reasoning": "brief explanation",
            "concerns": ["concern1", "concern2"] or []
        }}
        """
        
        return prompt
    
    def _parse_sweep_response(self, response: str) -> Dict:
        """Parse GPT response for sweep validation"""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                return result
            
            # Fallback if JSON parsing fails
            return {
                "is_valid_sweep": True,  # Default to true to avoid blocking trades
                "quality": "MEDIUM",
                "recommendation": "GO",
                "reasoning": "Default reasoning (JSON parsing failed)",
                "concerns": ["GPT response parsing failed"]
            }
            
        except Exception as e:
            logger.error(f"Error parsing sweep response: {str(e)}", exc_info=True)
            return {
                "is_valid_sweep": True,  # Default to true to avoid blocking trades
                "quality": "MEDIUM",
                "recommendation": "GO",
                "reasoning": f"Default reasoning (Error: {str(e)})",
                "concerns": ["GPT response parsing failed"]
            }
    
    def _create_reversal_prompt(self, session_data: Dict, market_data: Dict) -> str:
        """Create prompt for reversal validation"""
        asian_high = session_data.get('asian_range_high', 'N/A')
        asian_low = session_data.get('asian_range_low', 'N/A')
        asian_mid = session_data.get('asian_range_midpoint', 'N/A')
        range_size = session_data.get('asian_range_size', 'N/A')
        
        sweep_direction = market_data.get('sweep_direction', 'N/A')
        sweep_price = market_data.get('sweep_price', 'N/A')
        current_price = market_data.get('current_price', 'N/A')
        
        prompt = f"""
        As a professional XAU/USD trading advisor, validate this reversal after an Asian session liquidity sweep:
        
        ASIAN RANGE DATA:
        - High: {asian_high}
        - Low: {asian_low}
        - Midpoint: {asian_mid}
        - Range Size: {range_size} pips
        
        SWEEP & REVERSAL DETAILS:
        - Sweep Direction: {sweep_direction}
        - Sweep Price: {sweep_price}
        - Current Price: {current_price}
        - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
        
        VALIDATION TASK:
        1. Confirm if this is a valid reversal back into the Asian range
        2. Provide exact entry, stop loss, and take profit levels
        3. Calculate risk-to-reward ratio
        4. Provide a confidence score (1-10)
        
        Format your response as JSON:
        {{
            "is_valid_reversal": true/false,
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "take_profit1": 0.0,
            "take_profit2": 0.0,
            "risk_reward_ratio": 0.0,
            "confidence": 0,
            "reasoning": "brief explanation"
        }}
        """
        
        return prompt
    
    def _parse_reversal_response(self, response: str) -> Dict:
        """Parse GPT response for reversal validation"""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                return result
            
            # Fallback if JSON parsing fails
            return {
                "is_valid_reversal": True,  # Default to true to avoid blocking trades
                "entry_price": None,  # Will use system-calculated values
                "stop_loss": None,
                "take_profit1": None,
                "take_profit2": None,
                "risk_reward_ratio": 0.0,
                "confidence": 5,
                "reasoning": "Default reasoning (JSON parsing failed)"
            }
            
        except Exception as e:
            logger.error(f"Error parsing reversal response: {str(e)}", exc_info=True)
            return {
                "is_valid_reversal": True,
                "entry_price": None,
                "stop_loss": None,
                "take_profit1": None,
                "take_profit2": None,
                "risk_reward_ratio": 0.0,
                "confidence": 5,
                "reasoning": f"Default reasoning (Error: {str(e)})"
            }
    
    def _create_signal_prompt(self, session_data: Dict, signal_data: Dict) -> str:
        """Create prompt for signal validation"""
        signal_type = signal_data.get('signal_type', 'N/A')
        entry_price = signal_data.get('entry_price', 'N/A')
        stop_loss = signal_data.get('stop_loss', 'N/A')
        take_profit1 = signal_data.get('take_profit1', 'N/A')
        take_profit2 = signal_data.get('take_profit2', 'N/A')
        risk_pips = signal_data.get('risk_pips', 'N/A')
        reward_pips = signal_data.get('reward_pips', 'N/A')
        
        prompt = f"""
        As a professional XAU/USD trading advisor, validate and refine this trade signal:
        
        TRADE SIGNAL:
        - Direction: {signal_type}
        - Entry Price: {entry_price}
        - Stop Loss: {stop_loss}
        - Take Profit 1: {take_profit1}
        - Take Profit 2: {take_profit2}
        - Risk (pips): {risk_pips}
        - Reward (pips): {reward_pips}
        - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
        
        VALIDATION TASK:
        1. Validate the trade parameters
        2. Suggest any refinements to entry, SL, or TP levels
        3. Provide a professional trade recommendation
        4. Suggest a position sizing strategy (% risk)
        
        Format your response as JSON:
        {{
            "is_valid_signal": true/false,
            "refined_entry": 0.0,
            "refined_sl": 0.0,
            "refined_tp1": 0.0,
            "refined_tp2": 0.0,
            "risk_percentage": 0.0,
            "trade_recommendation": "professional trade recommendation",
            "management_plan": "brief management plan"
        }}
        """
        
        return prompt
    
    def _parse_signal_response(self, response: str) -> Dict:
        """Parse GPT response for signal validation"""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                return result
            
            # Fallback if JSON parsing fails
            return {
                "is_valid_signal": True,  # Default to true to avoid blocking trades
                "refined_entry": None,  # Will use system-calculated values
                "refined_sl": None,
                "refined_tp1": None,
                "refined_tp2": None,
                "risk_percentage": 1.0,  # Default 1% risk
                "trade_recommendation": "System-generated trade (GPT parsing failed)",
                "management_plan": "Move to breakeven at +0.5R, trail stop at +1R"
            }
            
        except Exception as e:
            logger.error(f"Error parsing signal response: {str(e)}", exc_info=True)
            return {
                "is_valid_signal": True,
                "refined_entry": None,
                "refined_sl": None,
                "refined_tp1": None,
                "refined_tp2": None,
                "risk_percentage": 1.0,
                "trade_recommendation": f"System-generated trade (Error: {str(e)})",
                "management_plan": "Move to breakeven at +0.5R, trail stop at +1R"
            }
    
    def _create_management_prompt(self, session_data: Dict, trade_data: Dict) -> str:
        """Create prompt for trade management"""
        signal_type = trade_data.get('signal_type', 'N/A')
        entry_price = trade_data.get('entry_price', 'N/A')
        current_price = trade_data.get('current_price', 'N/A')
        current_sl = trade_data.get('current_sl', 'N/A')
        current_tp = trade_data.get('current_tp', 'N/A')
        current_r = trade_data.get('current_r', 'N/A')
        time_in_trade = trade_data.get('time_in_trade', 'N/A')
        
        prompt = f"""
        As a professional XAU/USD trading advisor, provide management advice for this active trade:
        
        TRADE DETAILS:
        - Direction: {signal_type}
        - Entry Price: {entry_price}
        - Current Price: {current_price}
        - Current Stop Loss: {current_sl}
        - Current Take Profit: {current_tp}
        - Current Profit/Loss: {current_r}R
        - Time in Trade: {time_in_trade} minutes
        - Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
        
        MANAGEMENT TASK:
        1. Assess the current trade status
        2. Recommend any stop loss adjustments
        3. Suggest partial profit taking if appropriate
        4. Provide a hold/exit recommendation
        
        Format your response as JSON:
        {{
            "trade_status": "WINNING/LOSING/BREAKEVEN",
            "adjust_sl": true/false,
            "new_sl": 0.0,
            "take_partial": true/false,
            "partial_percentage": 0.0,
            "recommendation": "HOLD/EXIT",
            "reasoning": "brief explanation"
        }}
        """
        
        return prompt
    
    def _parse_management_response(self, response: str) -> Dict:
        """Parse GPT response for trade management"""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                return result
            
            # Fallback if JSON parsing fails
            return {
                "trade_status": "UNKNOWN",
                "adjust_sl": False,
                "new_sl": None,
                "take_partial": False,
                "partial_percentage": 0.0,
                "recommendation": "HOLD",
                "reasoning": "Default management (GPT parsing failed)"
            }
            
        except Exception as e:
            logger.error(f"Error parsing management response: {str(e)}", exc_info=True)
            return {
                "trade_status": "UNKNOWN",
                "adjust_sl": False,
                "new_sl": None,
                "take_partial": False,
                "partial_percentage": 0.0,
                "recommendation": "HOLD",
                "reasoning": f"Default management (Error: {str(e)})"
            }
    
    def _create_review_prompt(self, session_data: Dict, trade_data: Dict) -> str:
        """Create prompt for trade review"""
        signal_type = trade_data.get('signal_type', 'N/A')
        entry_price = trade_data.get('entry_price', 'N/A')
        exit_price = trade_data.get('exit_price', 'N/A')
        sl = trade_data.get('stop_loss', 'N/A')
        tp = trade_data.get('take_profit', 'N/A')
        profit_loss = trade_data.get('profit_loss', 'N/A')
        profit_r = trade_data.get('profit_r', 'N/A')
        time_in_trade = trade_data.get('time_in_trade', 'N/A')
        exit_reason = trade_data.get('exit_reason', 'N/A')
        
        prompt = f"""
        As a professional XAU/USD trading advisor, review this completed trade:
        
        TRADE DETAILS:
        - Direction: {signal_type}
        - Entry Price: {entry_price}
        - Exit Price: {exit_price}
        - Stop Loss: {sl}
        - Take Profit: {tp}
        - Profit/Loss: {profit_loss} ({profit_r}R)
        - Time in Trade: {time_in_trade} minutes
        - Exit Reason: {exit_reason}
        
        REVIEW TASK:
        1. Evaluate the trade execution
        2. Identify what went well
        3. Identify what could be improved
        4. Provide lessons learned
        5. Suggest adjustments for future trades
        
        Format your response as JSON:
        {{
            "trade_rating": 1-10,
            "strengths": ["strength1", "strength2"],
            "weaknesses": ["weakness1", "weakness2"],
            "lessons_learned": ["lesson1", "lesson2"],
            "future_adjustments": ["adjustment1", "adjustment2"],
            "summary": "brief summary"
        }}
        """
        
        return prompt
    
    def _parse_review_response(self, response: str) -> Dict:
        """Parse GPT response for trade review"""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                return result
            
            # Fallback if JSON parsing fails
            return {
                "trade_rating": 5,
                "strengths": ["Followed system rules"],
                "weaknesses": ["GPT review parsing failed"],
                "lessons_learned": ["Continue following system rules"],
                "future_adjustments": ["Monitor system performance"],
                "summary": "Trade executed according to system rules"
            }
            
        except Exception as e:
            logger.error(f"Error parsing review response: {str(e)}", exc_info=True)
            return {
                "trade_rating": 5,
                "strengths": ["Followed system rules"],
                "weaknesses": [f"GPT review error: {str(e)}"],
                "lessons_learned": ["Continue following system rules"],
                "future_adjustments": ["Monitor system performance"],
                "summary": "Trade executed according to system rules"
            }