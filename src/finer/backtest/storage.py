"""Backtest result persistence for F8.

Storage layout:
    data/review/{kol_id}/F8_backtest/
    ├── backtest_result.json        — BacktestResult without snapshots
    ├── equity_curve.csv            — portfolio snapshot series
    └── trades.json                 — compact trade audit rows

    data/F8_metrics/
    ├── {backtest_id}.json          — legacy CLI BacktestResult
    └── index.json                  — legacy chronological index

Each result JSON includes:
- run metadata (id, timestamp, config)
- performance metrics
- trade list
- portfolio snapshots (optional, can be large)
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from finer.paths import DATA_ROOT

logger = logging.getLogger(__name__)

BACKTESTS_DIR = DATA_ROOT / "F8_metrics"
DATA_REVIEW_DIR = DATA_ROOT / "review"
REVIEW_F8_DIRNAME = "F8_backtest"


def _ensure_dir() -> None:
    BACKTESTS_DIR.mkdir(parents=True, exist_ok=True)


def _index_path() -> Path:
    return BACKTESTS_DIR / "index.json"


def _load_index() -> List[Dict[str, Any]]:
    path = _index_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_index(index: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    _index_path().write_text(
        json.dumps(index, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def save_backtest_result(
    result_dict: Dict[str, Any],
    *,
    include_snapshots: bool = False,
) -> Path:
    """Save a BacktestResult dict to JSON and update the index.

    Args:
        result_dict: Serialized BacktestResult (model_dump(mode='json')).
        include_snapshots: Whether to include portfolio_snapshots in the file.
            Snapshots can be large; omit for index-only storage.

    Returns:
        Path to the saved JSON file.
    """
    _ensure_dir()

    backtest_id = result_dict.get("backtest_id", "unknown")
    file_path = BACKTESTS_DIR / f"{backtest_id}.json"

    # Optionally strip snapshots to save space
    save_dict = dict(result_dict)
    if not include_snapshots:
        save_dict.pop("portfolio_snapshots", None)

    file_path.write_text(
        json.dumps(save_dict, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Backtest result saved: %s", file_path)

    # Update index
    index_entry = {
        "backtest_id": backtest_id,
        "start_date": result_dict.get("start_date"),
        "end_date": result_dict.get("end_date"),
        "run_timestamp": result_dict.get("run_timestamp"),
        "total_return": result_dict.get("total_return"),
        "sharpe_ratio": result_dict.get("sharpe_ratio"),
        "max_drawdown": result_dict.get("max_drawdown"),
        "total_trades": result_dict.get("total_trades"),
        "file": str(file_path.name),
    }

    index = _load_index()
    # Deduplicate by backtest_id
    index = [e for e in index if e.get("backtest_id") != backtest_id]
    index.append(index_entry)
    _save_index(index)

    return file_path


def load_backtest_result(backtest_id: str) -> Optional[Dict[str, Any]]:
    """Load a saved BacktestResult by ID."""
    file_path = BACKTESTS_DIR / f"{backtest_id}.json"
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load backtest %s: %s", backtest_id, e)
        return None


def list_backtest_results() -> List[Dict[str, Any]]:
    """List all saved backtest results (from index)."""
    return _load_index()


def save_f8_backtest_artifacts(
    result: Any,
    kol_id: Optional[str] = None,
    *,
    metrics_dir: Optional[Path] = None,
    review_dir: Optional[Path] = None,
) -> Path:
    """Save a backtest result using the shared F8 artifact layout.

    KOL-attributed runs are stored under data/review/{kol_id}/F8_backtest so
    scripted E2E output and API output stay on the same read path. Anonymous
    runs keep the legacy data/F8_metrics JSON layout.
    """
    result_dict = _coerce_result_dict(result)
    if kol_id:
        return _save_review_backtest_artifacts(
            result_dict,
            kol_id,
            review_root=review_dir or DATA_REVIEW_DIR,
        )
    return _save_metrics_backtest_result(
        result_dict,
        metrics_root=metrics_dir or BACKTESTS_DIR,
    )


def load_f8_backtest_result(
    backtest_id: str,
    *,
    metrics_dir: Optional[Path] = None,
    review_dir: Optional[Path] = None,
):
    """Load a BacktestResult from review F8 artifacts or legacy F8_metrics."""
    from finer.backtest.engine import BacktestResult

    for path in _iter_f8_result_files(
        metrics_root=metrics_dir or BACKTESTS_DIR,
        review_root=review_dir or DATA_REVIEW_DIR,
    ):
        data = _read_json(path)
        if not data or data.get("backtest_id") != backtest_id:
            continue
        data = _hydrate_review_result(data, path)
        try:
            return BacktestResult.model_validate_json(
                json.dumps(data, ensure_ascii=False, default=str)
            )
        except Exception as exc:
            logger.error("Failed to validate backtest %s: %s", path, exc)
    return None


def list_f8_backtest_summaries(
    *,
    kol_id: Optional[str] = None,
    limit: int = 20,
    sort_by: str = "created_at",
    metrics_dir: Optional[Path] = None,
    review_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """List result summaries from review F8 artifacts and legacy F8_metrics."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for path in _iter_f8_result_files(
        metrics_root=metrics_dir or BACKTESTS_DIR,
        review_root=review_dir or DATA_REVIEW_DIR,
    ):
        data = _read_json(path)
        if not data:
            continue

        result_id = data.get("backtest_id")
        if not result_id:
            continue

        inferred_kol_id = _infer_kol_id(data, path)
        if kol_id and inferred_kol_id != kol_id:
            continue

        if result_id in by_id:
            continue

        by_id[result_id] = {
            "backtest_id": result_id,
            "kol_id": inferred_kol_id,
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "total_return": data.get("total_return", 0.0),
            "sharpe_ratio": data.get("sharpe_ratio", 0.0),
            "max_drawdown": data.get("max_drawdown", 0.0),
            "win_rate": data.get("win_rate", 0.0),
            "total_trades": data.get("total_trades", 0),
            "created_at": data.get("run_timestamp", ""),
            "filepath": str(path),
        }

    results = list(by_id.values())
    if sort_by in {"total_return", "sharpe_ratio", "win_rate"}:
        results.sort(key=lambda item: item.get(sort_by, 0), reverse=True)
    elif sort_by == "created_at":
        results.sort(key=lambda item: item.get(sort_by, ""), reverse=True)
    return results[:limit]


