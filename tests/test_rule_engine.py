"""
Comprehensive test suite for the Rule Engine module.

This test suite ensures the RuleEngine class is accurate, deterministic, and robust.
It covers rule validation, evaluation logic, error handling, performance, and thread safety.
"""

import pytest
import json
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

# Import the rule engine module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.rule_engine import (
    RuleEngine, 
    RuleValidationError, 
    RuleEvaluationError
)


class TestRuleEngine:
    """Test class for RuleEngine functionality."""
    
    @pytest.fixture
    def rule_engine(self):
        """Create a RuleEngine instance for testing."""
        return RuleEngine()
    
    @pytest.fixture
    def sample_indicator_values(self):
        """Sample indicator values for testing."""
        return {
            "PRICE": 100.50,
            "MA5": 98.75,
            "MA10": 97.25,
            "MA20": 95.50
        }
    
    @pytest.fixture
    def valid_rule(self):
        """A valid rule for testing."""
        return {
            "id": "test_rule_1",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ],
            "cooldown_sec": 60
        }
    
    @pytest.fixture
    def complex_rule(self):
        """A more complex rule with multiple conditions."""
        return {
            "id": "complex_rule",
            "name": "Complex Test Rule",
            "type": "SELL",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA20"
                },
                {
                    "left": "MA5",
                    "op": ">",
                    "right": "MA10"
                },
                {
                    "left": "MA10",
                    "op": ">",
                    "right": "MA20"
                }
            ]
        }


class TestRuleValidation(TestRuleEngine):
    """Test cases for rule validation functionality."""
    
    def test_validate_valid_rule(self, rule_engine, valid_rule):
        """Test validation of a valid rule."""
        # Should not raise any exception
        rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_missing_required_fields(self, rule_engine):
        """Test validation fails with missing required fields."""
        # Missing 'id' field
        invalid_rule = {
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": []
        }
        
        with pytest.raises(RuleValidationError, match="Missing required field: id"):
            rule_engine.validate_rule(invalid_rule)
    
    def test_validate_rule_invalid_logic_operator(self, rule_engine, valid_rule):
        """Test validation fails with unsupported logic operator."""
        valid_rule["logic"] = "OR"  # Not supported in MVP
        
        with pytest.raises(RuleValidationError, match="Unsupported logic operator: OR"):
            rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_empty_conditions(self, rule_engine, valid_rule):
        """Test validation fails with empty conditions."""
        valid_rule["conditions"] = []
        
        with pytest.raises(RuleValidationError, match="At least one condition is required"):
            rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_invalid_condition_structure(self, rule_engine, valid_rule):
        """Test validation fails with invalid condition structure."""
        # Condition missing 'op' field
        valid_rule["conditions"] = [
            {
                "left": "PRICE",
                "right": "MA5"
            }
        ]
        
        with pytest.raises(RuleValidationError, match="Condition 0 missing required field: op"):
            rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_unsupported_operand(self, rule_engine, valid_rule):
        """Test validation fails with unsupported operand."""
        valid_rule["conditions"] = [
            {
                "left": "PRICE",
                "op": ">",
                "right": "RSI"  # Not supported
            }
        ]
        
        with pytest.raises(RuleValidationError, match="Unsupported operand: RSI"):
            rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_unsupported_operator(self, rule_engine, valid_rule):
        """Test validation fails with unsupported operator."""
        valid_rule["conditions"] = [
            {
                "left": "PRICE",
                "op": "==",  # Not supported
                "right": "MA5"
            }
        ]
        
        with pytest.raises(RuleValidationError, match="Unsupported operator: =="):
            rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_invalid_cooldown(self, rule_engine, valid_rule):
        """Test validation fails with invalid cooldown."""
        valid_rule["cooldown_sec"] = -1  # Negative cooldown
        
        with pytest.raises(RuleValidationError, match="cooldown_sec must be a non-negative integer"):
            rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_non_dict_input(self, rule_engine):
        """Test validation fails with non-dictionary input."""
        with pytest.raises(RuleValidationError, match="Rule must be a dictionary"):
            rule_engine.validate_rule("not a dictionary")
    
    def test_validate_rule_conditions_not_list(self, rule_engine, valid_rule):
        """Test validation fails when conditions is not a list."""
        valid_rule["conditions"] = "not a list"
        
        with pytest.raises(RuleValidationError, match="Conditions must be a list"):
            rule_engine.validate_rule(valid_rule)
    
    def test_validate_rule_condition_not_dict(self, rule_engine, valid_rule):
        """Test validation fails when condition is not a dictionary."""
        valid_rule["conditions"] = ["not a dictionary"]
        
        with pytest.raises(RuleValidationError, match="Condition 0 must be a dictionary"):
            rule_engine.validate_rule(valid_rule)


