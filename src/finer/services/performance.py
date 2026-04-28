"""Performance monitoring and budget enforcement for Finer OS.

This module provides:
- Performance budget definitions
- Operation timing and tracking
- Statistics collection (p50, p95, p99)
- Budget violation alerts

Usage:
    from finer.services.performance import track_performance, monitor

    @track_performance("trade_action_extract")
    async def extract_actions(text: str) -> TradeActionBatch:
        ...

    # Check stats
    stats = monitor.get_stats("trade_action_extract")
    print(f"p95: {stats['p95']}ms")
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, ParamSpec
from collections import deque
import threading

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


# =============================================================================
# Configuration
# =============================================================================

# Environment variable to enable/disable monitoring
FINER_PERF_MONITORING_ENABLED = os.environ.get("FINER_PERF_MONITORING", "true").lower() in ("true", "1", "yes")

# Maximum samples to keep per operation
MAX_SAMPLES = 1000


# =============================================================================
# Performance Budget Definitions
# =============================================================================

@dataclass
class PerformanceBudget:
    """Performance budget for a single operation type.

    Attributes:
        operation: Human-readable operation name
        target_ms: Target latency in milliseconds
        warning_ms: Warning threshold (performance degradation)
        critical_ms: Critical threshold (SLA violation)
    """
    operation: str
    target_ms: int
    warning_ms: int
    critical_ms: int

    def check(self, duration_ms: float) -> Optional[str]:
        """Check if duration violates budget.

        Returns:
            None if OK, "warning" or "critical" if threshold exceeded
        """
        if duration_ms >= self.critical_ms:
            return "critical"
        if duration_ms >= self.warning_ms:
            return "warning"
        return None


# Performance budgets based on architecture review
PERFORMANCE_BUDGETS: Dict[str, PerformanceBudget] = {
    "trade_action_extract": PerformanceBudget(
        operation="TradeAction 抽取",
        target_ms=10000,
        warning_ms=15000,
        critical_ms=30000,
    ),
    "timeline_query": PerformanceBudget(
        operation="时间线查询",
        target_ms=500,
        warning_ms=1000,
        critical_ms=2000,
    ),
    "backtest_full": PerformanceBudget(
        operation="全量回测",
        target_ms=30000,
        warning_ms=60000,
        critical_ms=120000,
    ),
    "dashboard_load": PerformanceBudget(
        operation="Dashboard 首屏",
        target_ms=2000,
        warning_ms=3000,
        critical_ms=5000,
    ),
    "llm_call": PerformanceBudget(
        operation="LLM 调用",
        target_ms=5000,
        warning_ms=8000,
        critical_ms=15000,
    ),
    "file_scan": PerformanceBudget(
        operation="文件扫描",
        target_ms=200,
        warning_ms=500,
        critical_ms=1000,
    ),
    "summary_generate": PerformanceBudget(
        operation="摘要生成",
        target_ms=3000,
        warning_ms=5000,
        critical_ms=10000,
    ),
    "enrichment_merge": PerformanceBudget(
        operation="富化数据合并",
        target_ms=1000,
        warning_ms=2000,
        critical_ms=5000,
    ),
}


# =============================================================================
# Performance Monitor
# =============================================================================

class PerformanceMonitor:
    """Thread-safe performance monitor with statistics collection.

    Features:
    - Records operation durations
    - Maintains rolling window of samples
    - Calculates percentiles (p50, p95, p99)
    - Tracks budget violations
    - Low overhead design
    """

    def __init__(self, max_samples: int = MAX_SAMPLES):
        """Initialize monitor.

        Args:
            max_samples: Maximum samples to keep per operation
        """
        self.max_samples = max_samples
        self._metrics: Dict[str, deque] = {}
        self._violations: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()  # Use RLock for reentrant locking
        self._enabled = FINER_PERF_MONITORING_ENABLED

    def record(self, operation: str, duration_ms: float) -> Optional[str]:
        """Record an operation duration.

        Args:
            operation: Operation identifier (must match PERFORMANCE_BUDGETS key)
            duration_ms: Duration in milliseconds

        Returns:
            Violation level if budget exceeded, None otherwise
        """
        if not self._enabled:
            return None

        with self._lock:
            # Initialize metrics for this operation
            if operation not in self._metrics:
                self._metrics[operation] = deque(maxlen=self.max_samples)
                self._violations[operation] = []

            # Record duration
            self._metrics[operation].append(duration_ms)

            # Check budget
            violation = None
            if operation in PERFORMANCE_BUDGETS:
                budget = PERFORMANCE_BUDGETS[operation]
                violation = budget.check(duration_ms)

                if violation:
                    self._violations[operation].append({
                        "duration_ms": duration_ms,
                        "level": violation,
                        "threshold_ms": budget.critical_ms if violation == "critical" else budget.warning_ms,
                    })
                    # Keep only last 100 violations
                    if len(self._violations[operation]) > 100:
                        self._violations[operation] = self._violations[operation][-100:]

            return violation

    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for an operation.

        Args:
            operation: Operation identifier

        Returns:
            Dictionary with count, min, max, mean, p50, p95, p99
        """
        with self._lock:
            if operation not in self._metrics:
                return {
                    "operation": operation,
                    "count": 0,
                    "min_ms": 0,
                    "max_ms": 0,
                    "mean_ms": 0,
                    "p50_ms": 0,
                    "p95_ms": 0,
                    "p99_ms": 0,
                }

            samples = list(self._metrics[operation])
            if not samples:
                return {
                    "operation": operation,
                    "count": 0,
                    "min_ms": 0,
                    "max_ms": 0,
                    "mean_ms": 0,
                    "p50_ms": 0,
                    "p95_ms": 0,
                    "p99_ms": 0,
                }

            sorted_samples = sorted(samples)
            count = len(sorted_samples)

            return {
                "operation": operation,
                "count": count,
                "min_ms": round(sorted_samples[0], 2),
                "max_ms": round(sorted_samples[-1], 2),
                "mean_ms": round(sum(sorted_samples) / count, 2),
                "p50_ms": round(self._percentile(sorted_samples, 50), 2),
                "p95_ms": round(self._percentile(sorted_samples, 95), 2),
                "p99_ms": round(self._percentile(sorted_samples, 99), 2),
            }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all operations.

        Returns:
            Dictionary mapping operation names to their stats
        """
        with self._lock:
            ops = list(self._metrics.keys())
        return {op: self.get_stats(op) for op in ops}

    def get_violations(self, operation: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get budget violations.

        Args:
            operation: Optional specific operation, or all if None

        Returns:
            Dictionary of violations by operation
        """
        with self._lock:
            if operation:
                return {operation: self._violations.get(operation, [])}
            return dict(self._violations)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get current active alerts (recent violations).

        Returns:
            List of active alerts
        """
        alerts = []
        with self._lock:
            for op, violations in self._violations.items():
                # Get recent critical violations
                recent_critical = [
                    v for v in violations[-10:]
                    if v["level"] == "critical"
                ]
                if recent_critical:
                    alerts.append({
                        "operation": op,
                        "level": "critical",
                        "recent_count": len(recent_critical),
                        "last_duration_ms": recent_critical[-1]["duration_ms"],
                    })

                # Check if p95 exceeds warning
                stats = self.get_stats(op)
                if stats["count"] > 0 and op in PERFORMANCE_BUDGETS:
                    budget = PERFORMANCE_BUDGETS[op]
                    if stats["p95_ms"] >= budget.warning_ms:
                        alerts.append({
                            "operation": op,
                            "level": "warning" if stats["p95_ms"] < budget.critical_ms else "critical",
                            "p95_ms": stats["p95_ms"],
                            "target_ms": budget.target_ms,
                        })

        return alerts

    def clear(self, operation: Optional[str] = None) -> None:
        """Clear metrics for an operation or all operations.

        Args:
            operation: Optional specific operation, or all if None
        """
        with self._lock:
            if operation:
                self._metrics.pop(operation, None)
                self._violations.pop(operation, None)
            else:
                self._metrics.clear()
                self._violations.clear()

    def _percentile(self, sorted_samples: List[float], percentile: int) -> float:
        """Calculate percentile from sorted samples.

        Args:
            sorted_samples: Sorted list of samples
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not sorted_samples:
            return 0.0

        count = len(sorted_samples)
        index = (percentile / 100) * (count - 1)
        lower = int(index)
        upper = lower + 1

        if upper >= count:
            return sorted_samples[-1]

        weight = index - lower
        return sorted_samples[lower] * (1 - weight) + sorted_samples[upper] * weight


