"""Files API — asset listing and upload (F0 intake).

Primary query path is catalog-first via Project Memory asset_index.
Falls back to filesystem scan (degraded_scan) when Project Memory is unavailable.
"""

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

# Canonical F-stage → asset_index.stage mapping
_TIER_TO_STAGE = {
    "F0": "F0",
    "F1": "F1",
    "F2": "F2",
    "F5": "F5",
    "F6": "F6",
    "F8": "F8",
}


def _try_catalog_query(
    stage: str,
    limit: int,
    offset: int,
    q: Optional[str],
    source_type: Optional[str],
    source_group_id: Optional[str],
) -> Optional[dict]:
    """Attempt to serve the request from Project Memory asset_index.

    Returns a dict with 'files' list and 'projectMemory' metadata,
    or None if Project Memory is unavailable.
    """
    try:
        from finer.paths import PROJECT_MEMORY_DB
        if not PROJECT_MEMORY_DB.exists():
            return None

        from finer.services.project_memory.connection import get_connection
        from finer.services.project_memory.schema import SchemaInspector, SchemaHealth
        from finer.services.project_memory.asset_index import AssetIndexService
        from finer.services.project_memory.name_lineage import NameLineageService

        conn = get_connection(PROJECT_MEMORY_DB)
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()

        if report.status not in (SchemaHealth.HEALTHY, SchemaHealth.DEGRADED):
            logger.warning(
                "Project Memory schema status=%s, falling back to degraded scan",
                report.status.value,
            )
            return None

        asset_svc = AssetIndexService(conn)
        name_svc = NameLineageService(conn)

        # Query assets
        if q:
            raw_assets = asset_svc.search(q, stage=stage, limit=limit + offset)
        else:
            raw_assets = asset_svc.list_assets(
                stage=stage, limit=limit + offset, offset=0
            )

        # Apply pagination after search (search doesn't support offset directly)
        if q:
            raw_assets = raw_assets[offset : offset + limit]

        # Filter by source_type / source_group_id if provided
        if source_type and source_type != "all":
            raw_assets = [a for a in raw_assets if a.get("source_type") == source_type]
        if source_group_id:
            raw_assets = [a for a in raw_assets if a.get("source_group_id") == source_group_id]

        # Build response assets with name_lineage
        files = []
        for a in raw_assets:
            content_id = a["content_id"]

            # Resolve name lineage
            names = name_svc.get_names_for_content(content_id)
            name_lineage = _build_name_lineage(names, a)

            # Resolve content_version_id
            content_version_id = None
            try:
                row = conn.execute(
                    "SELECT active_content_version_id FROM contents WHERE content_id = ?",
                    (content_id,),
                ).fetchone()
                if row:
                    content_version_id = row["active_content_version_id"]
            except Exception:
                pass

            # Resolve source_record_id
            source_record_id = None
            try:
                row = conn.execute(
                    "SELECT primary_source_record_id FROM contents WHERE content_id = ?",
                    (content_id,),
                ).fetchone()
                if row:
                    source_record_id = row["primary_source_record_id"]
            except Exception:
                pass

            files.append({
                "id": a["asset_id"],
                "contentId": content_id,
                "contentVersionId": content_version_id,
                "stage": a["stage"],
                "name": a.get("display_name", content_id),
                "sourceRecordId": source_record_id,
                "sourceGroupId": a.get("source_group_id"),
                "latestArtifactId": a.get("latest_artifact_id"),
                "manifestId": a.get("manifest_id"),
                "nameLineage": name_lineage,
            })

        # Get asset_index updated_at for metadata
        asset_index_updated_at = None
        try:
            row = conn.execute(
                "SELECT MAX(updated_at) FROM asset_index WHERE stage = ?",
                (stage,),
            ).fetchone()
            if row and row[0]:
                asset_index_updated_at = row[0]
        except Exception:
            pass

        # Get project_id
        project_id = None
        try:
            row = conn.execute(
                "SELECT project_id FROM projects WHERE is_active = 1 LIMIT 1"
            ).fetchone()
            if row:
                project_id = row["project_id"]
        except Exception:
            pass

        schema_version = report.version

        return {
            "files": files,
            "projectMemory": {
                "projectId": project_id,
                "schemaVersion": str(schema_version) if schema_version else None,
                "dbPath": str(PROJECT_MEMORY_DB),
                "assetIndexUpdatedAt": asset_index_updated_at,
                "degraded": report.status == SchemaHealth.DEGRADED,
            },
        }

    except Exception as e:
        logger.warning("Project Memory catalog query failed: %s", e, exc_info=True)
        return None


def _build_name_lineage(names: dict, asset: dict) -> dict:
    """Build nameLineage dict from name_bindings grouped data."""
    lineage = {
        "originalFilename": None,
        "f0DisplayName": None,
        "f1EnvelopeTitle": None,
        "splitFilename": None,
        "materializedFilename": None,
    }

    # Map namespace.kind to lineage fields
    for key, bindings in names.items():
        if not bindings:
            continue
        primary = next((b for b in bindings if b.get("is_primary")), bindings[0])
        value = primary.get("display_value")
        if not value:
            continue

        if key == "source.original_filename":
            lineage["originalFilename"] = value
        elif key == "f0.display_name":
            lineage["f0DisplayName"] = value
        elif key == "f1.envelope_title":
            lineage["f1EnvelopeTitle"] = value
        elif key == "f1.split_filename":
            lineage["splitFilename"] = value
        elif key == "materialization.filename":
            lineage["materializedFilename"] = value

    # Fallback: use asset display_name if lineage is empty
    display_name = asset.get("display_name")
    if display_name and not any(lineage.values()):
        lineage["f0DisplayName"] = display_name

    return lineage


@router.get("")
async def get_files(
    tier: str = Query("F1"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    source_group_id: Optional[str] = Query(None),
    sort_by: str = Query("file_timestamp"),
):
    # Resolve canonical stage from tier
    stage = _TIER_TO_STAGE.get(tier)
    workflow = WORKFLOW_BY_TIER.get(tier, "library")

    # Attempt catalog-first query
    if stage:
        catalog_result = _try_catalog_query(
            stage=stage,
            limit=limit,
            offset=offset,
            q=q,
            source_type=source_type,
            source_group_id=source_group_id,
        )
        if catalog_result is not None:
            return {
                "ok": True,
                "source": "catalog",
                "contract": "canonical_asset_v1",
                "tier": tier,
                "workflow": workflow,
                "files": catalog_result["files"],
                "projectMemory": catalog_result["projectMemory"],
            }

    # Degraded fallback: filesystem scan via asset_builder
    try:
        files = build_workflow_assets(workflow)

        if source_type and source_type != "all":
            files = [f for f in files if f.source_type == source_type]

        if source_group_id:
            files = [f for f in files if f.source_group_id == source_group_id]

        # Apply limit/offset
        total = len(files)
        files = files[offset : offset + limit]

        summary = _build_source_summary(files)

        return {
            "ok": True,
            "source": "degraded_scan",
            "contract": "canonical_asset_v1",
            "tier": tier,
            "workflow": workflow,
            "files": [f.model_dump(by_alias=True) for f in files],
            "projectMemory": None,
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