def delete_f8_backtest_result(
    backtest_id: str,
    *,
    metrics_dir: Optional[Path] = None,
    review_dir: Optional[Path] = None,
) -> List[Path]:
    """Delete a saved F8 result and return the files removed."""
    deleted: List[Path] = []
    for path in _iter_f8_result_files(
        metrics_root=metrics_dir or BACKTESTS_DIR,
        review_root=review_dir or DATA_REVIEW_DIR,
    ):
        data = _read_json(path)
        if not data or data.get("backtest_id") != backtest_id:
            continue

        files = [path]
        if _is_review_result_path(path):
            files.extend(
                sibling
                for sibling in (
                    path.parent / "equity_curve.csv",
                    path.parent / "trades.json",
                )
                if sibling.exists()
            )

        for file_path in files:
            try:
                file_path.unlink()
                deleted.append(file_path)
                logger.info("Deleted F8 backtest artifact: %s", file_path)
            except OSError as exc:
                logger.error("Failed to delete %s: %s", file_path, exc)
    return deleted


def count_f8_backtest_results(
    *,
    metrics_dir: Optional[Path] = None,
    review_dir: Optional[Path] = None,
) -> int:
    """Count discoverable F8 result files."""
    return len(
        list(
            _iter_f8_result_files(
                metrics_root=metrics_dir or BACKTESTS_DIR,
                review_root=review_dir or DATA_REVIEW_DIR,
            )
        )
    )


def _coerce_result_dict(result: Any) -> Dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return dict(result)


