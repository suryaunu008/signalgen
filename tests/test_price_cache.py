import asyncio
from datetime import datetime, timedelta

from app.data_sources.base_data_source import BaseDataSource
from app.data_sources.cached_data_source import CachedDataSource
from app.storage.sqlite_repo import SQLiteRepository


class FakeDataSource(BaseDataSource):
    def __init__(self, candles=None):
        self.candles = candles or []
        self.calls = []

    async def fetch_historical_data(self, symbol, start_date, end_date, timeframe):
        self.calls.append((symbol, start_date, end_date, timeframe))
        return list(self.candles)

    async def validate_symbol(self, symbol):
        return True

    def get_supported_timeframes(self):
        return ["1m", "5m", "15m", "1h", "4h", "1d"]


def _candle(day, close=None):
    close_value = float(close if close is not None else day)
    return {
        "timestamp": datetime(2024, 1, day),
        "open": close_value - 0.5,
        "high": close_value + 1,
        "low": close_value - 1,
        "close": close_value,
        "volume": 1000 + day,
    }


def _candle_at(timestamp, close=1.0, is_final=True):
    return {
        "timestamp": timestamp,
        "open": close - 0.5,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1000,
        "is_final": is_final,
    }


def _repo(tmp_path):
    repo = SQLiteRepository(str(tmp_path / "cache.db"))
    repo.initialize_database()
    return repo


def test_repository_upserts_and_reads_cached_candles(tmp_path):
    repo = _repo(tmp_path)
    repo.upsert_candles("aapl", "1d", [_candle(1), _candle(2)], data_source="yahoo")
    repo.upsert_candles("AAPL", "1d", [_candle(1, close=42)], data_source="yahoo")

    candles = repo.get_cached_candles(
        "AAPL",
        "1d",
        datetime(2024, 1, 1),
        datetime(2024, 1, 3),
        data_source="yahoo",
    )

    assert len(candles) == 2
    assert candles[0]["timestamp"] == datetime(2024, 1, 1)
    assert candles[0]["close"] == 42
    assert candles[0]["is_final"] is True
    assert candles[1]["timestamp"] == datetime(2024, 1, 2)


def test_repository_stores_non_final_candle_status(tmp_path):
    repo = _repo(tmp_path)
    repo.upsert_candles(
        "AAPL",
        "1h",
        [_candle_at(datetime(2024, 1, 1, 10), close=10, is_final=False)],
        data_source="yahoo",
    )

    candles = repo.get_cached_candles(
        "AAPL",
        "1h",
        datetime(2024, 1, 1),
        datetime(2024, 1, 2),
        data_source="yahoo",
    )
    coverage = repo.get_price_cache_coverage(
        "AAPL",
        "1h",
        datetime(2024, 1, 1),
        datetime(2024, 1, 2),
        data_source="yahoo",
    )

    assert candles[0]["is_final"] is False
    assert coverage["last_final_timestamp"] is None
    assert coverage["non_final_count"] == 1


def test_cached_data_source_fetches_and_stores_on_cache_miss(tmp_path):
    repo = _repo(tmp_path)
    wrapped = FakeDataSource([_candle(1), _candle(2), _candle(3)])
    cached = CachedDataSource(wrapped, repo, data_source_name="yahoo")

    result = asyncio.run(cached.fetch_historical_data(
        "AAPL",
        datetime(2024, 1, 1),
        datetime(2024, 1, 4),
        "1d",
    ))

    assert len(result) == 3
    assert len(wrapped.calls) == 1
    assert len(repo.get_cached_candles("AAPL", "1d", datetime(2024, 1, 1), datetime(2024, 1, 4))) == 3


def test_cached_data_source_uses_cache_when_range_is_covered(tmp_path):
    repo = _repo(tmp_path)
    repo.upsert_candles("AAPL", "1d", [_candle(1), _candle(2), _candle(3)], data_source="yahoo")
    wrapped = FakeDataSource([_candle(9)])
    cached = CachedDataSource(wrapped, repo, data_source_name="yahoo")

    result = asyncio.run(cached.fetch_historical_data(
        "AAPL",
        datetime(2024, 1, 1),
        datetime(2024, 1, 4),
        "1d",
    ))

    assert [c["close"] for c in result] == [1, 2, 3]
    assert wrapped.calls == []


