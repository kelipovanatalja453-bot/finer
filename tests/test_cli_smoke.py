from pathlib import Path

from finer.pipeline import dry_run_pipeline, init_storage


def test_init_storage(tmp_path: Path) -> None:
    result = init_storage(tmp_path)
    assert result["status"] == "ok"
    assert (tmp_path / "data" / "raw" / "trader_ji" / "weekly_strategy").exists()


def test_dry_run_pipeline(tmp_path: Path) -> None:
    init_storage(tmp_path)
    result = dry_run_pipeline(tmp_path)
    assert result["status"] == "ok"
    assert result["summary"]["manifests_found"] == 0
