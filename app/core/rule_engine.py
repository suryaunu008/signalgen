"""
Rule Engine Module

This module provides deterministic rule evaluation logic for the SignalGen scalping system.
It evaluates user-defined rules against indicator values to determine trading signals.

Key Features:
- Evaluates rules with logical operators (AND)
- Supports comparison operators (>, <, >=, <=)
- Works with predefined operands (PRICE, MA5, MA10, MA20)
- Stateless evaluation - state is managed by the calling engine
- No dynamic code execution or eval() usage for security

Typical Usage:
    rule_engine = RuleEngine()
    result = rule_engine.evaluate(rule, indicator_values)
    if result:
        # Generate trading signal
        pass

MVP Limitations:
- No dynamic code execution or eval() usage
- Fixed set of supported operands and operators
- Single rule evaluation (no multi-rule support)
- Only AND logic is supported (no OR logic)
"""

import json
import logging
from typing import Dict, Any, List, Union

logger = logging.getLogger(__name__)

class RuleValidationError(Exception):
    """Exception raised when rule validation fails."""
    pass

class RuleEvaluationError(Exception):
    """Exception raised when rule evaluation fails."""
    pass

class RuleEngine:
    """
    Deterministic rule evaluation engine for trading signals.
    
    This class evaluates user-defined trading rules against current indicator values
    without using dynamic code execution for security and performance.
    """
    
    # Supported operands for rule conditions
    SUPPORTED_OPERANDS = {
        # Price indicators
        "PRICE",                    # Current price
        "PREV_CLOSE",              # Previous candle close
        "PREV_OPEN",               # Previous candle open
        
        # Moving Averages (Simple MA)
        "MA20", "MA50", "MA100", "MA200",  # 20, 50, 100, 200 period Simple Moving Averages
        "MA20_PREV", "MA50_PREV", "MA100_PREV", "MA200_PREV",  # Previous MA values
        
        # Exponential Moving Averages
        "EMA6", "EMA9", "EMA10", "EMA13", "EMA20", "EMA21", "EMA34", "EMA50",  # EMA periods
        "EMA6_PREV", "EMA9_PREV", "EMA10_PREV", "EMA13_PREV", "EMA20_PREV", "EMA21_PREV", "EMA34_PREV", "EMA50_PREV",  # Previous EMA values
        
        # MACD (Moving Average Convergence Divergence)
        "MACD",                    # MACD line (fast EMA - slow EMA)
        "MACD_SIGNAL",             # MACD signal line
        "MACD_HIST",               # MACD histogram current value
        "MACD_HIST_PREV",          # MACD histogram previous value
        "MACD_PREV",               # Previous MACD line
        "MACD_SIGNAL_PREV",        # Previous MACD signal line
        
        # Bollinger Bands
        "BB_UPPER",                # Bollinger Bands upper band
        "BB_MIDDLE",               # Bollinger Bands middle band (SMA)
        "BB_LOWER",                # Bollinger Bands lower band
        "BB_WIDTH",                # Bollinger Bands width (upper - lower)
        "BB_UPPER_PREV", "BB_MIDDLE_PREV", "BB_LOWER_PREV",  # Previous BB values
        
        # ADX (Average Directional Index) - Trend strength
        "ADX5",                    # ADX 5 period current value
        "ADX5_PREV",               # ADX 5 period previous value
        
        # RSI (Relative Strength Index) - Momentum oscillator
        "RSI14",                   # RSI 14 period current value
        "RSI14_PREV",              # RSI 14 period previous value
        
        # Volume indicators
        "VOLUME",                  # Current bar volume
        "SMA_VOLUME_20",           # 20-period SMA of volume
        "REL_VOLUME_20",           # Relative volume (VOLUME / SMA_VOLUME_20)
        
        # Calculated metrics
        "PRICE_EMA20_DIFF_PCT",    # Percentage difference between PRICE and EMA20
    }
    
    # Supported operators for rule conditions
    SUPPORTED_OPERATORS = {
        ">", "<", ">=", "<=",      # Standard comparison operators
        "CROSS_UP",                # Crossover up (indicator crosses above another)
        "CROSS_DOWN"               # Crossover down (indicator crosses below another)
    }
    
    # Supported logic operators
    SUPPORTED_LOGIC = {"AND"}
    
    def __init__(self):
        """Initialize the rule engine with supported operators."""
        self.operators = {
            '>': lambda a, b: a > b,
            '<': lambda a, b: a < b,
            '>=': lambda a, b: a >= b,
            '<=': lambda a, b: a <= b,
        }
        # Note: CROSS_UP and CROSS_DOWN are handled specially in evaluate_condition
    
    def evaluate(self, rule: Dict[str, Any], indicator_values: Dict[str, float]) -> bool:
        """
        Evaluate a rule against current indicator values.
        
        Args:
            rule: Rule definition dictionary with logic and conditions
            indicator_values: Dictionary of current indicator values
            
        Returns:
            bool: True if rule conditions are met, False otherwise
            
        Raises:
            RuleEvaluationError: If evaluation fails due to missing indicators or invalid rule
        """
        try:
            # Validate rule structure
            self.validate_rule(rule)
            
            # Get conditions and logic from rule
            conditions = rule.get("conditions", [])
            logic = rule.get("logic", "AND")
            
            # If no conditions, return False
            if not conditions:
                return False
            
            # Evaluate each condition
            condition_results = []
            for condition in conditions:
                result = self.evaluate_condition(condition, indicator_values)
                condition_results.append(result)
            
            # Apply logic operator (only AND is supported in MVP)
            if logic == "AND":
                return all(condition_results)
            else:
                # This should not happen due to validation, but handle gracefully
                raise RuleEvaluationError(f"Unsupported logic operator: {logic}")
                
        except (RuleValidationError, RuleEvaluationError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Catch any other unexpected errors
            raise RuleEvaluationError(f"Unexpected error during rule evaluation: {str(e)}")
    
    def evaluate_condition(self, condition: Dict[str, Any], indicator_values: Dict[str, float]) -> bool:
        """
        Evaluate a single condition.
        
        Args:
            condition: Single condition with left operand, operator, and right operand
            indicator_values: Dictionary of current indicator values
            
        Returns:
            bool: True if condition is met, False otherwise
            
        Raises:
            RuleEvaluationError: If evaluation fails due to missing indicators or invalid condition
        """
        try:
            # Extract condition components
            left_operand = condition.get("left")
            operator = condition.get("op")
            right_operand = condition.get("right")
            
            # Validate condition structure
            if not all([left_operand, operator, right_operand is not None]):
                raise RuleEvaluationError("Condition must have 'left', 'op', and 'right' fields")
            
            # Validate operator
            if operator not in self.SUPPORTED_OPERATORS:
                raise RuleEvaluationError(f"Unsupported operator: {operator}")
            
            # Handle CROSS_UP operator specially
            if operator == "CROSS_UP":
                return self._evaluate_cross_up(left_operand, right_operand, indicator_values)
            
            # Handle CROSS_DOWN operator specially
            if operator == "CROSS_DOWN":
                return self._evaluate_cross_down(left_operand, right_operand, indicator_values)
            
            # Get values for operands
            left_value = self._get_operand_value(left_operand, indicator_values)
            right_value = self._get_operand_value(right_operand, indicator_values)
            
            # Log condition evaluation for debugging
            result = self.operators.get(operator)(left_value, right_value)
            logger.debug(
                f"Condition: {left_operand}({left_value:.4f}) {operator} {right_operand}({right_value:.4f}) = {result}"
            )
            
            return result
            
        except (RuleEvaluationError, KeyError, TypeError) as e:
            raise RuleEvaluationError(f"Failed to evaluate condition: {str(e)}")
    
    def validate_rule(self, rule: Dict[str, Any]) -> None:
        """
        Validate rule structure and supported operands/operators.
        
        Args:
            rule: Rule definition dictionary
            
        Raises:
            RuleValidationError: If rule structure is invalid or contains unsupported elements
        """
        if not isinstance(rule, dict):
            raise RuleValidationError("Rule must be a dictionary")
        
        # Check required fields
        required_fields = ["id", "name", "type", "logic", "conditions"]
        for field in required_fields:
            if field not in rule:
                raise RuleValidationError(f"Missing required field: {field}")
        
        # Validate logic operator
        logic = rule.get("logic")
        if logic not in self.SUPPORTED_LOGIC:
            raise RuleValidationError(f"Unsupported logic operator: {logic}")
        
        # Validate conditions
        conditions = rule.get("conditions")
        if not isinstance(conditions, list):
            raise RuleValidationError("Conditions must be a list")
        
        if not conditions:
            raise RuleValidationError("At least one condition is required")
        
        # Validate each condition
        for i, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                raise RuleValidationError(f"Condition {i} must be a dictionary")
            
            # Check condition structure
            required_condition_fields = ["left", "op", "right"]
            for field in required_condition_fields:
                if field not in condition:
                    raise RuleValidationError(f"Condition {i} missing required field: {field}")
            
            # Validate operands
            left_operand = condition.get("left")
            right_operand = condition.get("right")
            
            for operand in [left_operand, right_operand]:
                # Allow numeric literals or supported operands
                if not self._is_valid_operand(operand):
                    raise RuleValidationError(f"Unsupported operand: {operand}")
            
            # Validate operator
            operator = condition.get("op")
            if operator not in self.SUPPORTED_OPERATORS:
                raise RuleValidationError(f"Unsupported operator: {operator}")
        
        # Validate cooldown_sec if present
        if "cooldown_sec" in rule:
            cooldown = rule.get("cooldown_sec")
            if not isinstance(cooldown, int) or cooldown < 0:
                raise RuleValidationError("cooldown_sec must be a non-negative integer")
    
    def parse_rule_definition(self, rule_json: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parse JSON rule definition.
        
        Args:
            rule_json: JSON string or dictionary containing rule definition
            
        Returns:
            Dict[str, Any]: Parsed rule definition
            
        Raises:
            RuleValidationError: If JSON parsing fails or rule is invalid
        """
        try:
            # Parse JSON if it's a string
            if isinstance(rule_json, str):
                rule = json.loads(rule_json)
            else:
                rule = rule_json
            
            # Validate the parsed rule
            self.validate_rule(rule)
            
            return rule
            
        except json.JSONDecodeError as e:
            raise RuleValidationError(f"Invalid JSON format: {str(e)}")
        except RuleValidationError:
            # Re-raise our validation errors
            raise
        except Exception as e:
            raise RuleValidationError(f"Failed to parse rule definition: {str(e)}")
    
    def _get_operand_value(self, operand: Union[str, int, float], indicator_values: Dict[str, float]) -> float:
        """
        Get the value for an operand from indicator values or return numeric literal.
        
        Args:
            operand: The operand to get value for (e.g., "PRICE", "MA5") or numeric literal
            indicator_values: Dictionary of current indicator values
            
        Returns:
            float: The value of the operand
            
        Raises:
            RuleEvaluationError: If operand is not found in indicator values
        """
        # If operand is a numeric literal, return it directly
        if isinstance(operand, (int, float)):
            return float(operand)
        
        # Try to convert string to number if it's a numeric string
        if isinstance(operand, str):
            try:
                return float(operand)
            except ValueError:
                pass  # Not a numeric string, continue to look it up
        
        if operand not in indicator_values:
            raise RuleEvaluationError(f"Missing indicator value for operand: {operand}")
        
        value = indicator_values[operand]
        
        # Ensure value is numeric
        if not isinstance(value, (int, float)):
            raise RuleEvaluationError(f"Non-numeric value for operand {operand}: {value}")
        
        return float(value)
    
    def _is_valid_operand(self, operand: Union[str, int, float]) -> bool:
        """
        Check if an operand is valid (either supported operand or numeric literal).
        
        Args:
            operand: The operand to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Allow numeric types
        if isinstance(operand, (int, float)):
            return True
        
        # Allow numeric strings
        if isinstance(operand, str):
            try:
                float(operand)
                return True
            except ValueError:
                pass
        
        # Check if it's a supported operand
        return operand in self.SUPPORTED_OPERANDS
    
    def _evaluate_cross_up(self, left_operand: str, right_operand: str, indicator_values: Dict[str, float]) -> bool:
        """
        Evaluate a CROSS_UP condition.
        
        CROSS_UP checks if left indicator crosses above right indicator:
        - Previous: left <= right
        - Current: left > right
        
        Args:
            left_operand: The indicator that crosses up (e.g., "EMA6")
            right_operand: The indicator being crossed (e.g., "EMA10")
            indicator_values: Dictionary of current and previous indicator values
            
        Returns:
            bool: True if cross up occurred, False otherwise
            
        Raises:
            RuleEvaluationError: If required previous values are not available
        """
        # Get current values
        current_left = self._get_operand_value(left_operand, indicator_values)
        current_right = self._get_operand_value(right_operand, indicator_values)
        
        # Get previous values - expect them to be named with _PREV suffix or stored separately
        # For indicators, we need their previous values
        prev_left_key = f"{left_operand}_PREV"
        prev_right_key = f"{right_operand}_PREV"
        
        if prev_left_key not in indicator_values or prev_right_key not in indicator_values:
            raise RuleEvaluationError(
                f"CROSS_UP requires previous values: {prev_left_key} and {prev_right_key} not found"
            )
        
        prev_left = indicator_values[prev_left_key]
        prev_right = indicator_values[prev_right_key]
        
        # Cross up condition: was below or equal, now above
        was_below_or_equal = prev_left <= prev_right
        is_now_above = current_left > current_right
        
        return was_below_or_equal and is_now_above
    
    def _evaluate_cross_down(self, left_operand: str, right_operand: str, indicator_values: Dict[str, float]) -> bool:
        """
        Evaluate a CROSS_DOWN condition.
        
        CROSS_DOWN checks if left indicator crosses below right indicator:
        - Previous: left >= right
        - Current: left < right
        
        Args:
            left_operand: The indicator that crosses down (e.g., "EMA6")
            right_operand: The indicator being crossed (e.g., "EMA10")
            indicator_values: Dictionary of current and previous indicator values
            
        Returns:
            bool: True if cross down occurred, False otherwise
            
        Raises:
            RuleEvaluationError: If required previous values are not available
        """
        # Get current values
        current_left = self._get_operand_value(left_operand, indicator_values)
        current_right = self._get_operand_value(right_operand, indicator_values)
        
        # Get previous values - expect them to be named with _PREV suffix or stored separately
        # For indicators, we need their previous values
        prev_left_key = f"{left_operand}_PREV"
        prev_right_key = f"{right_operand}_PREV"
        
        if prev_left_key not in indicator_values or prev_right_key not in indicator_values:
            raise RuleEvaluationError(
                f"CROSS_DOWN requires previous values: {prev_left_key} and {prev_right_key} not found"
            )
        
        prev_left = indicator_values[prev_left_key]
        prev_right = indicator_values[prev_right_key]
        
        # Cross down condition: was above or equal, now below
        was_above_or_equal = prev_left >= prev_right
        is_now_below = current_left < current_right
        
        return was_above_or_equal and is_now_below