def _save_metrics_backtest_result(
    result_dict: Dict[str, Any],
    *,
    metrics_root: Path,
) -> Path:
    metrics_root.mkdir(parents=True, exist_ok=True)
    result_id = result_dict.get("backtest_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = metrics_root / f"backtest_{result_id}_{timestamp}.json"
    filepath.write_text(
        json.dumps(result_dict, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Saved F8 backtest result: %s", filepath)
    return filepath


def _save_review_backtest_artifacts(
    result_dict: Dict[str, Any],
    kol_id: str,
    *,
    review_root: Path,
) -> Path:
    out_dir = review_root / kol_id / REVIEW_F8_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)

    result_payload = dict(result_dict)
    result_payload.pop("portfolio_snapshots", None)
    result_path = out_dir / "backtest_result.json"
    result_path.write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    _write_equity_curve_csv(
        result_dict.get("portfolio_snapshots") or [],
        out_dir / "equity_curve.csv",
    )
    _write_trades_snapshot(result_dict.get("trades") or [], out_dir / "trades.json")
    logger.info("Saved F8 review backtest artifacts: %s", out_dir)
    return result_path


def _write_equity_curve_csv(snapshots: List[Dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "date",
        "total_value",
        "cash",
        "positions_value",
        "cumulative_return",
        "drawdown",
        "num_positions",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for snapshot in snapshots:
            writer.writerow(
                {
                    "date": snapshot.get("date"),
                    "total_value": snapshot.get("total_value", 0.0),
                    "cash": snapshot.get("cash", 0.0),
                    "positions_value": snapshot.get("positions_value", 0.0),
                    "cumulative_return": snapshot.get("cumulative_return", 0.0),
                    "drawdown": snapshot.get("current_drawdown", 0.0),
                    "num_positions": snapshot.get("num_positions", 0),
                }
            )


def _write_trades_snapshot(trades: List[Dict[str, Any]], path: Path) -> None:
    compact_trades = []
    for trade in trades:
        compact_trades.append(
            {
                "trade_id": trade.get("trade_id"),
                "ticker": trade.get("ticker"),
                "side": _enum_value(trade.get("side")),
                "entry_date": trade.get("entry_date"),
                "entry_price": round(float(trade.get("entry_price", 0.0)), 4),
                "exit_date": trade.get("exit_date"),
                "exit_price": round(float(trade.get("exit_price", 0.0)), 4),
                "net_pnl": round(float(trade.get("net_pnl", 0.0)), 2),
                "return_pct": round(float(trade.get("return_pct", 0.0)) * 100, 2),
                "exit_reason": _enum_value(trade.get("exit_reason")),
                "holding_days": trade.get("holding_days"),
                "trade_action_id": trade.get("trade_action_id"),
                "kol_id": trade.get("kol_id"),
                "intent_id": trade.get("intent_id"),
                "policy_id": trade.get("policy_id"),
                "evidence_span_ids": trade.get("evidence_span_ids") or [],
            }
        )
    path.write_text(
        json.dumps(compact_trades, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _iter_f8_result_files(metrics_root: Path, review_root: Path):
    review_files = sorted(
        review_root.glob(f"*/{REVIEW_F8_DIRNAME}/backtest_result.json")
    )
    metric_files = sorted(
        path for path in metrics_root.glob("*.json") if path.name != "index.json"
    )
    yield from review_files
    yield from metric_files


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read F8 backtest result %s: %s", path, exc)
        return None


def _hydrate_review_result(data: Dict[str, Any], path: Path) -> Dict[str, Any]:
    if not _is_review_result_path(path) or data.get("portfolio_snapshots"):
        return data

    equity_path = path.parent / "equity_curve.csv"
    if equity_path.exists():
        hydrated = dict(data)
        hydrated["portfolio_snapshots"] = _load_equity_curve_snapshots(
            equity_path,
            initial_capital=float(data.get("initial_capital", 0.0) or 0.0),
        )
        return hydrated
    return data


def _load_equity_curve_snapshots(
    path: Path, *, initial_capital: float
) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    previous_total: Optional[float] = None
    peak_value = initial_capital

    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                total_value = _float_cell(row.get("total_value"))
                if peak_value == 0.0:
                    peak_value = total_value
                peak_value = max(peak_value, total_value)
                daily_pnl = (
                    0.0 if previous_total is None else total_value - previous_total
                )
                previous_total = total_value

                snapshots.append(
                    {
                        "date": row.get("date"),
                        "cash": _float_cell(row.get("cash")),
                        "positions_value": _float_cell(row.get("positions_value")),
                        "total_value": total_value,
                        "daily_pnl": daily_pnl,
                        "cumulative_pnl": total_value - initial_capital,
                        "cumulative_return": _float_cell(row.get("cumulative_return")),
                        "peak_value": peak_value,
                        "current_drawdown": _float_cell(
                            row.get("current_drawdown") or row.get("drawdown")
                        ),
                        "num_positions": _int_cell(row.get("num_positions")),
                        "long_exposure": _float_cell(row.get("long_exposure")),
                        "short_exposure": _float_cell(row.get("short_exposure")),
                    }
                )
    except OSError as exc:
        logger.warning("Failed to read F8 equity curve %s: %s", path, exc)
    return snapshots


def _float_cell(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _int_cell(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def _is_review_result_path(path: Path) -> bool:
    return path.name == "backtest_result.json" and path.parent.name == REVIEW_F8_DIRNAME


def _infer_kol_id(data: Dict[str, Any], path: Path) -> Optional[str]:
    if _is_review_result_path(path):
        return path.parent.parent.name

    explicit = data.get("kol_id")
    if isinstance(explicit, str) and explicit:
        return explicit

    kol_metrics = data.get("kol_metrics")
    if isinstance(kol_metrics, dict) and len(kol_metrics) == 1:
        return next(iter(kol_metrics.keys()))

    trade_kol_ids = {
        trade.get("kol_id")
        for trade in data.get("trades", [])
        if isinstance(trade, dict) and trade.get("kol_id")
    }
    if len(trade_kol_ids) == 1:
        return next(iter(trade_kol_ids))

    return None
