"""Market data providers — PriceProvider + MarketCalendarProvider adapters.

Connects market_data/infrastructure to backtest/prices.py protocol and
F5 timing policy via calendar queries.

Date format contract:
- PriceProvider protocol uses ISO dates (YYYY-MM-DD)
- LocalPro / Tushare uses YYYYMMDD
- Conversion happens at the provider boundary.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from finer.market_data.local_api import LocalPro

logger = logging.getLogger(__name__)


def _iso_to_yyyymmdd(iso_date: str) -> str:
    """Convert '2026-05-09' to '20260509'."""
    return iso_date.replace("-", "")


def _yyyymmdd_to_iso(yyyymmdd: str) -> str:
    """Convert '20260509' to '2026-05-09'."""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


# =============================================================================
# Tushare Price Provider
# =============================================================================


class TusharePriceProvider:
    """PriceProvider implementation backed by local Tushare Parquet data.

    Implements the PriceProvider protocol from backtest/prices.py.
    Supports forward-adjusted (qfq) and backward-adjusted (hfq) prices.
    """

    def __init__(self, data_dir: Path, adj: str = "qfq") -> None:
        self._api = LocalPro(data_dir)
        self._adj = adj

    def get_price(self, ticker: str, date: str) -> Optional[float]:
        """Get close price for ticker on ISO date.

        Args:
            ticker: Ticker symbol (e.g., '000001.SZ', '600519.SH').
            date: ISO date string (e.g., '2024-01-15').

        Returns:
            Close price as float, or None if unavailable.
        """
        trade_date = _iso_to_yyyymmdd(date)
        try:
            df = self._api.pro_bar(
                ts_code=ticker, start_date=trade_date, end_date=trade_date, adj=self._adj,
            )
            if df.empty:
                return None
            close = df.iloc[0]["close"]
            return float(close) if pd.notna(close) else None
        except Exception as e:
            logger.debug("get_price(%s, %s) failed: %s", ticker, date, e)
            return None

    def get_prices(
        self, ticker: str, start: str, end: str,
    ) -> List[Tuple[str, float]]:
        """Get close price series for ticker over ISO date range.

        Args:
            ticker: Ticker symbol.
            start: Start date (ISO format).
            end: End date (ISO format).

        Returns:
            List of (iso_date, close_price) tuples, sorted by date.
        """
        start_yyyymmdd = _iso_to_yyyymmdd(start)
        end_yyyymmdd = _iso_to_yyyymmdd(end)
        try:
            df = self._api.pro_bar(
                ts_code=ticker, start_date=start_yyyymmdd, end_date=end_yyyymmdd, adj=self._adj,
            )
            if df.empty:
                return []
            result = []
            for _, row in df.iterrows():
                iso_date = _yyyymmdd_to_iso(str(row["trade_date"]))
                close = row["close"]
                if pd.notna(close):
                    result.append((iso_date, float(close)))
            return result
        except Exception as e:
            logger.debug("get_prices(%s, %s, %s) failed: %s", ticker, start, end, e)
            return []

    def get_latest_price(self, ticker: str) -> Optional[float]:
        """Get most recent close price for ticker.

        Returns:
            Latest close price, or None if no data available.
        """
        try:
            df = self._api.pro_bar(ts_code=ticker, adj=self._adj)
            if df.empty:
                return None
            close = df.iloc[-1]["close"]
            return float(close) if pd.notna(close) else None
        except Exception as e:
            logger.debug("get_latest_price(%s) failed: %s", ticker, e)
            return None


# =============================================================================
# Tushare Calendar Provider
# =============================================================================


class TushareCalendarProvider:
    """Trading calendar queries backed by local Tushare Parquet data.

    Used by F5 timing policy for trading day calculations.
    """

    def __init__(self, data_dir: Path) -> None:
        self._api = LocalPro(data_dir)

    def is_trading_day(self, dt: date, exchange: str = "SSE") -> bool:
        """Check if a date is a trading day."""
        try:
            df = self._api.trade_cal(
                exchange=exchange,
                start_date=dt.strftime("%Y%m%d"),
                end_date=dt.strftime("%Y%m%d"),
                is_open="1",
            )
            return not df.empty
        except Exception:
            return False

    def next_trading_day(self, dt: date, exchange: str = "SSE") -> date:
        """Return the next trading day on or after dt."""
        try:
            df = self._api.trade_cal(
                exchange=exchange,
                start_date=dt.strftime("%Y%m%d"),
                is_open="1",
            )
            if df.empty:
                return dt
            first = df.iloc[0]["cal_date"]
            return datetime.strptime(str(first), "%Y%m%d").date()
        except Exception:
            return dt

    def prev_trading_day(self, dt: date, exchange: str = "SSE") -> date:
        """Return the last trading day on or before dt."""
        try:
            df = self._api.trade_cal(
                exchange=exchange,
                end_date=dt.strftime("%Y%m%d"),
                is_open="1",
            )
            if df.empty:
                return dt
            last = df.iloc[-1]["cal_date"]
            return datetime.strptime(str(last), "%Y%m%d").date()
        except Exception:
            return dt

    def trading_days_between(
        self, start: date, end: date, exchange: str = "SSE",
    ) -> list[date]:
        """Return sorted list of trading days in [start, end]."""
        try:
            df = self._api.trade_cal(
                exchange=exchange,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                is_open="1",
            )
            if df.empty:
                return []
            return [
                datetime.strptime(str(row["cal_date"]), "%Y%m%d").date()
                for _, row in df.iterrows()
            ]
        except Exception:
            return []
