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
import math
import re
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
    MAX_DYNAMIC_PERIOD = 250
    MIN_DYNAMIC_PERIOD = 1
    PREV_N_PATTERN = re.compile(r"^(.+)_PREV_(\d+)$")
    DYNAMIC_OPERAND_PATTERNS = {
        "PRICE_PREV_N": re.compile(r"^PRICE_PREV_(\d+)$"),
        "MA_N": re.compile(r"^MA(\d+)$"),
        "EMA_N": re.compile(r"^EMA(\d+)$"),
        "RSI_N": re.compile(r"^RSI(\d+)$"),
        "ADX_N": re.compile(r"^ADX(\d+)$"),
        "SMA_VOLUME_N": re.compile(r"^SMA_VOLUME_(\d+)$"),
        "REL_VOLUME_N": re.compile(r"^REL_VOLUME_(\d+)$"),
    }
    DYNAMIC_CROSSABLE_TYPES = {"MA_N", "EMA_N", "RSI_N", "ADX_N", "SMA_VOLUME_N", "REL_VOLUME_N"}
    CANDLE_PATTERN_DEFINITIONS = {
        "PATTERN_CDLDOJI": {"talib": "CDLDOJI", "label": "DOJI", "direction": "neutral"},
        "PATTERN_CDLHAMMER": {"talib": "CDLHAMMER", "label": "HAMMER", "direction": "bullish"},
        "PATTERN_CDLSHOOTINGSTAR": {"talib": "CDLSHOOTINGSTAR", "label": "SHOOTING STAR", "direction": "bearish"},
        "PATTERN_BULLISH_ENGULFING": {"talib": "CDLENGULFING", "label": "BULLISH ENGULFING", "direction": "bullish"},
        "PATTERN_BEARISH_ENGULFING": {"talib": "CDLENGULFING", "label": "BEARISH ENGULFING", "direction": "bearish"},
        "PATTERN_CDLMORNINGSTAR": {"talib": "CDLMORNINGSTAR", "label": "MORNING STAR", "direction": "bullish"},
        "PATTERN_CDLEVENINGSTAR": {"talib": "CDLEVENINGSTAR", "label": "EVENING STAR", "direction": "bearish"},
        "PATTERN_CDLHARAMI": {"talib": "CDLHARAMI", "label": "HARAMI", "direction": "neutral"},
        "PATTERN_CDLPIERCING": {"talib": "CDLPIERCING", "label": "PIERCING", "direction": "bullish"},
        "PATTERN_CDLDARKCLOUDCOVER": {"talib": "CDLDARKCLOUDCOVER", "label": "DARK CLOUD COVER", "direction": "bearish"},
    }
    CANDLE_PATTERN_OPERANDS = set(CANDLE_PATTERN_DEFINITIONS.keys())

    SUPPORTED_OPERANDS = {
        # Price indicators
        "PRICE",                    # Current price
        "OPEN", "HIGH", "LOW", "CLOSE",  # Current candle OHLC values
        "OPEN_PREV", "HIGH_PREV", "LOW_PREV", "CLOSE_PREV",  # Previous candle OHLC values
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

        # Stochastic Oscillator
        "STOCH_K",                 # Stochastic %K line
        "STOCH_D",                 # Stochastic %D signal line
        "STOCH_K_PREV", "STOCH_D_PREV",  # Previous Stochastic values

        # Ichimoku Cloud
        "ICHIMOKU_CONVERSION",     # Tenkan-sen conversion line
        "ICHIMOKU_BASE",           # Kijun-sen base line
        "ICHIMOKU_A",              # Senkou Span A
        "ICHIMOKU_B",              # Senkou Span B
        "ICHIMOKU_CONVERSION_PREV", "ICHIMOKU_BASE_PREV",
        "ICHIMOKU_A_PREV", "ICHIMOKU_B_PREV",
        
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

        # TA-Lib candle pattern signals
        *CANDLE_PATTERN_OPERANDS,
    }
    
    # Supported operators for rule conditions
    SUPPORTED_OPERATORS = {
        ">", "<", ">=", "<=",      # Standard comparison operators
        "CROSS_UP",                # Crossover up (indicator crosses above another)
        "CROSS_DOWN"               # Crossover down (indicator crosses below another)
    }
    
    # Supported logic operators
    SUPPORTED_LOGIC = {"AND"}

    @classmethod
    def get_crossable_operands(cls) -> List[str]:
        """
        Return operands that have matching previous values for crossover checks.
        """
        return sorted(
            operand for operand in cls.SUPPORTED_OPERANDS
            if (
                isinstance(operand, str)
                and not operand.endswith("_PREV")
                and f"{operand}_PREV" in cls.SUPPORTED_OPERANDS
            )
        )

    @classmethod
    def parse_dynamic_operand(cls, operand: Union[str, int, float]) -> Union[Dict[str, Any], None]:
        """Parse supported dynamic operand strings such as EMA12 or PRICE_PREV_5."""
        if not isinstance(operand, str):
            return None

        base_operand = operand[:-5] if operand.endswith("_PREV") else operand
        is_prev = operand.endswith("_PREV")

        for operand_type, pattern in cls.DYNAMIC_OPERAND_PATTERNS.items():
            match = pattern.match(base_operand)
            if not match:
                continue

            period = int(match.group(1))
            if period < cls.MIN_DYNAMIC_PERIOD or period > cls.MAX_DYNAMIC_PERIOD:
                return None
            if is_prev and operand_type == "PRICE_PREV_N":
                return None

            return {
                "type": operand_type,
                "period": period,
                "base": base_operand,
                "is_prev": is_prev,
            }

        return None

    @classmethod
    def parse_prev_n_operand(cls, operand: Union[str, int, float]) -> Union[Dict[str, Any], None]:
        """Parse generic previous-value operands such as EMA20_PREV_3 or CLOSE_PREV_5."""
        if not isinstance(operand, str):
            return None

        match = cls.PREV_N_PATTERN.match(operand)
        if not match:
            return None

        base = match.group(1)
        offset = int(match.group(2))
        if offset < cls.MIN_DYNAMIC_PERIOD or offset > cls.MAX_DYNAMIC_PERIOD:
            return None
        if base.endswith("_PREV") or cls.parse_prev_n_operand(base):
            return None
        if not cls._is_valid_base_operand(base):
            return None

        return {
            "type": "PREV_N",
            "base": base,
            "offset": offset,
        }

    @classmethod
    def is_dynamic_operand(cls, operand: Union[str, int, float]) -> bool:
        return cls.parse_dynamic_operand(operand) is not None or cls.parse_prev_n_operand(operand) is not None

    @classmethod
    def is_crossable_operand(cls, operand: Union[str, int, float]) -> bool:
        if not isinstance(operand, str) or operand.endswith("_PREV") or cls.parse_prev_n_operand(operand):
            return False
        if operand in cls.get_crossable_operands():
            return True

        parsed = cls.parse_dynamic_operand(operand)
        return bool(parsed and parsed["type"] in cls.DYNAMIC_CROSSABLE_TYPES)

    @classmethod
    def extract_required_operands(cls, rule: Dict[str, Any]) -> set:
        """Return non-numeric operands needed to evaluate a rule, including cross previous values."""
        required = set()
        cross_ops = {"CROSS_UP", "CROSS_DOWN"}
        for condition in rule.get("conditions", []):
            op = condition.get("op")
            for side in ("left", "right"):
                operand = condition.get(side)
                if isinstance(operand, str) and not cls._is_numeric_literal(operand):
                    required.add(operand)
                    if op in cross_ops and not operand.endswith("_PREV") and not cls.parse_prev_n_operand(operand):
                        required.add(f"{operand}_PREV")
        return required

    @classmethod
    def estimate_operand_warmup(cls, operand: Union[str, int, float]) -> int:
        """Estimate minimum candle count needed for an operand to be available."""
        if isinstance(operand, (int, float)) or cls._is_numeric_literal(operand):
            return 1

        if not isinstance(operand, str):
            return 1

        is_prev = operand.endswith("_PREV")
        base_operand = operand[:-5] if is_prev else operand
        prev_n = cls.parse_prev_n_operand(operand)
        if prev_n:
            return cls.estimate_operand_warmup(prev_n["base"]) + prev_n["offset"]

        parsed = cls.parse_dynamic_operand(operand)

        if parsed:
            operand_type = parsed["type"]
            period = parsed["period"]
            if operand_type == "PRICE_PREV_N":
                warmup = period + 1
            elif operand_type == "RSI_N":
                warmup = period + 1
            elif operand_type == "ADX_N":
                warmup = period + 1
            else:
                warmup = period
            return warmup + (1 if is_prev else 0)

        if base_operand in cls.CANDLE_PATTERN_OPERANDS:
            return 5 + (1 if is_prev else 0)

        static_warmup = {
            "PRICE": 1, "OPEN": 1, "HIGH": 1, "LOW": 1, "CLOSE": 1,
            "PREV_CLOSE": 2, "PREV_OPEN": 2,
            "MACD": 35, "MACD_SIGNAL": 35, "MACD_HIST": 35,
            "BB_UPPER": 20, "BB_MIDDLE": 20, "BB_LOWER": 20, "BB_WIDTH": 20,
            "STOCH_K": 17, "STOCH_D": 17,
            "ICHIMOKU_CONVERSION": 52, "ICHIMOKU_BASE": 52,
            "ICHIMOKU_A": 52, "ICHIMOKU_B": 52,
            "PRICE_EMA20_DIFF_PCT": 20,
            "VOLUME": 1,
        }
        if base_operand.startswith("MA") and base_operand[2:].isdigit():
            warmup = int(base_operand[2:])
        elif base_operand.startswith("EMA") and base_operand[3:].isdigit():
            warmup = int(base_operand[3:])
        elif base_operand.startswith("RSI") and base_operand[3:].isdigit():
            warmup = int(base_operand[3:]) + 1
        elif base_operand.startswith("ADX") and base_operand[3:].isdigit():
            warmup = int(base_operand[3:]) + 1
        elif base_operand.startswith("SMA_VOLUME_") and base_operand[11:].isdigit():
            warmup = int(base_operand[11:])
        elif base_operand.startswith("REL_VOLUME_") and base_operand[11:].isdigit():
            warmup = int(base_operand[11:])
        else:
            warmup = static_warmup.get(base_operand, 1)

        return warmup + (1 if is_prev else 0)

    @classmethod
    def estimate_rule_warmup(cls, rule: Dict[str, Any], default: int = 35) -> int:
        required = cls.extract_required_operands(rule)
        if not required:
            return default
        return max(cls.estimate_operand_warmup(operand) for operand in required)

    @staticmethod
    def _is_numeric_literal(operand: Union[str, int, float]) -> bool:
        if isinstance(operand, (int, float)):
            return True
        if isinstance(operand, str):
            try:
                float(operand)
                return True
            except ValueError:
                return False
        return False

    @classmethod
    def _is_valid_base_operand(cls, operand: Union[str, int, float]) -> bool:
        if cls._is_numeric_literal(operand):
            return True
        if not isinstance(operand, str):
            return False
        return operand in cls.SUPPORTED_OPERANDS or cls.parse_dynamic_operand(operand) is not None
    
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
    
    def evaluate_detailed(self, rule: Dict[str, Any], indicator_values: Dict[str, float]) -> Dict[str, Any]:
        """Evaluate a rule and report per-condition pass/fail plus resolved values.

        Same trigger semantics as ``evaluate`` (AND-only), but instead of a bare
        boolean it returns which conditions matched and the numeric operands that
        were compared. This powers the screener's "matched N/M" summary and the
        per-condition ✓/✗ breakdown so a lolos/gagal result can be explained
        (see #4). Comparison logic is delegated to ``evaluate_condition`` so it
        stays in lockstep with ``evaluate``.

        Returns::

            {
              "triggered": bool,          # rule as a whole fired
              "matched": int,             # conditions that passed
              "total": int,               # total conditions
              "conditions": [
                {"left", "op", "right", "passed",
                 "left_value"?, "right_value"?}  # values omitted for CROSS ops
              ]
            }
        """
        self.validate_rule(rule)
        conditions = rule.get("conditions", [])
        logic = rule.get("logic", "AND")

        details = []
        for condition in conditions:
            passed = bool(self.evaluate_condition(condition, indicator_values))
            op = condition.get("op")
            detail = {
                "left": condition.get("left"),
                "op": op,
                "right": condition.get("right"),
                "passed": passed,
            }
            # Resolved numeric operands help explain the result. Cross operators
            # compare current vs previous values, so a single pair isn't
            # meaningful there — skip them.
            if op not in ("CROSS_UP", "CROSS_DOWN"):
                try:
                    left_mult = self._get_condition_multiplier(condition, "left")
                    right_mult = self._get_condition_multiplier(condition, "right")
                    detail["left_value"] = self._get_operand_value(condition.get("left"), indicator_values) * left_mult
                    detail["right_value"] = self._get_operand_value(condition.get("right"), indicator_values) * right_mult
                except RuleEvaluationError:
                    pass
            details.append(detail)

        matched = sum(1 for d in details if d["passed"])
        total = len(details)
        triggered = total > 0 and logic == "AND" and matched == total
        return {
            "triggered": triggered,
            "matched": matched,
            "total": total,
            "conditions": details,
        }

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
            left_multiplier = self._get_condition_multiplier(condition, "left")
            right_multiplier = self._get_condition_multiplier(condition, "right")
            left_value = self._get_operand_value(left_operand, indicator_values) * left_multiplier
            right_value = self._get_operand_value(right_operand, indicator_values) * right_multiplier
            
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

            left_multiplier = self._parse_multiplier(condition.get("left_multiplier", 1.0))
            right_multiplier = self._parse_multiplier(condition.get("right_multiplier", 1.0))

            if operator in {"CROSS_UP", "CROSS_DOWN"}:
                if left_multiplier != 1.0 or right_multiplier != 1.0:
                    raise RuleValidationError(f"{operator} does not support operand multipliers")
                if not self.is_crossable_operand(left_operand):
                    raise RuleValidationError(
                        f"{operator} left operand must have a previous value: {left_operand}"
                    )
                if not self.is_crossable_operand(right_operand):
                    raise RuleValidationError(
                        f"{operator} right operand must have a previous value: {right_operand}"
                    )
        
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

    @classmethod
    def _parse_multiplier(cls, value: Union[str, int, float, None]) -> float:
        if value is None or value == "":
            return 1.0
        if isinstance(value, bool):
            raise RuleValidationError("Multiplier must be a positive number")
        try:
            multiplier = float(value)
        except (TypeError, ValueError):
            raise RuleValidationError("Multiplier must be a positive number")
        if not math.isfinite(multiplier) or multiplier <= 0:
            raise RuleValidationError("Multiplier must be a positive number")
        return multiplier

    @classmethod
    def _get_condition_multiplier(cls, condition: Dict[str, Any], side: str) -> float:
        try:
            return cls._parse_multiplier(condition.get(f"{side}_multiplier", 1.0))
        except RuleValidationError as e:
            raise RuleEvaluationError(str(e))
    
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
        # Allow numeric types and numeric strings
        if self._is_numeric_literal(operand):
            return True
        
        # Check if it's a supported operand
        return operand in self.SUPPORTED_OPERANDS or self.is_dynamic_operand(operand)
    
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
