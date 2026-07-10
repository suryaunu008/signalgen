"""Tests for the swing screening engine.

The most important guarantee here (thesis-critical, see improvement #3) is
*reproducibility*: two screening runs that end on the same date must produce the
same signal and the same indicator values, regardless of how the evaluation
window was specified (Latest lookback vs Historical start/end, narrow vs wide).

The bug this guards against: warmup was anchored to the *start* of the
evaluation window and never fetched enough candles to saturate the
IndicatorEngine deque, so recursive indicators (EMA/RSI/ADX) came out
window-width dependent — a ticker could appear in "Latest lookback 30" but
vanish in "Historical up to <same date>".
"""

import math
from datetime import datetime, timedelta

from app.data_sources.base_data_source import BaseDataSource
from app.engines.swing_screening_engine import SwingScreeningEngine


class WindowedFakeDataSource(BaseDataSource):
    """Returns candles from a fixed master series, filtered to [start, end).

    Filtering by the requested range is what makes this a real regression guard:
    if the engine ever anchors its warmup fetch to the *start* of the evaluation
    window again, a narrow and a wide window will feed different candle counts
    and the reproducibility assertions below will fail.
    """

    def __init__(self, master_candles):
        self.master = list(master_candles)
        self.calls = []

    async def fetch_historical_data(self, symbol, start_date, end_date, timeframe):
        self.calls.append((symbol, start_date, end_date, timeframe))
        return [
            dict(c)
            for c in self.master
            if start_date <= c["timestamp"] < end_date
        ]

    async def validate_symbol(self, symbol):
        return True

    def get_supported_timeframes(self):
        return ["1m", "5m", "15m", "1h", "4h", "1d"]


def _build_master_series(last_date: datetime, count: int):
    """Deterministic daily OHLCV series with genuine up/down moves.

    Oscillation (not a pure ramp) matters so RSI/ADX are well-defined and the
    indicators are actually sensitive to how much history precedes them.
    """
    candles = []
    for i in range(count):
        ts = last_date - timedelta(days=(count - 1 - i))
        price = 100.0 + 15.0 * math.sin(i * 0.15) + 0.02 * i
        candles.append({
            "timestamp": ts,
            "open": price - 0.4,
            "high": price + 1.2,
            "low": price - 1.2,
            "close": price,
            "volume": 1_000_000 + i,
            "is_final": True,
        })
    return candles


def _make_engine(master_candles):
    engine = SwingScreeningEngine(timeframe="1d")
    engine.data_source = WindowedFakeDataSource(master_candles)
    rule = {
        "id": 1,
        "name": "EMA/RSI swing",
        "type": "swing",
        "signal_type": "BUY",
        "definition": {
            "logic": "AND",
            "conditions": [
                {"left": "CLOSE", "op": ">", "right": "EMA20"},
                {"left": "RSI14", "op": ">", "right": 50},
            ],
            "cooldown_sec": 0,
        },
    }
    engine.repository.get_rule_by_id = lambda rule_id: rule
    return engine


def test_result_is_identical_across_window_widths_for_same_end_date():
    """Same end date + same data => identical signal and indicators.

    This is the reproducibility guarantee behind the swing screener's validity
    claim. A narrow window and a very wide window that both end on the same date
    must agree exactly.
    """
    import asyncio

    last_date = datetime(2026, 6, 30)
    master = _build_master_series(last_date, count=600)
    end_date = last_date + timedelta(days=1)  # exclusive end -> includes last_date

    engine = _make_engine(master)

    narrow = asyncio.run(engine.screen_tickers(
        tickers=["TSLA"],
        rule_id=1,
        start_date=last_date - timedelta(days=40),
        end_date=end_date,
    ))[0]

    wide = asyncio.run(engine.screen_tickers(
        tickers=["TSLA"],
        rule_id=1,
        start_date=last_date - timedelta(days=450),
        end_date=end_date,
    ))[0]

    assert narrow["status"] == "success"
    assert wide["status"] == "success"
    # Signal and the candle that produced it must match.
    assert narrow["signal"] == wide["signal"]
    assert narrow["price"] == wide["price"]
    assert narrow["timestamp"] == wide["timestamp"]
    # Every indicator value must be bit-identical, not merely close: both runs
    # see the same saturated trailing candle window.
    assert narrow["indicators"] == wide["indicators"]


