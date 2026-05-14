"""F0 Index API — Import Console query endpoints.

Backed by Project Memory SQLite (asset_index for F0-stage assets,
schema inspection for health).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from finer.errors import ErrorCode, FinerError
from finer.paths import F0_INDEX_DB_PATH
from finer.schemas.f0_index import F0IndexHealth, F0IndexQuery, F0IndexResult
from finer.startup import check_f0_index_on_startup, rebuild_f0_index

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/f0-index", tags=["F0 Project Memory"])


def _get_connection():
    """Get a Project Memory connection, raising on failure."""
    from finer.services.project_memory.connection import get_connection
    return get_connection(F0_INDEX_DB_PATH)


@router.get("/records")
async def list_f0_records(
    source_type: str | None = None,
    source_platform: str | None = None,
    creator_id: str | None = None,
    sort_by: str = "collected_at",
    sort_order: str = "desc",
    limit: int = Query(50, le=200),
    offset: int = 0,
) -> dict:
    """Query F0 content records from asset_index."""
    startup = check_f0_index_on_startup()
    if startup.state.value in ("missing", "corrupt"):
        raise FinerError(
            ErrorCode.F0_INDEX_001,
            f"F0 index not available: {startup.message}",
            stage="F0",
            operation="list_records",
            retryable=startup.state.value == "missing",
        )

    try:
        conn = _get_connection()
        # Query asset_index for F0-stage assets
        valid_sort = sort_by if sort_by in ("updated_at", "display_name") else "updated_at"
        order = "DESC" if sort_order.lower() == "desc" else "ASC"

        # Count total
        count_row = conn.execute(
            "SELECT COUNT(*) FROM asset_index WHERE stage = 'F0'"
        ).fetchone()
        total_count = count_row[0] if count_row else 0

        # Fetch page
        rows = conn.execute(
            f"SELECT * FROM asset_index WHERE stage = 'F0' "
            f"ORDER BY {valid_sort} {order} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

        records = [dict(r) for r in rows]

        return {
            "ok": True,
            "data": F0IndexResult(
                records=records,
                total_count=total_count,
                page=offset // limit if limit > 0 else 0,
                page_size=limit,
                has_more=(offset + limit) < total_count,
            ).__dict__,
        }

    except FinerError:
        raise
    except Exception as exc:
        logger.exception("F0 index records query failed")
        raise FinerError(
            ErrorCode.F0_INDEX_002,
            f"Query failed: {exc}",
            stage="F0",
            operation="list_records",
            retryable=True,
        )


@router.get("/health")
async def get_f0_index_health() -> dict:
    """Return F0 index health status for Import Console."""
    try:
        startup = check_f0_index_on_startup()
        if startup.health is None:
            # Build a degraded health payload
            from finer.services.project_memory.connection import get_connection
            from finer.services.project_memory.schema import SchemaInspector

            try:
                conn = get_connection(F0_INDEX_DB_PATH)
                inspector = SchemaInspector(conn)
                report = inspector.validate_schema()
                status = "missing" if report.status.value == "missing" else "stale"
            except Exception:
                status = "missing"

            return {
                "ok": True,
                "data": F0IndexHealth(
                    status=status,
                    record_count=0,
                    last_rebuild_at=None,
                    last_rebuild_duration_ms=None,
                    manifest_count_on_disk=0,
                    drift=0,
                    db_path=str(F0_INDEX_DB_PATH),
                    db_size_bytes=0,
                ).__dict__,
            }

        return {
            "ok": True,
            "data": startup.health.__dict__,
        }

    except Exception as exc:
        logger.exception("F0 index health check failed")
        raise FinerError(
            ErrorCode.F0_INDEX_002,
            f"Health check failed: {exc}",
            stage="F0",
            operation="health",
            retryable=True,
        )


@router.post("/rebuild")
async def trigger_f0_index_rebuild(background: bool = True) -> dict:
    """Explicitly trigger F0 index rebuild (asset_index projection)."""
    try:
        result = rebuild_f0_index(background=background)
        if background:
            return {
                "ok": True,
                "data": {
                    "task_id": result,
                    "status": "started",
                },
            }
        return {
            "ok": True,
            "data": {
                "status": "completed",
                "result": result,
            },
        }
    except Exception as exc:
        logger.exception("F0 index rebuild failed")
        raise FinerError(
            ErrorCode.F0_INDEX_003,
            f"Rebuild failed: {exc}",
            stage="F0",
            operation="rebuild",
            retryable=True,
        )
