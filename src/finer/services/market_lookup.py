"""Market lookup — 标注工作台行情对照查询（本地 tushare Parquet，零网络）.

封装 ``market_data.LocalPro``，给定 ticker + 锚定日期返回锚定日收盘与 ±N 交易日
窗口，供标注者验证价位量级（区分「涨幅比例」与「目标价」）。

覆盖范围：本地库只有 A 股日线（tushare daily_kline）。港股/美股返回
``unsupported_market``，本地数据未同步返回 ``no_local_data``，均不抛错——
降级态是产品状态，不是异常。
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from finer.entity_registry import resolve
from finer.paths import MARKET_PARQUET_DIR

_TS_CODE_RE = re.compile(r"^\d{6}\.(SH|SZ)$")
_HK_RE = re.compile(r"^\d{4,5}\.HK$")

_SYNC_HINT = "本地行情库未同步。设置 TUSHARE_TOKEN 后运行: python -m finer.cli market-data sync"

# (data_dir, ts_code, anchor_date) → (expires_at, result)
_CACHE: Dict[Tuple[str, str, str], Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 600
_WINDOW_TRADING_DAYS = 10
# 自然日窗口取交易日窗口的 2 倍冗余（覆盖周末/假期）
_WINDOW_CALENDAR_DAYS = _WINDOW_TRADING_DAYS * 2 + 5


def _parse_anchor_date(value: str) -> date:
    text = value.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text if fmt == "%Y-%m-%d" else value.strip()[:8], fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {value!r}（期望 YYYY-MM-DD）")


def _resolve_ts_code(ticker: str) -> Tuple[Optional[str], Optional[str]]:
    """ticker/alias → (ts_code, market)。ts_code 为 None 表示不可本地查询。"""
    raw = ticker.strip()
    upper = raw.upper()
    if _TS_CODE_RE.match(upper):
        return upper, "CN"
    if _HK_RE.match(upper):
        return None, "HK"
    entry = resolve(raw) or resolve(upper)
    if entry:
        resolved_ticker, market, _etype = entry
        if market == "CN" and _TS_CODE_RE.match(resolved_ticker.upper()):
            return resolved_ticker.upper(), "CN"
        return None, market or None
    # 纯字母（美股形态）但不在 registry
    if re.match(r"^[A-Z]{1,5}$", upper):
        return None, "US"
    return None, None


def lookup_market_window(
    ticker: str,
    anchor: str,
    *,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """查询 ticker 在 anchor 日期附近的本地行情窗口。

    Returns:
        coverage ∈ {"local", "unsupported_market", "unknown_ticker", "no_local_data"}；
        coverage="local" 时附 name/anchor_date/anchor_close/anchor_pct_chg/window。
    """
    anchor_date = _parse_anchor_date(anchor)
    ts_code, market = _resolve_ts_code(ticker)

    if ts_code is None:
        if market in ("HK", "US"):
            return {
                "ticker": ticker,
                "coverage": "unsupported_market",
                "market": market,
                "hint": f"本地 tushare 库仅覆盖 A 股日线，{market} 市场暂不支持",
            }
        return {
            "ticker": ticker,
            "coverage": "unknown_ticker",
            "market": market,
            "hint": "无法解析为 A 股代码（600519.SH 格式）或实体库别名",
        }

    resolved_dir = data_dir or MARKET_PARQUET_DIR
    cache_key = (str(resolved_dir), ts_code, anchor_date.isoformat())
    cached = _CACHE.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    try:
        from finer.market_data.local_api import LocalPro
    except ImportError:
        return {
            "ticker": ticker,
            "ts_code": ts_code,
            "coverage": "no_local_data",
            "hint": "duckdb 未安装。运行: pip install 'finer[market-data]'",
        }

    pro = LocalPro(resolved_dir)
    start = (anchor_date - timedelta(days=_WINDOW_CALENDAR_DAYS)).strftime("%Y%m%d")
    end = (anchor_date + timedelta(days=_WINDOW_CALENDAR_DAYS)).strftime("%Y%m%d")
    try:
        bars = pro.pro_bar(ts_code, start_date=start, end_date=end, adj="qfq")
    except (FileNotFoundError, ImportError):
        return {
            "ticker": ticker,
            "ts_code": ts_code,
            "coverage": "no_local_data",
            "hint": _SYNC_HINT,
        }
    if bars.empty:
        return {
            "ticker": ticker,
            "ts_code": ts_code,
            "coverage": "no_local_data",
            "hint": f"本地库无 {ts_code} 在 {anchor_date} 附近的日线（{_SYNC_HINT}）",
        }

    bars = bars.sort_values("trade_date").reset_index(drop=True)
    anchor_str = anchor_date.strftime("%Y%m%d")
    on_or_before = bars[bars["trade_date"] <= anchor_str]
    anchor_idx = int(on_or_before.index[-1]) if not on_or_before.empty else 0
    anchor_row = bars.iloc[anchor_idx]

    name: Optional[str] = None
    try:
        basic = pro.stock_basic(ts_code=ts_code, fields=["ts_code", "name"])
        if not basic.empty:
            name = str(basic.iloc[0]["name"])
    except Exception:
        # name 是装饰性信息（basic 表可能未同步/缺列），不因它失败整个查询
        name = None

    lo = max(0, anchor_idx - _WINDOW_TRADING_DAYS)
    hi = min(len(bars), anchor_idx + _WINDOW_TRADING_DAYS + 1)
    window = [
        {
            "trade_date": str(r["trade_date"]),
            "close": float(r["close"]),
            "pct_chg": float(r["pct_chg"]) if r["pct_chg"] == r["pct_chg"] else None,
        }
        for r in bars.iloc[lo:hi].to_dict("records")
    ]

    result = {
        "ticker": ticker,
        "ts_code": ts_code,
        "name": name,
        "coverage": "local",
        "anchor_date": str(anchor_row["trade_date"]),
        "anchor_close": float(anchor_row["close"]),
        "anchor_pct_chg": float(anchor_row["pct_chg"]) if anchor_row["pct_chg"] == anchor_row["pct_chg"] else None,
        "window": window,
    }
    _CACHE[cache_key] = (time.monotonic() + _CACHE_TTL_SECONDS, result)
    return result
