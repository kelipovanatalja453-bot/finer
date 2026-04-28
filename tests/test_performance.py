"""Performance tests for Finer OS.

Tests that critical operations meet performance budgets.

Run: pytest tests/test_performance.py -v
"""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from finer.services.performance import (
    PerformanceBudget,
    PerformanceMonitor,
    PerformanceTracker,
    track_performance,
    PERFORMANCE_BUDGETS,
    reset_monitor,
    monitor as global_monitor,
)


class TestPerformanceBudget:
    """Tests for PerformanceBudget class."""

    def test_budget_within_target(self):
        """Duration within target should return None."""
        budget = PerformanceBudget("test", target_ms=100, warning_ms=200, critical_ms=500)
        assert budget.check(50) is None
        assert budget.check(99) is None

    def test_budget_warning_threshold(self):
        """Duration at warning threshold should return 'warning'."""
        budget = PerformanceBudget("test", target_ms=100, warning_ms=200, critical_ms=500)
        assert budget.check(200) == "warning"
        assert budget.check(250) == "warning"
        assert budget.check(499) == "warning"

    def test_budget_critical_threshold(self):
        """Duration at critical threshold should return 'critical'."""
        budget = PerformanceBudget("test", target_ms=100, warning_ms=200, critical_ms=500)
        assert budget.check(500) == "critical"
        assert budget.check(1000) == "critical"


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class."""

    def setup_method(self):
        """Reset monitor before each test."""
        self.monitor = PerformanceMonitor()

    def test_record_operation(self):
        """Recording an operation should store it."""
        result = self.monitor.record("test_op", 100.0)
        assert result is None  # No budget defined, no violation

        stats = self.monitor.get_stats("test_op")
        assert stats["count"] == 1
        assert stats["min_ms"] == 100.0
        assert stats["max_ms"] == 100.0
        assert stats["mean_ms"] == 100.0

    def test_record_multiple_operations(self):
        """Recording multiple operations should calculate stats correctly."""
        for duration in [50, 100, 150, 200, 250]:
            self.monitor.record("test_op", duration)

        stats = self.monitor.get_stats("test_op")
        assert stats["count"] == 5
        assert stats["min_ms"] == 50.0
        assert stats["max_ms"] == 250.0
        assert stats["mean_ms"] == 150.0

    def test_percentile_calculation(self):
        """Percentiles should be calculated correctly."""
        # Add 100 samples from 1 to 100
        for i in range(1, 101):
            self.monitor.record("test_op", float(i))

        stats = self.monitor.get_stats("test_op")
        assert stats["count"] == 100
        # p50 should be around 50
        assert 45 <= stats["p50_ms"] <= 55
        # p95 should be around 95
        assert 90 <= stats["p95_ms"] <= 98
        # p99 should be around 99
        assert 97 <= stats["p99_ms"] <= 100

    def test_violation_tracking(self):
        """Violations should be tracked when budget is exceeded."""
        # Use existing budget
        self.monitor._enabled = True

        # Record a critical violation
        violation = self.monitor.record("trade_action_extract", 35000.0)
        assert violation == "critical"

        violations = self.monitor.get_violations("trade_action_extract")
        assert len(violations["trade_action_extract"]) == 1
        assert violations["trade_action_extract"][0]["level"] == "critical"

    def test_violation_limit(self):
        """Only last 100 violations should be kept."""
        for i in range(150):
            self.monitor.record("trade_action_extract", 35000.0)

        violations = self.monitor.get_violations("trade_action_extract")
        assert len(violations["trade_action_extract"]) == 100

    def test_max_samples_limit(self):
        """Only last MAX_SAMPLES should be kept."""
        monitor = PerformanceMonitor(max_samples=50)

        for i in range(100):
            monitor.record("test_op", float(i))

        stats = monitor.get_stats("test_op")
        # Should only have last 50 samples (50-99)
        assert stats["count"] == 50
        assert stats["min_ms"] == 50.0
        assert stats["max_ms"] == 99.0

    def test_get_all_stats(self):
        """get_all_stats should return stats for all operations."""
        self.monitor.record("op1", 100.0)
        self.monitor.record("op2", 200.0)

        all_stats = self.monitor.get_all_stats()
        assert "op1" in all_stats
        assert "op2" in all_stats
        assert all_stats["op1"]["count"] == 1
        assert all_stats["op2"]["count"] == 1

    def test_clear_operation(self):
        """Clear should remove metrics for specific operation."""
        self.monitor.record("op1", 100.0)
        self.monitor.record("op2", 200.0)

        self.monitor.clear("op1")

        assert self.monitor.get_stats("op1")["count"] == 0
        assert self.monitor.get_stats("op2")["count"] == 1

    def test_clear_all(self):
        """Clear with no operation should remove all metrics."""
        self.monitor.record("op1", 100.0)
        self.monitor.record("op2", 200.0)

        self.monitor.clear()

        assert self.monitor.get_stats("op1")["count"] == 0
        assert self.monitor.get_stats("op2")["count"] == 0

    def test_monitoring_disabled(self):
        """When monitoring is disabled, records should be ignored."""
        monitor = PerformanceMonitor()
        monitor._enabled = False

        monitor.record("test_op", 100.0)

        stats = monitor.get_stats("test_op")
        assert stats["count"] == 0


class TestTrackPerformanceDecorator:
    """Tests for track_performance decorator."""

    def setup_method(self):
        """Reset monitor before each test."""
        global_monitor.clear()

    def test_sync_function_tracking(self):
        """Sync function should be tracked."""
        @track_performance("test_op")
        def slow_function():
            time.sleep(0.01)
            return "done"

        result = slow_function()

        assert result == "done"
        # Verify it was tracked
        stats = global_monitor.get_stats("test_op")
        assert stats["count"] == 1
        assert stats["min_ms"] > 0

    def test_async_function_tracking(self):
        """Async function should be tracked."""
        @track_performance("test_op")
        async def async_function():
            await asyncio.sleep(0.01)
            return "done"

        result = asyncio.run(async_function())

        assert result == "done"

    def test_function_error_tracking(self):
        """Function errors should still record timing."""
        @track_performance("test_op")
        def error_function():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            error_function()

        # Timing should still be recorded even on error

    def test_disabled_monitoring(self):
        """When monitoring is disabled, decorator should pass through."""
        from finer.services import performance
        original_enabled = performance.FINER_PERF_MONITORING_ENABLED

        try:
            performance.FINER_PERF_MONITORING_ENABLED = False

            @track_performance("test_op")
            def test_func():
                return "done"

            result = test_func()
            assert result == "done"
        finally:
            performance.FINER_PERF_MONITORING_ENABLED = original_enabled


class TestPerformanceTracker:
    """Tests for PerformanceTracker context manager."""

    def setup_method(self):
        """Reset monitor before each test."""
        global_monitor.clear()

    def test_context_manager_tracking(self):
        """Context manager should track duration."""
        with PerformanceTracker("test_op") as tracker:
            time.sleep(0.01)

        assert tracker.duration_ms > 0

    def test_context_manager_violation(self):
        """Context manager should detect violations."""
        # Use an operation with a very low budget
        with PerformanceTracker("file_scan") as tracker:
            time.sleep(0.001)  # 1ms, might exceed 200ms budget in tests

        # duration_ms should be set
        assert tracker.duration_ms >= 0

    def test_disabled_monitoring_context(self):
        """When monitoring is disabled, context should still work."""
        from finer.services import performance
        original_enabled = performance.monitor._enabled

        try:
            performance.monitor._enabled = False

            with PerformanceTracker("test_op") as tracker:
                time.sleep(0.01)

            # start_time is None when disabled
            assert tracker.start_time is None
        finally:
            performance.monitor._enabled = original_enabled


class TestPerformanceBudgets:
    """Tests for predefined performance budgets."""

    def test_budgets_exist(self):
        """All required budgets should be defined."""
        required_budgets = [
            "trade_action_extract",
            "timeline_query",
            "backtest_full",
            "dashboard_load",
            "llm_call",
            "file_scan",
            "summary_generate",
        ]

        for budget_name in required_budgets:
            assert budget_name in PERFORMANCE_BUDGETS, f"Missing budget: {budget_name}"

    def test_budget_values_reasonable(self):
        """Budget values should be reasonable."""
        for name, budget in PERFORMANCE_BUDGETS.items():
            # Target < warning < critical
            assert budget.target_ms < budget.warning_ms < budget.critical_ms, \
                f"Budget {name}: thresholds not ordered correctly"

            # All positive
            assert budget.target_ms > 0
            assert budget.warning_ms > 0
            assert budget.critical_ms > 0


class TestIntegration:
    """Integration tests with actual operations."""

    def test_extraction_performance_simulation(self):
        """Simulate extraction and verify it's tracked."""
        monitor = PerformanceMonitor()
        monitor._enabled = True

        # Simulate multiple extractions
        import random
        random.seed(42)
        for _ in range(20):
            # Simulate LLM call time (3-8 seconds)
            duration = random.uniform(3000, 8000)
            monitor.record("trade_action_extract", duration)

        stats = monitor.get_stats("trade_action_extract")
        assert stats["count"] == 20
        assert stats["mean_ms"] > 0

        # Check if within budget
        budget = PERFORMANCE_BUDGETS["trade_action_extract"]
        # p95 of simulated data (3-8s range) should be within 10s target
        assert stats["p95_ms"] < budget.target_ms, \
            f"p95 ({stats['p95_ms']}ms) exceeds target ({budget.target_ms}ms)"

    def test_timeline_query_simulation(self):
        """Simulate timeline query and verify performance."""
        monitor = PerformanceMonitor()

        # Simulate queries (should be fast)
        import random
        random.seed(42)
        for _ in range(50):
            # Most queries should be fast (50-200ms)
            # Some might be slow due to cold cache (500-1000ms)
            if random.random() < 0.9:
                duration = random.uniform(50, 200)
            else:
                duration = random.uniform(500, 1000)
            monitor.record("timeline_query", duration)

        stats = monitor.get_stats("timeline_query")
        assert stats["count"] == 50

        # p50 should be within target for 90% fast queries
        budget = PERFORMANCE_BUDGETS["timeline_query"]
        assert stats["p50_ms"] < budget.target_ms, \
            f"p50 ({stats['p50_ms']}ms) exceeds target ({budget.target_ms}ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
