"""Market data infrastructure layer — A-share local data pipeline.

Non-F-stage module. Provides Tushare data sync, Parquet/DuckDB storage,
and local query API for backtest price snapshots and market calendars.
"""
from __future__ import annotations

from finer.market_data.config import MarketDataConfig, load_market_data_config
from finer.market_data.providers import TushareCalendarProvider, TusharePriceProvider

__all__ = [
    "MarketDataConfig",
    "TushareCalendarProvider",
    "TusharePriceProvider",
    "load_market_data_config",
]
