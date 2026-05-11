"""Files API — asset listing and upload (F0 intake)."""

from fastapi import APIRouter, UploadFile, File, Query
from typing import Optional
import logging

from finer.api.routes.files_utils import (
    DATA_ROOT,
    WORKFLOW_BY_TIER,
    _assets_cache,
    _build_source_summary,
)
from finer.api.routes.asset_builder import build_workflow_assets
from finer.errors.exceptions import FinerError, FinerInternalError
from finer.errors.codes import ErrorCode

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def get_files(
    tier: str = Query("F1"),
    source_type: Optional[str] = Query(None),
    source_group_id: Optional[str] = Query(None),
    sort_by: str = Query("file_timestamp"),
):
    workflow = WORKFLOW_BY_TIER.get(tier, "library")
    try:
        files = build_workflow_assets(workflow)

        if source_type and source_type != "all":
            files = [f for f in files if f.source_type == source_type]

        if source_group_id:
            files = [f for f in files if f.source_group_id == source_group_id]

        summary = _build_source_summary(files)

        return {
            "contract": "canonical_asset_v1",
            "tier": tier,
            "workflow": workflow,
            "files": [f.model_dump(by_alias=True) for f in files],
            **summary,
        }
    except FinerError:
        raise
    except Exception as e:
        logger.exception(
            "Failed to build canonical asset view for tier=%s workflow=%s",
            tier, workflow,
        )
        raise FinerInternalError(
            ErrorCode.API_INT_001,
            f"Failed to build canonical asset view: {type(e).__name__}: {e}",
            cause=e,
            tier=tier,
            workflow=workflow,
        ) from e


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    try:
        target_dir = DATA_ROOT / "raw" / "_inbox" / "unclassified"
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / file.filename
        with open(file_path, "wb") as buffer:
            import shutil
            shutil.copyfileobj(file.file, buffer)

        _assets_cache.clear()

        return {
            "success": True,
            "contract": "canonical_asset_v1",
            "message": f"File {file.filename} imported into canonical intake inbox",
            "path": str(file_path),
            "workflow": "intake",
            "stageBadge": "F0"
        }
    except Exception as e:
        raise FinerError(
            ErrorCode.F0_IO_001,
            f"Failed to upload file: {e}",
            stage="F0",
            operation="file_upload",
            source_channel="local",
            retryable=True,
            cause=e,
        )