class TestRuleEvaluation(TestRuleEngine):
    """Test cases for rule evaluation functionality."""
    
    def test_evaluate_simple_true_condition(self, rule_engine, sample_indicator_values):
        """Test evaluation of a simple condition that should be true."""
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, sample_indicator_values)
        assert result is True  # 100.50 > 98.75
    
    def test_evaluate_simple_false_condition(self, rule_engine, sample_indicator_values):
        """Test evaluation of a simple condition that should be false."""
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": "<",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, sample_indicator_values)
        assert result is False  # 100.50 < 98.75 is False
    
    def test_evaluate_multiple_conditions_all_true(self, rule_engine, sample_indicator_values):
        """Test evaluation with multiple conditions that are all true."""
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                },
                {
                    "left": "MA5",
                    "op": ">",
                    "right": "MA10"
                },
                {
                    "left": "MA10",
                    "op": ">",
                    "right": "MA20"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, sample_indicator_values)
        assert result is True  # All conditions are true
    
    def test_evaluate_multiple_conditions_one_false(self, rule_engine, sample_indicator_values):
        """Test evaluation with multiple conditions where one is false."""
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                },
                {
                    "left": "MA5",
                    "op": "<",  # This will be false
                    "right": "MA10"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, sample_indicator_values)
        assert result is False  # One condition is false, so AND is false
    
    def test_evaluate_all_operators(self, rule_engine, sample_indicator_values):
        """Test evaluation with all supported operators."""
        test_cases = [
            (">", "PRICE", "MA20", True),   # 100.50 > 95.50
            ("<", "PRICE", "MA20", False),  # 100.50 < 95.50
            (">=", "PRICE", "MA20", True),  # 100.50 >= 95.50
            ("<=", "PRICE", "MA20", False), # 100.50 <= 95.50
        ]
        
        for op, left, right, expected in test_cases:
            rule = {
                "id": f"test_rule_{op}",
                "name": f"Test Rule {op}",
                "type": "BUY",
                "logic": "AND",
                "conditions": [
                    {
                        "left": left,
                        "op": op,
                        "right": right
                    }
                ]
            }
            
            result = rule_engine.evaluate(rule, sample_indicator_values)
            assert result is expected, f"Operator {op} failed: expected {expected}, got {result}"
    
    def test_evaluate_boundary_conditions(self, rule_engine):
        """Test evaluation with boundary conditions."""
        # Test equal values with >= and <=
        indicator_values = {
            "PRICE": 100.0,
            "MA5": 100.0,
            "MA10": 100.0,
            "MA20": 100.0
        }
        
        # Test >= with equal values
        rule_gte = {
            "id": "test_rule_gte",
            "name": "Test Rule GTE",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">=",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule_gte, indicator_values)
        assert result is True  # 100.0 >= 100.0
        
        # Test <= with equal values
        rule_lte = {
            "id": "test_rule_lte",
            "name": "Test Rule LTE",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": "<=",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule_lte, indicator_values)
        assert result is True  # 100.0 <= 100.0
        
        # Test > with equal values (should be false)
        rule_gt = {
            "id": "test_rule_gt",
            "name": "Test Rule GT",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule_gt, indicator_values)
        assert result is False  # 100.0 > 100.0 is False
        
        # Test < with equal values (should be false)
        rule_lt = {
            "id": "test_rule_lt",
            "name": "Test Rule LT",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": "<",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule_lt, indicator_values)
        assert result is False  # 100.0 < 100.0 is False
    
    def test_evaluate_missing_indicator(self, rule_engine, sample_indicator_values):
        """Test evaluation fails when required indicator is missing."""
        # Remove MA20 from indicator values
        incomplete_values = {k: v for k, v in sample_indicator_values.items() if k != "MA20"}
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA20"  # This indicator is missing
                }
            ]
        }
        
        with pytest.raises(RuleEvaluationError, match="Missing indicator value for operand: MA20"):
            rule_engine.evaluate(rule, incomplete_values)
    
    def test_evaluate_non_numeric_indicator(self, rule_engine):
        """Test evaluation fails when indicator value is not numeric."""
        indicator_values = {
            "PRICE": "not_a_number",
            "MA5": 98.75,
            "MA10": 97.25,
            "MA20": 95.50
        }
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        with pytest.raises(RuleEvaluationError, match="Non-numeric value for operand PRICE"):
            rule_engine.evaluate(rule, indicator_values)
    
    def test_evaluate_no_conditions(self, rule_engine, sample_indicator_values):
        """Test evaluation with no conditions returns False."""
        # This tests line 89 in rule_engine.py
        # We need to mock validate_rule to bypass validation and test the evaluation path
        import unittest.mock
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": []  # Empty conditions
        }
        
        with unittest.mock.patch.object(rule_engine, 'validate_rule'):
            result = rule_engine.evaluate(rule, sample_indicator_values)
            assert result is False  # Should return False when no conditions


