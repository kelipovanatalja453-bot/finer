from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from finer.task_cards import TaskCardRequest, generate_task_card


ROOT = Path(__file__).resolve().parents[1]


def test_generate_f8_task_card_from_contracts() -> None:
    generated = generate_task_card(
        ROOT,
        TaskCardRequest(
            line="D",
            stage="F8",
            targets=("src/finer/backtest/engine.py",),
            goal="Wire F8 backend output.",
        ),
    )

    assert generated.boundary.status == "OK"
    assert "Line D - F8 Backtest API + Revenue Curve" in generated.markdown
    assert "F-stage input: F5 `TradeAction[]`" in generated.markdown
    assert "F-stage output: `BacktestResult`" in generated.markdown
    assert "src/finer/backtest/engine.py is covered" in generated.markdown
    assert "pytest tests/test_backtest.py" in generated.markdown


def test_generate_f0_task_card_includes_red_lines() -> None:
    generated = generate_task_card(
        ROOT,
        TaskCardRequest(
            line="A",
            stage="F0",
            targets=("src/finer/ingestion/wechat_adapter.py",),
        ),
    )

    assert generated.boundary.status == "OK"
    assert "Line A - F0 Intake Repair" in generated.markdown
    assert "F-stage output: `ContentRecord`" in generated.markdown
    assert "src/finer/parsing/**" in generated.markdown
    assert "Actual SQLite schema creation or data migration requires user confirmation" in generated.markdown
    assert "src/finer/ingestion/wechat_adapter.py is covered" in generated.markdown


def test_generate_f0_task_card_blocks_forbidden_target() -> None:
    generated = generate_task_card(
        ROOT,
        TaskCardRequest(
            line="A",
            stage="F0",
            targets=("src/finer/backtest/engine.py",),
        ),
    )

    assert generated.boundary.status == "BLOCKED"
    assert "matches forbidden pattern(s): src/finer/backtest/**" in generated.markdown


def test_task_card_script_smoke() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_agent_task_card.py"),
            "--line",
            "D",
            "--stage",
            "F8",
            "--target",
            "src/finer/backtest/engine.py",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "# Agent Task Card" in result.stdout
    assert "Boundary status: OK" in result.stdout
