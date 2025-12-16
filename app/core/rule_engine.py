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
from typing import Dict, Any, List, Union

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
    SUPPORTED_OPERANDS = {"PRICE", "MA5", "MA10", "MA20"}
    
    # Supported operators for rule conditions
    SUPPORTED_OPERATORS = {">", "<", ">=", "<="}
    
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
            if not all([left_operand, operator, right_operand]):
                raise RuleEvaluationError("Condition must have 'left', 'op', and 'right' fields")
            
            # Validate operator
            if operator not in self.SUPPORTED_OPERATORS:
                raise RuleEvaluationError(f"Unsupported operator: {operator}")
            
            # Get values for operands
            left_value = self._get_operand_value(left_operand, indicator_values)
            right_value = self._get_operand_value(right_operand, indicator_values)
            
            # Apply operator
            operator_func = self.operators.get(operator)
            if not operator_func:
                raise RuleEvaluationError(f"Operator not implemented: {operator}")
            
            return operator_func(left_value, right_value)
            
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
                if operand not in self.SUPPORTED_OPERANDS:
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
    
    def _get_operand_value(self, operand: str, indicator_values: Dict[str, float]) -> float:
        """
        Get the value for an operand from indicator values.
        
        Args:
            operand: The operand to get value for (e.g., "PRICE", "MA5")
            indicator_values: Dictionary of current indicator values
            
        Returns:
            float: The value of the operand
            
        Raises:
            RuleEvaluationError: If operand is not found in indicator values
        """
        if operand not in indicator_values:
            raise RuleEvaluationError(f"Missing indicator value for operand: {operand}")
        
        value = indicator_values[operand]
        
        # Ensure value is numeric
        if not isinstance(value, (int, float)):
            raise RuleEvaluationError(f"Non-numeric value for operand {operand}: {value}")
        
        return float(value)