class TestDeterministicBehavior(TestRuleEngine):
    """Test cases to ensure deterministic behavior of the rule engine."""
    
    def test_deterministic_evaluation_single_thread(self, rule_engine, valid_rule, sample_indicator_values):
        """Test that evaluation is deterministic in single-threaded execution."""
        results = []
        
        # Evaluate the same rule multiple times
        for _ in range(100):
            result = rule_engine.evaluate(valid_rule, sample_indicator_values)
            results.append(result)
        
        # All results should be identical
        assert all(r == results[0] for r in results)
    
    def test_deterministic_evaluation_multi_thread(self, rule_engine, valid_rule, sample_indicator_values):
        """Test that evaluation is deterministic in multi-threaded execution."""
        results = []
        
        def evaluate_rule():
            return rule_engine.evaluate(valid_rule, sample_indicator_values)
        
        # Evaluate the same rule from multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(evaluate_rule) for _ in range(100)]
            for future in as_completed(futures):
                results.append(future.result())
        
        # All results should be identical
        assert all(r == results[0] for r in results)
    
    def test_deterministic_with_different_instances(self, valid_rule, sample_indicator_values):
        """Test that different RuleEngine instances produce the same results."""
        results = []
        
        # Create multiple RuleEngine instances
        for _ in range(10):
            engine = RuleEngine()
            result = engine.evaluate(valid_rule, sample_indicator_values)
            results.append(result)
        
        # All results should be identical
        assert all(r == results[0] for r in results)


