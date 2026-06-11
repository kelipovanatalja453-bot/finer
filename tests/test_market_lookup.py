"""market_lookup tests — 标注行情对照查询（本地 Parquet 路径 + 降级态）."""

from pathlib import Path

import pytest

from finer.services.market_lookup import lookup_market_window

duckdb = pytest.importorskip("duckdb")


DAILY_ROWS = [
    # ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
    ("300750.SZ", "20260310", 180.0, 183.0, 178.0, 182.0, 179.0, 3.0, 1.68, 1e6, 1.8e8),
    ("300750.SZ", "20260311", 182.0, 185.0, 181.0, 184.5, 182.0, 2.5, 1.37, 1e6, 1.8e8),
    ("300750.SZ", "20260312", 184.5, 186.0, 182.0, 183.0, 184.5, -1.5, -0.81, 1e6, 1.8e8),
    ("300750.SZ", "20260313", 183.0, 188.0, 183.0, 187.2, 183.0, 4.2, 2.30, 1e6, 1.8e8),
    ("300750.SZ", "20260316", 187.2, 190.0, 186.0, 189.0, 187.2, 1.8, 0.96, 1e6, 1.8e8),
]


@pytest.fixture
def parquet_dir(tmp_path: Path) -> Path:
    """构造最小可用的本地 tushare Parquet 布局（daily_kline + adj_factor + basic）。"""
    con = duckdb.connect()

    daily_dir = tmp_path / "daily_kline" / "date=20260301"
    daily_dir.mkdir(parents=True)
    values = ", ".join(
        f"('{r[0]}', '{r[1]}', {r[2]}, {r[3]}, {r[4]}, {r[5]}, {r[6]}, {r[7]}, {r[8]}, {r[9]}, {r[10]})"
        for r in DAILY_ROWS
    )
    con.execute(
        f"CREATE TABLE d AS SELECT * FROM (VALUES {values}) "
        "t(ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)"
    )
    con.execute(f"COPY d TO '{daily_dir / 'data.parquet'}' (FORMAT PARQUET)")

    adj_dir = tmp_path / "adj_factor" / "date=20260301"
    adj_dir.mkdir(parents=True)
    adj_values = ", ".join(f"('{r[0]}', '{r[1]}', 1.0)" for r in DAILY_ROWS)
    con.execute(
        f"CREATE TABLE a AS SELECT * FROM (VALUES {adj_values}) t(ts_code, trade_date, adj_factor)"
    )
    con.execute(f"COPY a TO '{adj_dir / 'data.parquet'}' (FORMAT PARQUET)")

    basic_dir = tmp_path / "basic"
    basic_dir.mkdir(parents=True)
    con.execute(
        "CREATE TABLE b AS SELECT '300750.SZ' AS ts_code, '宁德时代' AS name, 'L' AS list_status"
    )
    con.execute(f"COPY b TO '{basic_dir / 'data.parquet'}' (FORMAT PARQUET)")
    return tmp_path


def test_local_window_with_anchor(parquet_dir: Path):
    result = lookup_market_window("300750.SZ", "2026-03-13", data_dir=parquet_dir)
    assert result["coverage"] == "local"
    assert result["ts_code"] == "300750.SZ"
    assert result["name"] == "宁德时代"
    assert result["anchor_date"] == "20260313"
    assert result["anchor_close"] == pytest.approx(187.2)
    assert result["anchor_pct_chg"] == pytest.approx(2.30)
    assert [bar["trade_date"] for bar in result["window"]] == [r[1] for r in DAILY_ROWS]


def test_anchor_falls_back_to_previous_trade_day(parquet_dir: Path):
    # 2026-03-14/15 周末：锚定回退到 13 日
    result = lookup_market_window("300750.SZ", "2026-03-15", data_dir=parquet_dir)
    assert result["coverage"] == "local"
    assert result["anchor_date"] == "20260313"


def test_alias_resolution_via_registry(parquet_dir: Path):
    # entity_registry 中「宁德时代」→ 300750.SZ
    result = lookup_market_window("宁德时代", "2026-03-13", data_dir=parquet_dir)
    assert result["coverage"] == "local"
    assert result["ts_code"] == "300750.SZ"


def test_unsupported_and_unknown_markets(parquet_dir: Path):
    assert lookup_market_window("0700.HK", "2026-03-13", data_dir=parquet_dir)["coverage"] == "unsupported_market"
    assert lookup_market_window("TME", "2026-03-13", data_dir=parquet_dir)["coverage"] == "unsupported_market"
    assert lookup_market_window("不存在的东西", "2026-03-13", data_dir=parquet_dir)["coverage"] == "unknown_ticker"


def test_no_local_data_paths(tmp_path: Path, parquet_dir: Path):
    # 完全没同步过：daily_kline 目录缺失
    empty = tmp_path / "empty_parquet"
    empty.mkdir()
    result = lookup_market_window("300750.SZ", "2026-03-13", data_dir=empty)
    assert result["coverage"] == "no_local_data"
    assert "market-data sync" in result["hint"]

    # 库存在但该 ticker 无数据
    result2 = lookup_market_window("600519.SH", "2026-03-13", data_dir=parquet_dir)
    assert result2["coverage"] == "no_local_data"


def test_bad_date_raises():
    with pytest.raises(ValueError, match="日期"):
        lookup_market_window("300750.SZ", "13/03/2026")
