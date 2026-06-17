import math

import numpy as np
import pytest
import talib

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
        _rule("HIGH", ">", "LOW"),
        _rule("CLOSE_PREV_5", ">", "OPEN_PREV_5"),
        _rule("PRICE_PREV_5", ">", "EMA12"),
        _rule("EMA12_PREV_3", ">", "RSI7_PREV_2"),
        _rule("MACD_HIST_PREV_2", ">", 0),
        _rule("RSI7", "<", 40),
        _rule("REL_VOLUME_10", ">=", 1.3),
        _rule("STOCH_K", ">", "STOCH_D"),
        _rule("ICHIMOKU_CONVERSION", ">", "ICHIMOKU_BASE"),
        _rule("PATTERN_CDLDOJI", ">", 0),
        _rule("PATTERN_BULLISH_ENGULFING", ">", 0),
        _rule("PATTERN_CDLHAMMER_PREV_1", ">", 0),
    ]:
        engine.validate_rule(rule)


@pytest.mark.parametrize("operand", ["PRICE_PREV_0", "EMAabc", "RSI9999", "EMA20_PREV_0", "UNKNOWN_PREV_3"])
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


def test_rule_engine_applies_optional_operand_multipliers():
    engine = RuleEngine()
    rule = _rule("PRICE", ">", "MA20")
    rule["conditions"][0]["right_multiplier"] = 1.2

    engine.validate_rule(rule)
    assert engine.evaluate(rule, {"PRICE": 121, "MA20": 100}) is True
    assert engine.evaluate(rule, {"PRICE": 119, "MA20": 100}) is False


def test_rule_engine_multiplier_defaults_to_one_for_legacy_rules():
    engine = RuleEngine()
    rule = _rule("PRICE", ">", "MA20")

    engine.validate_rule(rule)
    assert engine.evaluate(rule, {"PRICE": 101, "MA20": 100}) is True


@pytest.mark.parametrize("multiplier", [0, -1, float("inf"), "abc"])
def test_rule_engine_rejects_invalid_multipliers(multiplier):
    engine = RuleEngine()
    rule = _rule("PRICE", ">", "MA20")
    rule["conditions"][0]["right_multiplier"] = multiplier

    with pytest.raises(RuleValidationError):
        engine.validate_rule(rule)


def test_rule_engine_rejects_multipliers_for_cross_operators():
    engine = RuleEngine()
    rule = _rule("EMA12", "CROSS_UP", "EMA20")
    rule["conditions"][0]["left_multiplier"] = 1.1

    with pytest.raises(RuleValidationError):
        engine.validate_rule(rule)


@pytest.mark.parametrize(
    ("left", "right", "indicators"),
    [
        (
            "STOCH_K",
            "STOCH_D",
            {"STOCH_K": 55, "STOCH_D": 50, "STOCH_K_PREV": 45, "STOCH_D_PREV": 50},
        ),
        (
            "ICHIMOKU_CONVERSION",
            "ICHIMOKU_BASE",
            {
                "ICHIMOKU_CONVERSION": 105,
                "ICHIMOKU_BASE": 100,
                "ICHIMOKU_CONVERSION_PREV": 95,
                "ICHIMOKU_BASE_PREV": 100,
            },
        ),
    ],
)
def test_rule_engine_allows_new_indicator_crossable_operands(left, right, indicators):
    engine = RuleEngine()
    rule = _rule(left, "CROSS_UP", right)

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


def test_indicator_engine_generates_ohlc_and_generic_price_prev_n_values():
    indicator_engine = IndicatorEngine(timeframe="1m")
    indicator_engine.set_required_operands({"HIGH_PREV_2", "CLOSE_PREV_3", "PRICE_PREV_3"})

    for i in range(2, 21):
        indicator_engine.update_candle_data(
            symbol="AAPL",
            open_price=float(i),
            high=float(i) + 2,
            low=float(i) - 1,
            close=float(i) + 0.5,
            timestamp=float(i * 60),
            volume=100 + i,
        )

    indicators = indicator_engine.get_indicators("AAPL")

    assert indicators["OPEN"] == 19
    assert indicators["HIGH"] == 21
    assert indicators["LOW"] == 18
    assert indicators["CLOSE"] == indicators["PRICE"] == 19.5
    assert indicators["PREV_OPEN"] == indicators["OPEN_PREV"] == 18
    assert indicators["PREV_CLOSE"] == indicators["CLOSE_PREV"] == 18.5
    assert indicators["HIGH_PREV_2"] == 17 + 2
    assert indicators["CLOSE_PREV_3"] == 16.5
    assert indicators["PRICE_PREV_3"] == indicators["CLOSE_PREV_3"]


def test_indicator_engine_generates_dynamic_technical_indicators():
    indicator_engine = IndicatorEngine(timeframe="1m")
    indicator_engine.set_required_operands({
        "EMA12",
        "RSI7",
        "EMA12_PREV_3",
        "RSI7_PREV_2",
        "MACD_HIST_PREV_1",
    })

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
    assert "EMA12_PREV_3" in indicators
    assert "RSI7_PREV_2" in indicators
    assert "MACD_HIST_PREV_1" in indicators
    assert math.isfinite(indicators["EMA12"])
    assert math.isfinite(indicators["RSI7"])
    assert math.isfinite(indicators["EMA12_PREV_3"])
    assert math.isfinite(indicators["RSI7_PREV_2"])
    assert math.isfinite(indicators["MACD_HIST_PREV_1"])