class TestErrorHandling(TestRuleEngine):
    """Test cases for error handling in the rule engine."""
    
    def test_evaluate_invalid_rule(self, rule_engine, sample_indicator_values):
        """Test evaluation fails with invalid rule."""
        invalid_rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "INVALID",  # Invalid logic
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        with pytest.raises(RuleValidationError):
            rule_engine.evaluate(invalid_rule, sample_indicator_values)
    
    def test_evaluate_condition_missing_fields(self, rule_engine, sample_indicator_values):
        """Test evaluation fails when condition is missing required fields."""
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    # Missing 'op' and 'right'
                }
            ]
        }
        
        # Rule validation happens before evaluation, so we expect RuleValidationError
        with pytest.raises(RuleValidationError, match="Condition 0 missing required field: op"):
            rule_engine.evaluate(rule, sample_indicator_values)
    
    def test_evaluate_unsupported_operator(self, rule_engine, sample_indicator_values):
        """Test evaluation fails with unsupported operator."""
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": "==",  # Not supported
                    "right": "MA5"
                }
            ]
        }
        
        # Rule validation happens before evaluation, so we expect RuleValidationError
        with pytest.raises(RuleValidationError, match="Unsupported operator: =="):
            rule_engine.evaluate(rule, sample_indicator_values)
    
    def test_parse_rule_json_string(self, rule_engine, valid_rule):
        """Test parsing rule from JSON string."""
        rule_json = json.dumps(valid_rule)
        parsed_rule = rule_engine.parse_rule_definition(rule_json)
        
        assert parsed_rule == valid_rule
    
    def test_parse_rule_invalid_json(self, rule_engine):
        """Test parsing fails with invalid JSON."""
        invalid_json = "{ invalid json }"
        
        with pytest.raises(RuleValidationError, match="Invalid JSON format"):
            rule_engine.parse_rule_definition(invalid_json)
    
    def test_parse_rule_invalid_structure(self, rule_engine):
        """Test parsing fails with invalid rule structure."""
        invalid_rule = {
            "id": "test_rule",
            # Missing required fields
        }
        
        with pytest.raises(RuleValidationError):
            rule_engine.parse_rule_definition(invalid_rule)
    
    def test_parse_rule_unexpected_error(self, rule_engine):
        """Test parsing handles unexpected errors gracefully."""
        # This tests lines 245-246 in rule_engine.py
        # Create a rule that will cause an unexpected error during validation
        # We need to mock the validate_rule method to raise an unexpected error
        import unittest.mock
        
        with unittest.mock.patch.object(rule_engine, 'validate_rule', side_effect=RuntimeError("Unexpected error")):
            with pytest.raises(RuleValidationError, match="Failed to parse rule definition"):
                rule_engine.parse_rule_definition({"id": "test"})  # Valid dict but validation will fail
    
    def test_evaluate_unsupported_logic_operator(self, rule_engine, sample_indicator_values):
        """Test evaluation fails with unsupported logic operator after validation bypass."""
        # Create a valid rule first
        valid_rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        # Mock the validate_rule method to bypass validation and test the evaluation path
        # This tests line 102 in rule_engine.py
        import unittest.mock
        with unittest.mock.patch.object(rule_engine, 'validate_rule'):
            valid_rule["logic"] = "UNSUPPORTED"
            
            with pytest.raises(RuleEvaluationError, match="Unsupported logic operator: UNSUPPORTED"):
                rule_engine.evaluate(valid_rule, sample_indicator_values)
    
    def test_evaluate_unexpected_error(self, rule_engine, sample_indicator_values):
        """Test evaluation handles unexpected errors gracefully."""
        # Create a rule that will cause an unexpected error
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        # Mock indicator_values to cause an unexpected error
        # This tests lines 107-109 in rule_engine.py
        class MockDict:
            def __getitem__(self, key):
                raise RuntimeError("Unexpected error")
            
            def get(self, key, default=None):
                raise RuntimeError("Unexpected error")
        
        mock_values = MockDict()
        
        with pytest.raises(RuleEvaluationError, match="Unexpected error during rule evaluation"):
            rule_engine.evaluate(rule, mock_values)
    
    def test_evaluate_condition_missing_fields_direct(self, rule_engine, sample_indicator_values):
        """Test evaluate_condition directly with missing fields."""
        # This tests line 133 in rule_engine.py
        condition = {
            "left": "PRICE"
            # Missing 'op' and 'right'
        }
        
        with pytest.raises(RuleEvaluationError, match="Condition must have 'left', 'op', and 'right' fields"):
            rule_engine.evaluate_condition(condition, sample_indicator_values)
    
    def test_evaluate_condition_unsupported_operator_direct(self, rule_engine, sample_indicator_values):
        """Test evaluate_condition directly with unsupported operator."""
        # This tests line 137 in rule_engine.py
        condition = {
            "left": "PRICE",
            "op": "==",  # Not supported
            "right": "MA5"
        }
        
        with pytest.raises(RuleEvaluationError, match="Unsupported operator: =="):
            rule_engine.evaluate_condition(condition, sample_indicator_values)
    
    def test_evaluate_condition_operator_not_implemented(self, rule_engine, sample_indicator_values):
        """Test evaluate_condition when operator is not implemented."""
        # This tests line 146 in rule_engine.py
        # We need to manipulate the operators dict to remove an operator
        original_operators = rule_engine.operators
        rule_engine.operators = {}  # Empty operators dict
        
        condition = {
            "left": "PRICE",
            "op": ">",
            "right": "MA5"
        }
        
        with pytest.raises(RuleEvaluationError, match="Operator not implemented: >"):
            rule_engine.evaluate_condition(condition, sample_indicator_values)
        
        # Restore original operators
        rule_engine.operators = original_operators


