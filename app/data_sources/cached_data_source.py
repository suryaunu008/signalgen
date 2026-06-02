"""
Cached Data Source Module

Wraps another BaseDataSource and persists historical OHLCV candles in SQLite.
The wrapped source remains responsible for provider-specific behavior such as
Yahoo retention limits and 4h aggregation.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .base_data_source import BaseDataSource
from ..storage.sqlite_repo import SQLiteRepository


class CachedDataSource(BaseDataSource):
    """SQLite-backed cache wrapper for historical OHLCV data sources."""

    RECENT_REFRESH_TTL = timedelta(minutes=15)

    TIMEFRAME_SECONDS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    def __init__(
        self,
        wrapped: BaseDataSource,
        repository: SQLiteRepository,
        data_source_name: str = "yahoo"
    ):
        self.wrapped = wrapped
        self.repository = repository
        self.data_source_name = data_source_name.lower()
        self.logger = logging.getLogger(__name__)
        self.repository.initialize_database()

    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> List[Dict]:
        if not self.validate_timeframe(timeframe):
            raise ValueError(f"Timeframe '{timeframe}' not supported. Use one of: {self.get_supported_timeframes()}")

        cached = self.repository.get_cached_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            data_source=self.data_source_name
        )
        coverage = self.repository.get_price_cache_coverage(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            data_source=self.data_source_name
        )

        if self._cache_covers_range(cached, coverage, start_date, end_date, timeframe):
            self.logger.info(
                "OHLCV cache hit: %s %s %s candles=%s",
                self.data_source_name,
                symbol.upper(),
                timeframe,
                len(cached)
            )
            return cached

        cache_state = "refresh" if cached else "miss"
        self.logger.info(
            "OHLCV cache %s: %s %s %s cached=%s",
            cache_state,
            self.data_source_name,
            symbol.upper(),
            timeframe,
            len(cached)
        )

        fetched = await self.wrapped.fetch_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe
        )
        fetched = fetched or []

        if fetched:
            upserted = self.repository.upsert_candles(
                symbol=symbol,
                timeframe=timeframe,
                candles=fetched,
                data_source=self.data_source_name
            )
            self.logger.info(
                "OHLCV cache stored: %s %s %s fetched=%s upserted=%s",
                self.data_source_name,
                symbol.upper(),
                timeframe,
                len(fetched),
                upserted
            )

        refreshed = self.repository.get_cached_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            data_source=self.data_source_name
        )
        self.logger.info(
            "OHLCV cache return: %s %s %s candles=%s",
            self.data_source_name,
            symbol.upper(),
            timeframe,
            len(refreshed)
        )
        return refreshed

    async def validate_symbol(self, symbol: str) -> bool:
        return await self.wrapped.validate_symbol(symbol)

    def get_supported_timeframes(self) -> List[str]:
        return self.wrapped.get_supported_timeframes()

    def _cache_covers_range(
        self,
        cached: List[Dict[str, Any]],
        coverage: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        timeframe: str
    ) -> bool:
        if not cached:
            return False

        start = self._normalize_dt(start_date)
        end = self._normalize_dt(end_date)
        first = self._normalize_dt(cached[0]['timestamp'])
        last = self._normalize_dt(cached[-1]['timestamp'])
        start_tolerance = self._start_coverage_tolerance(timeframe)
        end_tolerance = self._end_coverage_tolerance(timeframe)

        start_is_covered = first <= (start + start_tolerance)
        end_is_covered = last >= (end - end_tolerance)
        if start_is_covered and end_is_covered:
            return True

        return self._has_recent_current_refresh(coverage, end)

    def _has_recent_current_refresh(self, coverage: Dict[str, Any], end_date: datetime) -> bool:
        """
        Treat a current open-ended request as covered after a recent refresh.

        Screener calls without explicit dates use datetime.now(), so two identical
        runs have slightly different end_date values. During non-trading periods
        Yahoo may return no candle near that moving end, but a fresh updated_at
        means we just attempted the provider range and can reuse the cache.
        """
        last_updated_at = coverage.get('last_updated_at') if coverage else None
        if not last_updated_at:
            return False

        now = datetime.utcnow()
        end = self._normalize_dt(end_date)
        updated = self._normalize_dt(last_updated_at)
        is_current_request = end >= (now - self.RECENT_REFRESH_TTL)
        is_recent_refresh = updated >= (now - self.RECENT_REFRESH_TTL)
        return is_current_request and is_recent_refresh

    def _start_coverage_tolerance(self, timeframe: str) -> timedelta:
        if timeframe == "1d":
            return timedelta(days=3)
        return timedelta(days=1)

    def _end_coverage_tolerance(self, timeframe: str) -> timedelta:
        seconds = self.TIMEFRAME_SECONDS.get(timeframe, 86400)
        return timedelta(seconds=seconds * 1.1)

    def _normalize_dt(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
