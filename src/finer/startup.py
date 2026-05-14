"""F0 Project Memory — startup check.

Uses Project Memory SQLite schema inspection to determine index health
without performing any filesystem scan.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from finer.paths import F0_INDEX_DB_PATH
from finer.schemas.f0_index import F0IndexHealth

logger = logging.getLogger(__name__)


class F0IndexStartupState(str, Enum):
    """Startup states for F0 index."""
    READY = "ready"
    STALE = "stale"
    MISSING = "missing"
    CORRUPT = "corrupt"


@dataclass
class F0StartupResult:
    """Result of F0 index startup check."""
    state: F0IndexStartupState
    health: F0IndexHealth | None
    message: str
    action_taken: str  # "none" | "loaded" | "background_rebuild_scheduled"


def _build_health_from_schema(conn) -> F0IndexHealth:
    """Build F0IndexHealth from Project Memory schema inspection."""
    from finer.services.project_memory.schema import SchemaHealth, SchemaInspector
    from finer.services.project_memory.asset_index import AssetIndexService

    inspector = SchemaInspector(conn)
    report = inspector.validate_schema()

    # Map schema health to F0 index status
    status_map = {
        SchemaHealth.HEALTHY: "healthy",
        SchemaHealth.DEGRADED: "stale",
        SchemaHealth.MISSING: "missing",
        SchemaHealth.CORRUPT: "missing",
        SchemaHealth.SCHEMA_MISMATCH: "stale",
    }
    status = status_map.get(report.status, "missing")

    # Count F0 assets if asset_index table exists
    record_count = 0
    try:
        asset_svc = AssetIndexService(conn)
        record_count = asset_svc.count_assets(stage="F0")
    except Exception:
        pass

    # Read rebuild metadata from project_memory_meta
    last_rebuild_at = None
    last_rebuild_duration_ms = None
    try:
        row = conn.execute(
            "SELECT value FROM project_memory_meta WHERE key = 'last_rebuild_at'"
        ).fetchone()
        if row:
            last_rebuild_at = row[0]
        row = conn.execute(
            "SELECT value FROM project_memory_meta WHERE key = 'last_rebuild_duration_ms'"
        ).fetchone()
        if row:
            last_rebuild_duration_ms = int(row[0])
    except Exception:
        pass

    # Compute drift: if schema is healthy, drift is 0 (asset_index is derived)
    drift = 0

    db_path = str(F0_INDEX_DB_PATH)
    db_size_bytes = 0
    try:
        db_size_bytes = F0_INDEX_DB_PATH.stat().st_size
    except OSError:
        pass

    return F0IndexHealth(
        status=status,
        record_count=record_count,
        last_rebuild_at=last_rebuild_at,
        last_rebuild_duration_ms=last_rebuild_duration_ms,
        manifest_count_on_disk=record_count,  # asset_index is the manifest projection
        drift=drift,
        db_path=db_path,
        db_size_bytes=db_size_bytes,
    )


def check_f0_index_on_startup(db_path: Path = F0_INDEX_DB_PATH) -> F0StartupResult:
    """Check F0 index health at startup. NEVER triggers full rebuild synchronously.

    Uses Project Memory SQLite schema inspection. No filesystem scan.
    """
    from finer.services.project_memory.connection import get_connection
    from finer.services.project_memory.schema import SchemaHealth, SchemaInspector

    if not db_path.exists():
        return F0StartupResult(
            state=F0IndexStartupState.MISSING,
            health=None,
            message="F0 index database not found on disk",
            action_taken="none",
        )

    try:
        conn = get_connection(db_path)
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()

        if report.status == SchemaHealth.CORRUPT:
            return F0StartupResult(
                state=F0IndexStartupState.CORRUPT,
                health=None,
                message=f"Database corrupt: {report.errors}",
                action_taken="none",
            )

        if report.status == SchemaHealth.MISSING:
            return F0StartupResult(
                state=F0IndexStartupState.MISSING,
                health=None,
                message="Required tables missing from database",
                action_taken="none",
            )

        health = _build_health_from_schema(conn)

        if report.status == SchemaHealth.HEALTHY:
            return F0StartupResult(
                state=F0IndexStartupState.READY,
                health=health,
                message="F0 index loaded successfully",
                action_taken="loaded",
            )

        # DEGRADED or SCHEMA_MISMATCH → stale
        return F0StartupResult(
            state=F0IndexStartupState.STALE,
            health=health,
            message=f"Schema degraded: {report.errors}",
            action_taken="loaded",
        )

    except Exception as exc:
        logger.warning("F0 index startup check failed: %s", exc)
        return F0StartupResult(
            state=F0IndexStartupState.CORRUPT,
            health=None,
            message=f"Startup check failed: {exc}",
            action_taken="none",
        )


def rebuild_f0_index(db_path: Path = F0_INDEX_DB_PATH, *, background: bool = True) -> str:
    """Rebuild F0 asset_index from authoritative Project Memory tables.

    Does NOT scan raw files — only rebuilds the derived asset_index projection.

    Args:
        db_path: Path to SQLite database
        background: If True, run in background thread and return task_id

    Returns:
        task_id if background, "sync_complete" if synchronous
    """
    import time
    import uuid

    def _do_rebuild() -> None:
        from finer.services.project_memory.connection import get_connection
        from finer.services.project_memory.asset_index import AssetIndexService

        start = time.monotonic()
        try:
            conn = get_connection(db_path)
            asset_svc = AssetIndexService(conn)
            count = asset_svc.rebuild_all()
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Update metadata
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            conn.execute(
                "INSERT OR REPLACE INTO project_memory_meta (key, value, updated_at) "
                "VALUES ('last_rebuild_at', ?, ?)",
                (now_iso, now_iso),
            )
            conn.execute(
                "INSERT OR REPLACE INTO project_memory_meta (key, value, updated_at) "
                "VALUES ('last_rebuild_duration_ms', ?, ?)",
                (str(elapsed_ms), now_iso),
            )
            conn.commit()
            logger.info("F0 index rebuilt: %d assets in %dms", count, elapsed_ms)
        except Exception:
            logger.exception("F0 index rebuild failed")

    if background:
        task_id = f"f0-rebuild-{uuid.uuid4().hex[:8]}"
        thread = threading.Thread(target=_do_rebuild, name=task_id, daemon=True)
        thread.start()
        return task_id

    _do_rebuild()
    return "sync_complete"
