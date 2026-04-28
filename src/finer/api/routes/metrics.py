"""Performance metrics API — expose performance monitoring data.

Provides endpoints for:
- Current performance statistics
- Budget definitions
- Active alerts
- Historical violations
"""

from fastapi import APIRouter, Query
from typing import Optional

from finer.services.performance import (
    monitor,
    PERFORMANCE_BUDGETS,
    PerformanceBudget,
)

router = APIRouter()


def _budget_to_dict(budget: PerformanceBudget) -> dict:
    """Convert PerformanceBudget to dict for JSON serialization."""
    return {
        "operation": budget.operation,
        "target_ms": budget.target_ms,
        "warning_ms": budget.warning_ms,
        "critical_ms": budget.critical_ms,
    }


@router.get("")
async def get_performance_metrics():
    """Get comprehensive performance metrics.

    Returns:
        Budgets, current stats, and active alerts
    """
    # Get all stats
    all_stats = monitor.get_all_stats()

    # Get active alerts
    alerts = monitor.get_active_alerts()

    # Convert budgets to dict
    budgets = {
        key: _budget_to_dict(budget)
        for key, budget in PERFORMANCE_BUDGETS.items()
    }

    return {
        "ok": True,
        "data": {
            "budgets": budgets,
            "current_stats": all_stats,
            "alerts": alerts,
            "monitoring_enabled": monitor._enabled,
        },
    }


@router.get("/stats/{operation}")
async def get_operation_stats(operation: str):
    """Get statistics for a specific operation.

    Args:
        operation: Operation identifier

    Returns:
        Statistics including p50, p95, p99
    """
    stats = monitor.get_stats(operation)
    budget = PERFORMANCE_BUDGETS.get(operation)

    result = {
        "ok": True,
        "data": {
            "stats": stats,
        },
    }

    if budget:
        result["data"]["budget"] = _budget_to_dict(budget)
        result["data"]["within_target"] = stats["p95_ms"] < budget.target_ms if stats["count"] > 0 else True

    return result


@router.get("/violations")
async def get_violations(
    operation: Optional[str] = Query(None, description="Filter by operation"),
    limit: int = Query(20, description="Maximum violations per operation"),
):
    """Get budget violations.

    Args:
        operation: Optional filter by specific operation
        limit: Maximum number of violations to return per operation

    Returns:
        Dictionary of violations by operation
    """
    violations = monitor.get_violations(operation)

    # Apply limit
    limited_violations = {}
    for op, vlist in violations.items():
        limited_violations[op] = vlist[-limit:] if len(vlist) > limit else vlist

    return {
        "ok": True,
        "data": {
            "violations": limited_violations,
            "total_operations": len(limited_violations),
            "total_violations": sum(len(v) for v in limited_violations.values()),
        },
    }


@router.get("/budgets")
async def get_budgets():
    """Get all performance budget definitions.

    Returns:
        Dictionary of performance budgets
    """
    return {
        "ok": True,
        "data": {
            "budgets": {
                key: _budget_to_dict(budget)
                for key, budget in PERFORMANCE_BUDGETS.items()
            },
        },
    }


@router.post("/reset")
async def reset_metrics(
    operation: Optional[str] = Query(None, description="Reset specific operation or all"),
):
    """Reset performance metrics.

    Args:
        operation: Optional specific operation to reset, or all if not provided

    Returns:
        Success status
    """
    monitor.clear(operation)

    return {
        "ok": True,
        "data": {
            "reset": operation if operation else "all",
            "message": f"Metrics reset for {operation if operation else 'all operations'}",
        },
    }
