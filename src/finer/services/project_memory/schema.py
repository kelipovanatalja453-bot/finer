"""Schema inspection and health validation for Project Memory."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SchemaHealth(str, Enum):
    """Possible health states for a Project Memory database."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    MISSING = "missing"
    CORRUPT = "corrupt"
    SCHEMA_MISMATCH = "schema_mismatch"


# Tables that must exist for a healthy Project Memory database.
_REQUIRED_TABLES: frozenset[str] = frozenset(
    {
        "projects",
        "project_memory_meta",
        "schema_migrations",
        "source_groups",
        "source_records",
        "content_identities",
        "content_versions",
        "source_content_links",
        "contents",
        "storage_objects",
        "manifests",
        "artifacts",
        "content_blocks",
        "topic_blocks",
        "topic_block_members",
        "artifact_edges",
        "name_bindings",
        "stage_status",
        "asset_index",
    }
)


@dataclass
class SchemaHealthReport:
    """Structured result of a schema health check."""

    status: SchemaHealth
    version: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class SchemaInspector:
    """Read-only inspector for a Project Memory SQLite database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_applied_migrations(self) -> list[dict[str, Any]]:
        """Return rows from ``schema_migrations`` ordered by version."""
        try:
            rows = self._conn.execute(
                "SELECT version, name, checksum, applied_at, applied_by, execution_ms "
                "FROM schema_migrations ORDER BY version"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def validate_schema(self) -> SchemaHealthReport:
        """Check that all required tables exist and return a health report."""
        errors: list[str] = []

        # Check if the database is accessible and not corrupt.
        try:
            self._conn.execute("SELECT 1")
        except Exception as exc:
            return SchemaHealthReport(
                status=SchemaHealth.CORRUPT,
                errors=[f"Database unreachable: {exc}"],
            )

        # Gather existing table names.
        existing = self._existing_tables()

        # Check required tables.
        missing = sorted(_REQUIRED_TABLES - existing)
        if missing:
            errors.append(f"Missing tables: {', '.join(missing)}")

        # Read schema version.
        version = self.get_schema_version()

        # Collect counts.
        counts = self.get_table_counts()

        # Determine status.
        if missing:
            if len(missing) == len(_REQUIRED_TABLES):
                status = SchemaHealth.MISSING
            else:
                status = SchemaHealth.DEGRADED
        else:
            status = SchemaHealth.HEALTHY

        return SchemaHealthReport(
            status=status,
            version=version,
            counts=counts,
            errors=errors,
        )

    def get_table_counts(self) -> dict[str, int]:
        """Return ``{table_name: row_count}`` for every Project Memory table."""
        existing = self._existing_tables()
        counts: dict[str, int] = {}
        for table in sorted(existing):
            try:
                row = self._conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
                counts[table] = row[0] if row else 0
            except sqlite3.OperationalError:
                counts[table] = -1
        return counts

    def get_schema_version(self) -> int | None:
        """Read ``schema_version`` from ``project_memory_meta``."""
        try:
            row = self._conn.execute(
                "SELECT value FROM project_memory_meta WHERE key = 'schema_version'"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None:
            return None
        try:
            return int(row[0])
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _existing_tables(self) -> set[str]:
        """Return the set of user-created table names in the database."""
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {r[0] for r in rows}