# Global monitor instance
monitor = PerformanceMonitor()


# =============================================================================
# Decorators
# =============================================================================

def track_performance(operation: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to track function performance.

    Usage:
        @track_performance("trade_action_extract")
        async def extract_actions(text: str) -> TradeActionBatch:
            ...

    Args:
        operation: Operation identifier (must match PERFORMANCE_BUDGETS key)

    Returns:
        Decorated function
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not monitor._enabled:
                return func(*args, **kwargs)

            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                violation = monitor.record(operation, duration_ms)

                if violation:
                    budget = PERFORMANCE_BUDGETS.get(operation)
                    if budget:
                        logger.warning(
                            f"Performance budget violated: {operation} "
                            f"took {duration_ms:.0f}ms ({violation} threshold: "
                            f"{budget.warning_ms if violation == 'warning' else budget.critical_ms}ms)"
                        )

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not monitor._enabled:
                return await func(*args, **kwargs)

            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                violation = monitor.record(operation, duration_ms)

                if violation:
                    budget = PERFORMANCE_BUDGETS.get(operation)
                    if budget:
                        logger.warning(
                            f"Performance budget violated: {operation} "
                            f"took {duration_ms:.0f}ms ({violation} threshold: "
                            f"{budget.warning_ms if violation == 'warning' else budget.critical_ms}ms)"
                        )

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


class PerformanceTracker:
    """Context manager for tracking performance of code blocks.

    Usage:
        with PerformanceTracker("file_scan") as tracker:
            # ... do work ...
            pass
        # tracker.duration_ms is automatically recorded
    """

    def __init__(self, operation: str):
        """Initialize tracker.

        Args:
            operation: Operation identifier
        """
        self.operation = operation
        self.start_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self._violation: Optional[str] = None

    def __enter__(self) -> "PerformanceTracker":
        if monitor._enabled:
            self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time is not None:
            self.duration_ms = (time.perf_counter() - self.start_time) * 1000
            self._violation = monitor.record(self.operation, self.duration_ms)

            if self._violation:
                budget = PERFORMANCE_BUDGETS.get(self.operation)
                if budget:
                    logger.warning(
                        f"Performance budget violated: {self.operation} "
                        f"took {self.duration_ms:.0f}ms ({self._violation} threshold: "
                        f"{budget.warning_ms if self._violation == 'warning' else budget.critical_ms}ms)"
                    )

    @property
    def violation(self) -> Optional[str]:
        """Get violation level if budget was exceeded."""
        return self._violation


# =============================================================================
# Utility Functions
# =============================================================================

def get_budget(operation: str) -> Optional[PerformanceBudget]:
    """Get performance budget for an operation.

    Args:
        operation: Operation identifier

    Returns:
        PerformanceBudget if defined, None otherwise
    """
    return PERFORMANCE_BUDGETS.get(operation)


def is_within_budget(operation: str, duration_ms: float) -> bool:
    """Check if a duration is within budget.

    Args:
        operation: Operation identifier
        duration_ms: Duration in milliseconds

    Returns:
        True if within budget, False otherwise
    """
    budget = PERFORMANCE_BUDGETS.get(operation)
    if not budget:
        return True
    return duration_ms < budget.target_ms


def reset_monitor() -> None:
    """Reset the global monitor (useful for testing)."""
    monitor.clear()


# =============================================================================
# Structured Logging Integration
# =============================================================================

def log_performance_event(
    operation: str,
    duration_ms: float,
    status: str = "ok",
    **extra: Any,
) -> None:
    """Log a performance event with structured data.

    Args:
        operation: Operation name
        duration_ms: Duration in milliseconds
        status: Status (ok, warning, critical)
        **extra: Additional context
    """
    budget = PERFORMANCE_BUDGETS.get(operation)

    log_data = {
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "status": status,
        **extra,
    }

    if budget:
        log_data["target_ms"] = budget.target_ms
        log_data["within_budget"] = duration_ms < budget.target_ms

    # Use structlog if available, otherwise standard logging
    try:
        import structlog
        struct_logger = structlog.get_logger()
        struct_logger.info("operation_completed", **log_data)
    except ImportError:
        logger.info(f"Performance: {log_data}")