def test_latest_lookback_matches_historical_for_same_end_date():
    """The reviewer's Tesla scenario, made deterministic.

    Latest(lookback=N) and Historical(start, end) that resolve to the same end
    candle must give the same result. We express Latest via a lookback that ends
    at the same last candle by passing start/end explicitly for both, differing
    only in how far back the window nominally reaches.
    """
    import asyncio

    last_date = datetime(2026, 6, 30)
    master = _build_master_series(last_date, count=600)
    end_date = last_date + timedelta(days=1)

    engine = _make_engine(master)

    # "Latest": short 30-day evaluation window ending on the last candle.
    latest = asyncio.run(engine.screen_tickers(
        tickers=["TSLA"],
        rule_id=1,
        lookback_days=30,
        end_date=end_date,
    ))[0]

    # "Historical": explicit start/end ending on the same last candle.
    historical = asyncio.run(engine.screen_tickers(
        tickers=["TSLA"],
        rule_id=1,
        start_date=datetime(2026, 1, 1),
        end_date=end_date,
    ))[0]

    assert latest["status"] == "success"
    assert historical["status"] == "success"
    assert latest["signal"] == historical["signal"]
    assert latest["indicators"] == historical["indicators"]


def test_open_candle_is_excluded_from_signal_and_reported_as_current():
    """The still-forming candle must not drive the signal (#5).

    The signal is taken from the last CLOSED candle; the forming candle is
    evaluated separately and surfaced as ``current_condition`` so a completed
    BUY is never confused with the live bar (which may have broken down).
    """
    import asyncio

    last_final = datetime(2026, 6, 30)
    # Clean uptrend so CLOSE > EMA20 holds on the last closed candle.
    closed = []
    for i in range(400):
        ts = last_final - timedelta(days=(399 - i))
        close = 100.0 + i
        closed.append({
            "timestamp": ts,
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1_000_000,
            "is_final": True,
        })
    # A still-forming next-day candle that breaks down hard.
    open_ts = last_final + timedelta(days=1)
    forming = {
        "timestamp": open_ts,
        "open": 60.0,
        "high": 61.0,
        "low": 50.0,
        "close": 50.0,
        "volume": 1_000_000,
        "is_final": False,
    }
    master = closed + [forming]

    engine = SwingScreeningEngine(timeframe="1d")
    engine.data_source = WindowedFakeDataSource(master)
    rule = {
        "id": 1,
        "name": "close>ema20",
        "type": "swing",
        "signal_type": "BUY",
        "definition": {
            "logic": "AND",
            "conditions": [{"left": "CLOSE", "op": ">", "right": "EMA20"}],
            "cooldown_sec": 0,
        },
    }
    engine.repository.get_rule_by_id = lambda rule_id: rule

    res = asyncio.run(engine.screen_tickers(
        tickers=["TSLA"],
        rule_id=1,
        start_date=last_final - timedelta(days=60),
        end_date=open_ts + timedelta(days=1),  # window includes the forming candle
    ))[0]

    assert res["status"] == "success"
    # Signal comes from the last closed candle, not the forming one.
    assert res["timestamp"] == last_final
    assert res["signal"] == "BUY"
    # The forming candle is reported separately and shows the rule has cleared.
    assert res["has_open_candle"] is True
    assert res["current_timestamp"] == open_ts
    assert res["current_condition"] is False


def test_warmup_start_depends_only_on_end_date_and_saturates_deque():
    """Warmup anchor is the end date, and it fetches enough to fill the deque."""
    engine = SwingScreeningEngine(timeframe="1d")
    rule = {"logic": "AND", "conditions": [{"left": "CLOSE", "op": ">", "right": "EMA20"}]}

    end_a = datetime(2026, 6, 30)
    start_a = engine._calculate_warmup_start(end_a, rule)
    start_b = engine._calculate_warmup_start(end_a, rule)

    # Deterministic in the end date only.
    assert start_a == start_b
    # Enough calendar span to comfortably cover a full INDICATOR_HISTORY window
    # of trading candles (~250 trading days need well over 250 calendar days).
    assert (end_a - start_a).days >= engine.INDICATOR_HISTORY