def test_cached_data_source_refreshes_partial_cache(tmp_path):
    repo = _repo(tmp_path)
    repo.upsert_candles("AAPL", "1d", [_candle(1)], data_source="yahoo")
    wrapped = FakeDataSource([_candle(1), _candle(2), _candle(3)])
    cached = CachedDataSource(wrapped, repo, data_source_name="yahoo")

    result = asyncio.run(cached.fetch_historical_data(
        "AAPL",
        datetime(2024, 1, 1),
        datetime(2024, 1, 4),
        "1d",
    ))

    assert len(wrapped.calls) == 1
    assert wrapped.calls[0][1] == datetime(2024, 1, 2)
    assert [c["close"] for c in result] == [1, 2, 3]


def test_cached_data_source_refreshes_from_non_final_candle(tmp_path):
    repo = _repo(tmp_path)
    repo.upsert_candles(
        "AAPL",
        "1h",
        [
            _candle_at(datetime(2024, 1, 1, 9), close=9, is_final=True),
            _candle_at(datetime(2024, 1, 1, 10), close=10, is_final=False),
        ],
        data_source="yahoo",
    )
    wrapped = FakeDataSource([
        _candle_at(datetime(2024, 1, 1, 10), close=11, is_final=True),
        _candle_at(datetime(2024, 1, 1, 11), close=12, is_final=True),
    ])
    cached = CachedDataSource(wrapped, repo, data_source_name="yahoo")

    result = asyncio.run(cached.fetch_historical_data(
        "AAPL",
        datetime(2024, 1, 1, 9),
        datetime(2024, 1, 1, 12),
        "1h",
    ))

    assert wrapped.calls[0][1] == datetime(2024, 1, 1, 10)
    assert [c["close"] for c in result] == [9, 11, 12]


def test_cached_data_source_reuses_recent_current_refresh_when_end_moves(tmp_path):
    repo = _repo(tmp_path)
    now = datetime.utcnow().replace(microsecond=0)
    candles = [
        {
            **_candle(1),
            "timestamp": now - timedelta(hours=4),
        },
        {
            **_candle(2),
            "timestamp": now - timedelta(hours=3),
        },
    ]
    wrapped = FakeDataSource(candles)
    cached = CachedDataSource(wrapped, repo, data_source_name="yahoo")

    first_result = asyncio.run(cached.fetch_historical_data(
        "AAPL",
        now - timedelta(days=2),
        now,
        "1h",
    ))
    second_result = asyncio.run(cached.fetch_historical_data(
        "AAPL",
        now - timedelta(days=2),
        now + timedelta(seconds=30),
        "1h",
    ))

    assert len(wrapped.calls) == 1
    assert [c["timestamp"] for c in second_result] == [c["timestamp"] for c in first_result]


def test_cached_data_source_keeps_timeframes_separate(tmp_path):
    repo = _repo(tmp_path)
    repo.upsert_candles("AAPL", "1d", [_candle(1), _candle(2), _candle(3)], data_source="yahoo")
    wrapped = FakeDataSource([{
        **_candle(1),
        "timestamp": datetime(2024, 1, 1, 9, 30),
    }])
    cached = CachedDataSource(wrapped, repo, data_source_name="yahoo")

    result = asyncio.run(cached.fetch_historical_data(
        "AAPL",
        datetime(2024, 1, 1),
        datetime(2024, 1, 2),
        "1h",
    ))

    assert len(wrapped.calls) == 1
    assert result[0]["timestamp"] == datetime(2024, 1, 1, 9, 30)
    assert repo.get_cached_candles("AAPL", "4h", datetime(2024, 1, 1), datetime(2024, 1, 4)) == []


def test_cached_data_source_stores_4h_as_its_own_timeframe(tmp_path):
    repo = _repo(tmp_path)
    four_hour_candle = {
        **_candle(1),
        "timestamp": datetime(2024, 1, 1, 12, 0),
    }
    wrapped = FakeDataSource([four_hour_candle])
    cached = CachedDataSource(wrapped, repo, data_source_name="yahoo")

    asyncio.run(cached.fetch_historical_data(
        "AAPL",
        datetime(2024, 1, 1),
        datetime(2024, 1, 1, 16, 0),
        "4h",
    ))

    assert repo.get_cached_candles("AAPL", "1h", datetime(2024, 1, 1), datetime(2024, 1, 2)) == []
    stored_4h = repo.get_cached_candles("AAPL", "4h", datetime(2024, 1, 1), datetime(2024, 1, 2))
    assert len(stored_4h) == 1
    assert stored_4h[0]["timestamp"] == datetime(2024, 1, 1, 12, 0)