def test_indicator_engine_generates_stochastic_and_ichimoku_indicators():
    indicator_engine = IndicatorEngine(timeframe="1m")
    indicator_engine.set_required_operands({
        "ICHIMOKU_CONVERSION_PREV_2",
        "ICHIMOKU_BASE_PREV_2",
        "ICHIMOKU_A_PREV_2",
        "ICHIMOKU_B_PREV_2",
    })

    for i in range(1, 82):
        price = 100 + (i * 0.3) + ((i % 7) * 0.2)
        indicator_engine.update_candle_data(
            symbol="NVDA",
            open_price=price - 0.5,
            high=price + 2,
            low=price - 2,
            close=price,
            timestamp=float(i * 60),
            volume=2000 + i,
        )

    indicators = indicator_engine.get_indicators("NVDA")

    for key in [
        "STOCH_K",
        "STOCH_D",
        "ICHIMOKU_CONVERSION",
        "ICHIMOKU_BASE",
        "ICHIMOKU_A",
        "ICHIMOKU_B",
        "ICHIMOKU_CONVERSION_PREV_2",
        "ICHIMOKU_BASE_PREV_2",
        "ICHIMOKU_A_PREV_2",
        "ICHIMOKU_B_PREV_2",
    ]:
        assert key in indicators
        assert math.isfinite(indicators[key])


def test_indicator_engine_warmup_for_stochastic_and_ichimoku_operands():
    stoch_engine = IndicatorEngine(timeframe="1m")
    stoch_engine.set_required_operands(_rule("STOCH_K", ">", "STOCH_D"))

    for i in range(1, 18):
        price = 50 + i
        stoch_engine.update_candle_data("AMD", price, price + 1, price - 1, price, float(i * 60), 100 + i)

    assert stoch_engine.is_symbol_ready("AMD") is False

    stoch_engine.update_candle_data("AMD", 68, 69, 67, 68, 18 * 60.0, 118)
    assert stoch_engine.is_symbol_ready("AMD") is True

    ichimoku_engine = IndicatorEngine(timeframe="1m")
    ichimoku_engine.set_required_operands(_rule("ICHIMOKU_A", ">", "ICHIMOKU_B"))

    for i in range(1, 53):
        price = 100 + i
        ichimoku_engine.update_candle_data("TSLA", price, price + 1, price - 1, price, float(i * 60), 500 + i)

    assert ichimoku_engine.is_symbol_ready("TSLA") is False

    ichimoku_engine.update_candle_data("TSLA", 153, 154, 152, 153, 53 * 60.0, 553)
    assert ichimoku_engine.is_symbol_ready("TSLA") is True


def test_indicator_engine_generates_talib_candle_pattern_values(monkeypatch):
    def fake_doji(open_, high, low, close):
        values = np.zeros(len(close), dtype=int)
        values[-1] = 100
        return values

    def fake_engulfing(open_, high, low, close):
        values = np.zeros(len(close), dtype=int)
        values[-1] = -100
        return values

    monkeypatch.setattr(talib, "CDLDOJI", fake_doji)
    monkeypatch.setattr(talib, "CDLENGULFING", fake_engulfing)

    indicator_engine = IndicatorEngine(timeframe="1m")
    indicator_engine.set_required_operands({
        "PATTERN_CDLDOJI",
        "PATTERN_BULLISH_ENGULFING",
        "PATTERN_BEARISH_ENGULFING",
        "PATTERN_CDLDOJI_PREV_1",
    })

    for i in range(1, 8):
        price = 100 + i
        indicator_engine.update_candle_data(
            symbol="AAPL",
            open_price=float(price),
            high=float(price + 1),
            low=float(price - 1),
            close=float(price),
            timestamp=float(i * 60),
            volume=100 + i,
        )

    indicators = indicator_engine.get_indicators("AAPL")

    assert indicators["PATTERN_CDLDOJI"] == 1.0
    assert indicators["PATTERN_BULLISH_ENGULFING"] == 0.0
    assert indicators["PATTERN_BEARISH_ENGULFING"] == 1.0
    assert indicators["PATTERN_CDLDOJI_PREV_1"] == 0.0


def test_rule_engine_warmup_for_candle_pattern_prev_n():
    engine = IndicatorEngine(timeframe="1m")
    engine.set_required_operands(_rule("PATTERN_CDLHAMMER_PREV_1", ">", 0))

    for i in range(1, 6):
        price = 50 + i
        engine.update_candle_data("AMD", price, price + 1, price - 1, price, float(i * 60), 100 + i)

    assert engine.is_symbol_ready("AMD") is False

    engine.update_candle_data("AMD", 56, 57, 55, 56, 6 * 60.0, 106)
    engine.update_candle_data("AMD", 57, 58, 56, 57, 7 * 60.0, 107)
    assert engine.is_symbol_ready("AMD") is True
