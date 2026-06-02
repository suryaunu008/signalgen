"""
Data Sources Package

This package provides abstraction layer for different market data sources.
All data sources implement BaseDataSource interface for consistency.

Available Data Sources:
- IBKRDataSource: Interactive Brokers via ib_insync
- YahooDataSource: Yahoo Finance via yfinance
- CachedDataSource: SQLite cache wrapper for historical OHLCV data

Usage:
    from app.data_sources import CachedDataSource, IBKRDataSource, YahooDataSource
    
    # For real-time and intraday backtesting
    ibkr = IBKRDataSource(host='127.0.0.1', port=7497)
    
    # For swing trading and daily backtesting
    yahoo = YahooDataSource()
"""

from .base_data_source import BaseDataSource
from .cached_data_source import CachedDataSource
from .ibkr_data_source import IBKRDataSource
from .yahoo_data_source import YahooDataSource

__all__ = ['BaseDataSource', 'CachedDataSource', 'IBKRDataSource', 'YahooDataSource']
