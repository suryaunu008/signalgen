import math

import pytest

from app.core.indicator_engine import IndicatorEngine
from app.core.rule_engine import RuleEngine, RuleValidationError


def _rule(left, op, right):
    return {
        "id": 1,
        "name": "dynamic",
        "type": "custom",
        "logic": "AND",
        "conditions": [{"left": left, "op": op, "right": right}],
    }


def test_rule_engine_accepts_existing_and_dynamic_operands():
    engine = RuleEngine()

    for rule in [
        _rule("EMA20", ">", "RSI14"),
        _rule("PRICE_PREV_5", ">", "EMA12"),
        _rule("RSI7", "<", 40),
        _rule("REL_VOLUME_10", ">=", 1.3),
    ]:
        engine.validate_rule(rule)


@pytest.mark.parametrize("operand", ["PRICE_PREV_0", "EMAabc", "RSI9999"])
def test_rule_engine_rejects_invalid_dynamic_operands(operand):
    engine = RuleEngine()

    with pytest.raises(RuleValidationError):
        engine.validate_rule(_rule(operand, ">", "PRICE"))


def test_rule_engine_allows_dynamic_crossable_operands():
    engine = RuleEngine()
    rule = _rule("EMA12", "CROSS_UP", "EMA20")
    indicators = {
        "EMA12": 11,
        "EMA20": 10,
        "EMA12_PREV": 9,
        "EMA20_PREV": 10,
    }

    engine.validate_rule(rule)
    assert engine.evaluate(rule, indicators) is True


def test_indicator_engine_generates_dynamic_price_indicator_and_volume_values():
    indicator_engine = IndicatorEngine(timeframe="1m")
    indicator_engine.set_required_operands(_rule("PRICE_PREV_3", ">", "REL_VOLUME_10"))

    for i in range(1, 41):
        indicator_engine.update_candle_data(
            symbol="AAPL",
            open_price=float(i),
            high=float(i) + 1,
            low=float(i) - 0.5,
            close=float(i),
            timestamp=float(i * 60),
            volume=100 + i,
        )

    indicators = indicator_engine.get_indicators("AAPL")

    assert indicators["PRICE_PREV_3"] == indicators["PRICE"] - 3
    assert "REL_VOLUME_10" in indicators
    assert "SMA_VOLUME_10" in indicators
    assert math.isfinite(indicators["REL_VOLUME_10"])


def test_indicator_engine_generates_dynamic_technical_indicators():
    indicator_engine = IndicatorEngine(timeframe="1m")
    indicator_engine.set_required_operands(_rule("EMA12", ">", "RSI7"))

    for i in range(1, 60):
        price = 100 + (i * 0.5)
        indicator_engine.update_candle_data(
            symbol="MSFT",
            open_price=price,
            high=price + 1,
            low=price - 1,
            close=price,
            timestamp=float(i * 60),
            volume=1000 + i,
        )

    indicators = indicator_engine.get_indicators("MSFT")

    assert "EMA12" in indicators
    assert "RSI7" in indicators
    assert math.isfinite(indicators["EMA12"])
    assert math.isfinite(indicators["RSI7"])
