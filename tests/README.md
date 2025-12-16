# Test Suite for SignalGen Rule Engine

This directory contains comprehensive tests for the Rule Engine component of the SignalGen application.

## Test Coverage

The test suite provides 100% code coverage for the `app/core/rule_engine.py` module, ensuring all functionality is thoroughly tested.

## Test Categories

### 1. Rule Validation Tests (`TestRuleValidation`)
- Valid rule structure validation
- Missing required fields
- Invalid logic operators
- Empty conditions
- Invalid condition structure
- Unsupported operands and operators
- Invalid cooldown values
- Non-dictionary inputs

### 2. Rule Evaluation Tests (`TestRuleEvaluation`)
- Simple true/false conditions
- Multiple conditions with AND logic
- All supported operators (>, <, >=, <=)
- Boundary conditions (equal values)
- Missing indicators
- Non-numeric indicator values
- Empty conditions

### 3. Deterministic Behavior Tests (`TestDeterministicBehavior`)
- Single-threaded deterministic evaluation
- Multi-threaded deterministic evaluation
- Consistency across different instances

### 4. Error Handling Tests (`TestErrorHandling`)
- Invalid rule evaluation
- Missing condition fields
- Unsupported operators
- JSON parsing errors
- Unexpected error handling

### 5. Performance Tests (`TestPerformance`)
- Evaluation performance (10,000 operations < 1 second)
- Validation performance (10,000 operations < 1 second)

### 6. Property-Based Tests (`TestPropertyBased`)
- Parametrized evaluation with various indicator combinations
- Randomized AND logic testing

### 7. Thread Safety Tests (`TestThreadSafety`)
- Concurrent evaluation
- Concurrent validation
- Multiple instance evaluation

### 8. Edge Cases Tests (`TestEdgeCases`)
- Zero values
- Negative values
- Very large values
- Very small values
- Integer values
- Mixed numeric types

## Running Tests

### Prerequisites
Install the required dependencies:
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
pytest tests/test_rule_engine.py -v
```

### Run with Coverage
```bash
pytest tests/test_rule_engine.py --cov=app.core.rule_engine --cov-report=term-missing
```

### Run Specific Test Categories
```bash
# Run only validation tests
pytest tests/test_rule_engine.py::TestRuleValidation -v

# Run only performance tests
pytest tests/test_rule_engine.py::TestPerformance -v
```

## Test Data Fixtures

The test suite includes several fixtures for consistent testing:

- `rule_engine`: Fresh RuleEngine instance for each test
- `sample_indicator_values`: Standard indicator values (PRICE: 100.50, MA5: 98.75, etc.)
- `valid_rule`: A valid rule structure for testing
- `complex_rule`: A rule with multiple conditions

## Test Configuration

The `pytest.ini` file configures:
- Verbose output
- Coverage reporting
- 95% minimum coverage requirement
- Test discovery patterns

## Mocking Strategy

Tests use appropriate mocking to:
- Bypass validation when testing evaluation logic
- Simulate unexpected errors
- Test error handling paths
- Isolate components under test

## Performance Benchmarks

The performance tests ensure:
- Rule evaluation completes 10,000 operations in < 1 second
- Rule validation completes 10,000 operations in < 1 second
- Suitable for high-frequency trading scenarios

## Thread Safety Verification

Thread safety tests verify:
- Concurrent evaluation produces consistent results
- No race conditions in validation
- Multiple instances work correctly in parallel