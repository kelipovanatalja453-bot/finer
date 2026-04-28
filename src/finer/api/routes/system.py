"""System API — cache management and diagnostics."""

from fastapi import APIRouter
import json as json_mod

from finer.api.routes.files_utils import (
    DATA_ROOT,
    _assets_cache,
    _manifests_index,
    _build_manifests_index,
    get_manifests_index,
)
from finer.api.routes.asset_builder import build_workflow_assets

router = APIRouter()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """Manually invalidate all caches."""
    global _manifests_index
    _assets_cache.clear()
    _manifests_index = None
    return {"status": "ok", "message": "All caches invalidated"}


@router.post("/cache/warmup")
async def warmup_cache():
    """Pre-build caches for faster subsequent loads."""
    global _manifests_index

    _manifests_index = _build_manifests_index()

    for workflow in ["intake", "library", "parsing"]:
        build_workflow_assets(workflow, use_cache=True)

    return {
        "status": "ok",
        "manifests_indexed": _manifests_index["count"],
        "workflows_cached": ["intake", "library", "parsing"],
    }


@router.get("/diagnostics")
async def get_diagnostics():
    """Get diagnostic info about data and sync status."""
    l0_count = sum(1 for _ in (DATA_ROOT / "L0_ingest").rglob("*") if _.is_file() and not _.name.endswith(".json"))
    raw_count = sum(1 for _ in (DATA_ROOT / "raw").rglob("*") if _.is_file() and not _.name.endswith(".json")) if (DATA_ROOT / "raw").exists() else 0
    manifest_count = len(get_manifests_index()["by_content_id"])

    sync_state_path = DATA_ROOT / ".feishu_sync_state.json"
    sync_state = {}
    if sync_state_path.exists():
        sync_state = json_mod.loads(sync_state_path.read_text())

    feishu_pool_count = sum(1 for _ in (DATA_ROOT / "feishu_sync_pool").iterdir() if _.is_file()) if (DATA_ROOT / "feishu_sync_pool").exists() else 0

    return {
        "dataRoot": str(DATA_ROOT),
        "fileCounts": {
            "l0_ingest": l0_count,
            "raw": raw_count,
            "manifests": manifest_count,
            "feishu_pool_pending": feishu_pool_count,
        },
        "syncState": sync_state,
        "cacheStatus": {
            "assets_cache_entries": len(_assets_cache),
            "manifests_index_built": _manifests_index is not None,
        },
    }