class TestPerformance(TestRuleEngine):
    """Test cases for performance evaluation."""
    
    def test_evaluation_performance(self, rule_engine, complex_rule, sample_indicator_values):
        """Test that rule evaluation is performant."""
        # Measure time for multiple evaluations
        start_time = time.time()
        
        for _ in range(10000):
            rule_engine.evaluate(complex_rule, sample_indicator_values)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete 10,000 evaluations in less than 1 second
        assert elapsed_time < 1.0, f"Evaluation took too long: {elapsed_time} seconds"
    
    def test_validation_performance(self, rule_engine, complex_rule):
        """Test that rule validation is performant."""
        # Measure time for multiple validations
        start_time = time.time()
        
        for _ in range(10000):
            rule_engine.validate_rule(complex_rule)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete 10,000 validations in less than 1 second
        assert elapsed_time < 1.0, f"Validation took too long: {elapsed_time} seconds"


class TestPropertyBased(TestRuleEngine):
    """Property-based tests for the rule engine."""
    
    @pytest.mark.parametrize("price,ma5,ma10,ma20", [
        (100.0, 95.0, 90.0, 85.0),  # All decreasing
        (85.0, 90.0, 95.0, 100.0),  # All increasing
        (100.0, 100.0, 100.0, 100.0),  # All equal
        (100.0, 95.0, 100.0, 95.0),  # Alternating
        (50.0, 75.0, 100.0, 125.0),  # Increasing trend
        (125.0, 100.0, 75.0, 50.0),  # Decreasing trend
    ])
    def test_property_based_evaluation(self, rule_engine, price, ma5, ma10, ma20):
        """Test rule evaluation with various indicator value combinations."""
        indicator_values = {
            "PRICE": price,
            "MA5": ma5,
            "MA10": ma10,
            "MA20": ma20
        }
        
        # Test all possible simple conditions
        test_cases = [
            ("PRICE", ">", "MA5", price > ma5),
            ("PRICE", "<", "MA5", price < ma5),
            ("PRICE", ">=", "MA5", price >= ma5),
            ("PRICE", "<=", "MA5", price <= ma5),
            ("MA5", ">", "MA10", ma5 > ma10),
            ("MA5", "<", "MA10", ma5 < ma10),
            ("MA5", ">=", "MA10", ma5 >= ma10),
            ("MA5", "<=", "MA10", ma5 <= ma10),
            ("MA10", ">", "MA20", ma10 > ma20),
            ("MA10", "<", "MA20", ma10 < ma20),
            ("MA10", ">=", "MA20", ma10 >= ma20),
            ("MA10", "<=", "MA20", ma10 <= ma20),
        ]
        
        for left, op, right, expected in test_cases:
            rule = {
                "id": f"test_rule_{left}_{op}_{right}",
                "name": f"Test Rule {left} {op} {right}",
                "type": "BUY",
                "logic": "AND",
                "conditions": [
                    {
                        "left": left,
                        "op": op,
                        "right": right
                    }
                ]
            }
            
            result = rule_engine.evaluate(rule, indicator_values)
            assert result is expected, f"Failed for {left} {op} {right} with values {price}, {ma5}, {ma10}, {ma20}"
    
    def test_property_based_and_logic(self, rule_engine):
        """Test AND logic with property-based approach."""
        # Generate random indicator values
        for _ in range(100):
            price = random.uniform(50, 150)
            ma5 = random.uniform(50, 150)
            ma10 = random.uniform(50, 150)
            ma20 = random.uniform(50, 150)
            
            indicator_values = {
                "PRICE": price,
                "MA5": ma5,
                "MA10": ma10,
                "MA20": ma20
            }
            
            # Create a rule with multiple conditions
            rule = {
                "id": "test_rule",
                "name": "Test Rule",
                "type": "BUY",
                "logic": "AND",
                "conditions": [
                    {
                        "left": "PRICE",
                        "op": ">",
                        "right": "MA5"
                    },
                    {
                        "left": "MA5",
                        "op": ">",
                        "right": "MA10"
                    }
                ]
            }
            
            result = rule_engine.evaluate(rule, indicator_values)
            expected = (price > ma5) and (ma5 > ma10)
            
            assert result is expected, f"AND logic failed for values {price}, {ma5}, {ma10}, {ma20}"


