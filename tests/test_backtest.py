"""Tests for Backtest Engine."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from finer.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
    PortfolioSimulator,
    Position,
    PositionSide,
    ExitReason,
    run_simple_backtest,
)


class TestBacktestConfig:
    """Test BacktestConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BacktestConfig()
        assert config.initial_capital == 100000.0
        assert config.default_position_pct == 0.1
        assert config.commission_pct == 0.001
        assert config.slippage_pct == 0.0005
        assert config.allow_short_selling is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = BacktestConfig(
            initial_capital=50000.0,
            default_position_pct=0.05,
            commission_pct=0.002,
        )
        assert config.initial_capital == 50000.0
        assert config.default_position_pct == 0.05
        assert config.commission_pct == 0.002


class TestPortfolioSimulator:
    """Test PortfolioSimulator."""

    def test_initialization(self):
        """Test simulator initialization."""
        simulator = PortfolioSimulator()
        assert simulator.cash == 100000.0
        assert len(simulator.positions) == 0
        assert len(simulator.trades) == 0

    def test_open_long_position(self):
        """Test opening a long position."""
        simulator = PortfolioSimulator()
        position = simulator.open_position(
            ticker="AAPL",
            side=PositionSide.LONG,
            price=150.0,
            date=datetime.now(),
        )

        assert position is not None
        assert position.ticker == "AAPL"
        assert position.side == PositionSide.LONG
        assert position.entry_price > 150.0  # Includes slippage
        assert "AAPL" in simulator.positions

    def test_open_short_position(self):
        """Test opening a short position."""
        config = BacktestConfig(allow_short_selling=True)
        simulator = PortfolioSimulator(config)
        position = simulator.open_position(
            ticker="TSLA",
            side=PositionSide.SHORT,
            price=200.0,
            date=datetime.now(),
        )

        assert position is not None
        assert position.side == PositionSide.SHORT

    def test_close_position(self):
        """Test closing a position."""
        simulator = PortfolioSimulator()
        simulator.open_position(
            ticker="AAPL",
            side=PositionSide.LONG,
            price=150.0,
            date=datetime.now(),
        )

        trade = simulator.close_position(
            ticker="AAPL",
            price=160.0,
            date=datetime.now(),
            exit_reason=ExitReason.MANUAL,
        )

        assert trade is not None
        assert trade.ticker == "AAPL"
        assert trade.return_pct > 0  # Profitable trade
        assert "AAPL" not in simulator.positions

    def test_stop_loss_exit(self):
        """Test stop loss triggered exit."""
        config = BacktestConfig(default_stop_loss_pct=0.1)
        simulator = PortfolioSimulator(config)
        position = simulator.open_position(
            ticker="AAPL",
            side=PositionSide.LONG,
            price=150.0,
            date=datetime.now(),
        )

        # Price drops below stop loss
        current_price = position.entry_price * 0.85  # 15% drop
        assert position.stop_loss_price is not None
        assert current_price < position.stop_loss_price

    def test_position_sizing(self):
        """Test position sizing constraints."""
        config = BacktestConfig(
            initial_capital=100000.0,
            default_position_pct=0.1,
            max_position_pct=0.25,
        )
        simulator = PortfolioSimulator(config)

        # Open position
        position = simulator.open_position(
            ticker="AAPL",
            side=PositionSide.LONG,
            price=150.0,
            date=datetime.now(),
        )

        # Position should be approximately 10% of capital
        expected_value = 100000.0 * 0.1
        assert position.entry_value < expected_value * 1.1  # Allow for costs

    def test_snapshot(self):
        """Test portfolio snapshot."""
        simulator = PortfolioSimulator()
        simulator.open_position(
            ticker="AAPL",
            side=PositionSide.LONG,
            price=150.0,
            date=datetime.now(),
        )

        snapshot = simulator.take_snapshot(
            date=datetime.now(),
            prices={"AAPL": 155.0},
        )

        assert snapshot.num_positions == 1
        assert snapshot.total_value > 0
        assert snapshot.date is not None


class TestBacktestEngine:
    """Test BacktestEngine."""

    @pytest.fixture
    def sample_price_data(self):
        """Create sample price data."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        data = []
        for date in dates:
            for ticker in ["AAPL", "MSFT"]:
                price = 150.0 + np.random.randn() * 5
                data.append({
                    "date": date,
                    "ticker": ticker,
                    "open": price,
                    "high": price * 1.02,
                    "low": price * 0.98,
                    "close": price,
                    "volume": 1000000,
                })
        return pd.DataFrame(data)

    @pytest.fixture
    def sample_actions(self):
        """Create sample trade actions."""
        return [
            {
                "timestamp": "2024-01-05",
                "ticker": "AAPL",
                "direction": "bullish",
                "action_type": "long",
                "trade_action_id": "ta_001",
                "kol_id": "kol_001",
            },
            {
                "timestamp": "2024-01-15",
                "ticker": "MSFT",
                "direction": "bearish",
                "action_type": "short",
                "trade_action_id": "ta_002",
                "kol_id": "kol_001",
            },
        ]

    def test_run_backtest(self, sample_price_data, sample_actions):
        """Test running a full backtest."""
        engine = BacktestEngine()
        result = engine.run_backtest(
            actions=sample_actions,
            price_data=sample_price_data,
        )

        assert result is not None
        assert result.backtest_id is not None
        assert result.initial_capital == 100000.0
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)

    def test_backtest_with_config(self, sample_price_data, sample_actions):
        """Test backtest with custom config."""
        config = BacktestConfig(
            initial_capital=50000.0,
            commission_pct=0.002,
        )
        engine = BacktestEngine(config)
        result = engine.run_backtest(
            actions=sample_actions,
            price_data=sample_price_data,
        )

        assert result.initial_capital == 50000.0
        assert "commission_pct" in result.config

    def test_backtest_metrics(self, sample_price_data, sample_actions):
        """Test backtest metrics calculation."""
        engine = BacktestEngine()
        result = engine.run_backtest(
            actions=sample_actions,
            price_data=sample_price_data,
        )

        # Check all metrics are calculated
        assert hasattr(result, "total_return")
        assert hasattr(result, "annualized_return")
        assert hasattr(result, "volatility")
        assert hasattr(result, "sharpe_ratio")
        assert hasattr(result, "max_drawdown")
        assert hasattr(result, "win_rate")

    def test_kol_attribution(self, sample_price_data, sample_actions):
        """Test KOL attribution in backtest."""
        engine = BacktestEngine()
        result = engine.run_backtest(
            actions=sample_actions,
            price_data=sample_price_data,
        )

        # Check KOL metrics if trades occurred
        if result.total_trades > 0:
            assert isinstance(result.kol_metrics, dict)

    def test_empty_actions(self, sample_price_data):
        """Test backtest with no actions."""
        engine = BacktestEngine()
        result = engine.run_backtest(
            actions=[],
            price_data=sample_price_data,
        )

        assert result.total_trades == 0


class TestRunSimpleBacktest:
    """Test convenience function."""

    def test_simple_backtest(self):
        """Test simple backtest wrapper."""
        price_data = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "ticker": ["AAPL"] * 10,
            "open": [150.0] * 10,
            "high": [152.0] * 10,
            "low": [148.0] * 10,
            "close": [150.0 + i for i in range(10)],
            "volume": [1000000] * 10,
        })

        actions = [{
            "timestamp": "2024-01-03",
            "ticker": "AAPL",
            "direction": "bullish",
            "action_type": "long",
        }]

        result = run_simple_backtest(actions, price_data)
        assert result is not None
