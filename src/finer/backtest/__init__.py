"""Backtest Module — Portfolio simulation and performance analysis.

This module provides backtesting capabilities for KOL trade signals:
- Portfolio simulation with realistic costs
- Performance metrics calculation
- KOL attribution analysis
- Price data providers with caching
"""

from finer.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    PortfolioSimulator,
    PortfolioSnapshot,
    Position,
    Trade,
    PositionSide,
    ExitReason,
    run_simple_backtest,
)
from finer.backtest.prices import (
    PriceProvider,
    CachedPriceProvider,
    MockPriceProvider,
    MultiMarketPriceProvider,
    PriceCache,
    PriceCacheConfig,
)

__all__ = [
    # Engine
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "PortfolioSimulator",
    "PortfolioSnapshot",
    "Position",
    "Trade",
    "PositionSide",
    "ExitReason",
    "run_simple_backtest",
    # Price providers
    "PriceProvider",
    "CachedPriceProvider",
    "MockPriceProvider",
    "MultiMarketPriceProvider",
    "PriceCache",
    "PriceCacheConfig",
]