class TestThreadSafety(TestRuleEngine):
    """Test cases for thread safety of the rule engine."""
    
    def test_concurrent_evaluation(self, rule_engine, valid_rule, sample_indicator_values):
        """Test concurrent evaluation from multiple threads."""
        results = []
        errors = []
        
        def evaluate_rule():
            try:
                result = rule_engine.evaluate(valid_rule, sample_indicator_values)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads that evaluate the same rule
        threads = []
        for _ in range(50):
            thread = threading.Thread(target=evaluate_rule)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check for errors
        assert len(errors) == 0, f"Errors occurred during concurrent evaluation: {errors}"
        
        # Check that all results are identical
        assert len(results) == 50
        assert all(r == results[0] for r in results)
    
    def test_concurrent_validation(self, rule_engine, valid_rule):
        """Test concurrent validation from multiple threads."""
        results = []
        errors = []
        
        def validate_rule():
            try:
                rule_engine.validate_rule(valid_rule)
                results.append(True)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads that validate the same rule
        threads = []
        for _ in range(50):
            thread = threading.Thread(target=validate_rule)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check for errors
        assert len(errors) == 0, f"Errors occurred during concurrent validation: {errors}"
        
        # Check that all validations succeeded
        assert len(results) == 50
        assert all(results)
    
    def test_concurrent_different_instances(self, valid_rule, sample_indicator_values):
        """Test concurrent evaluation with different RuleEngine instances."""
        results = []
        errors = []
        
        def evaluate_with_new_instance():
            try:
                engine = RuleEngine()
                result = engine.evaluate(valid_rule, sample_indicator_values)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads with different RuleEngine instances
        threads = []
        for _ in range(50):
            thread = threading.Thread(target=evaluate_with_new_instance)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check for errors
        assert len(errors) == 0, f"Errors occurred during concurrent evaluation: {errors}"
        
        # Check that all results are identical
        assert len(results) == 50
        assert all(r == results[0] for r in results)


class TestEdgeCases(TestRuleEngine):
    """Test cases for edge cases and boundary conditions."""
    
    def test_evaluate_with_zero_values(self, rule_engine):
        """Test evaluation with zero values."""
        indicator_values = {
            "PRICE": 0.0,
            "MA5": 0.0,
            "MA10": 0.0,
            "MA20": 0.0
        }
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">=",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, indicator_values)
        assert result is True  # 0.0 >= 0.0
    
    def test_evaluate_with_negative_values(self, rule_engine):
        """Test evaluation with negative values."""
        indicator_values = {
            "PRICE": -10.0,
            "MA5": -20.0,
            "MA10": -30.0,
            "MA20": -40.0
        }
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, indicator_values)
        assert result is True  # -10.0 > -20.0
    
    def test_evaluate_with_very_large_values(self, rule_engine):
        """Test evaluation with very large values."""
        indicator_values = {
            "PRICE": 1e10,
            "MA5": 1e9,
            "MA10": 1e8,
            "MA20": 1e7
        }
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, indicator_values)
        assert result is True  # 1e10 > 1e9
    
    def test_evaluate_with_very_small_values(self, rule_engine):
        """Test evaluation with very small values."""
        indicator_values = {
            "PRICE": 1e-10,
            "MA5": 1e-9,
            "MA10": 1e-8,
            "MA20": 1e-7
        }
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": "<",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, indicator_values)
        assert result is True  # 1e-10 < 1e-9
    
    def test_evaluate_with_integer_values(self, rule_engine):
        """Test evaluation with integer values."""
        indicator_values = {
            "PRICE": 100,
            "MA5": 95,
            "MA10": 90,
            "MA20": 85
        }
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, indicator_values)
        assert result is True  # 100 > 95
    
    def test_evaluate_with_mixed_numeric_types(self, rule_engine):
        """Test evaluation with mixed integer and float values."""
        indicator_values = {
            "PRICE": 100.5,  # float
            "MA5": 100,      # int
            "MA10": 99.5,    # float
            "MA20": 99       # int
        }
        
        rule = {
            "id": "test_rule",
            "name": "Test Rule",
            "type": "BUY",
            "logic": "AND",
            "conditions": [
                {
                    "left": "PRICE",
                    "op": ">",
                    "right": "MA5"
                }
            ]
        }
        
        result = rule_engine.evaluate(rule, indicator_values)
        assert result is True  # 100.5 > 100