"""Artifact ledger — CRUD, canonicality, and lineage edges."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


VALID_STAGES = frozenset(
    {"F0", "F1", "F1_5", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F_PLUS"}
)

VALID_RELATIONS = frozenset(
    {
        "derived_from",
        "standardizes",
        "assembles",
        "anchors",
        "extracts_intent_from",
        "maps_policy_from",
        "executes_from",
        "reviews",
        "backtests",
    }
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_artifact_id() -> str:
    return f"art_{uuid.uuid4()}"


class ArtifactStore:
    """Manages ``artifacts`` and ``artifact_edges`` rows."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Artifact CRUD
    # ------------------------------------------------------------------

    def create_artifact(
        self,
        content_id: str,
        stage: str,
        artifact_type: str,
        role: str,
        object_id: str,
        *,
        manifest_id: Optional[str] = None,
        schema_name: Optional[str] = None,
        schema_version: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Insert a new artifact row and return its ``artifact_id``."""
        if stage not in VALID_STAGES:
            raise ValueError(f"Invalid stage: {stage!r}. Must be one of {sorted(VALID_STAGES)}")

        artifact_id = _new_artifact_id()
        now = _utcnow_iso()

        # Compute next version number for this content+stage+type.
        row = self._conn.execute(
            """
            SELECT COALESCE(MAX(artifact_version), 0) FROM artifacts
            WHERE content_id = ? AND stage = ? AND artifact_type = ?
            """,
            (content_id, stage, artifact_type),
        ).fetchone()
        next_version = (row[0] or 0) + 1

        self._conn.execute(
            """
            INSERT INTO artifacts
                (artifact_id, content_id, stage, artifact_type, role, object_id,
                 manifest_id, schema_name, schema_version, run_id,
                 artifact_version, is_canonical, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                artifact_id,
                content_id,
                stage,
                artifact_type,
                role,
                object_id,
                manifest_id,
                schema_name,
                schema_version,
                run_id,
                next_version,
                now,
                json.dumps(metadata) if metadata else None,
            ),
        )
        self._conn.commit()
        return artifact_id

    def get_artifact(self, artifact_id: str) -> Optional[sqlite3.Row]:
        """Return the artifact row, or ``None``."""
        return self._conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()

    def get_canonical_artifact(
        self,
        content_id: str,
        stage: str,
        artifact_type: Optional[str] = None,
    ) -> Optional[sqlite3.Row]:
        """Return the latest canonical artifact for *content_id* + *stage*."""
        if artifact_type is not None:
            return self._conn.execute(
                """
                SELECT * FROM artifacts
                WHERE content_id = ? AND stage = ? AND artifact_type = ? AND is_canonical = 1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (content_id, stage, artifact_type),
            ).fetchone()
        return self._conn.execute(
            """
            SELECT * FROM artifacts
            WHERE content_id = ? AND stage = ? AND is_canonical = 1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (content_id, stage),
        ).fetchone()

    def list_artifacts_for_content(
        self, content_id: str, stage: Optional[str] = None
    ) -> list[sqlite3.Row]:
        """List all artifacts for a content item, optionally filtered by stage."""
        if stage is not None:
            return self._conn.execute(
                """
                SELECT * FROM artifacts
                WHERE content_id = ? AND stage = ?
                ORDER BY created_at DESC
                """,
                (content_id, stage),
            ).fetchall()
        return self._conn.execute(
            """
            SELECT * FROM artifacts
            WHERE content_id = ?
            ORDER BY stage, created_at DESC
            """,
            (content_id,),
        ).fetchall()

    def mark_canonical(self, artifact_id: str) -> None:
        """Set ``is_canonical=1`` for *artifact_id*, clearing siblings."""
        row = self._conn.execute(
            "SELECT content_id, stage, artifact_type FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Artifact not found: {artifact_id}")

        content_id, stage, artifact_type = row[0], row[1], row[2]
        # Clear canonical for same content+stage+type.
        self._conn.execute(
            """
            UPDATE artifacts SET is_canonical = 0
            WHERE content_id = ? AND stage = ? AND artifact_type = ?
            """,
            (content_id, stage, artifact_type),
        )
        self._conn.execute(
            "UPDATE artifacts SET is_canonical = 1 WHERE artifact_id = ?",
            (artifact_id,),
        )
        self._conn.commit()

    def mark_non_canonical(self, artifact_id: str) -> None:
        """Set ``is_canonical=0`` for *artifact_id*."""
        self._conn.execute(
            "UPDATE artifacts SET is_canonical = 0 WHERE artifact_id = ?",
            (artifact_id,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Artifact edges
    # ------------------------------------------------------------------

    def add_edge(
        self, parent_artifact_id: str, child_artifact_id: str, relation: str
    ) -> None:
        """Record a lineage edge between two artifacts."""
        if relation not in VALID_RELATIONS:
            raise ValueError(
                f"Invalid relation: {relation!r}. Must be one of {sorted(VALID_RELATIONS)}"
            )
        self._conn.execute(
            """
            INSERT OR IGNORE INTO artifact_edges
                (parent_artifact_id, child_artifact_id, relation)
            VALUES (?, ?, ?)
            """,
            (parent_artifact_id, child_artifact_id, relation),
        )
        self._conn.commit()

    def get_edges_from(self, artifact_id: str) -> list[sqlite3.Row]:
        """Return edges where *artifact_id* is the parent."""
        return self._conn.execute(
            "SELECT * FROM artifact_edges WHERE parent_artifact_id = ?",
            (artifact_id,),
        ).fetchall()

    def get_edges_to(self, artifact_id: str) -> list[sqlite3.Row]:
        """Return edges where *artifact_id* is the child."""
        return self._conn.execute(
            "SELECT * FROM artifact_edges WHERE child_artifact_id = ?",
            (artifact_id,),
        ).fetchall()

    def get_lineage(self, artifact_id: str) -> list[str]:
        """Return transitive parent chain (BFS up the ``parent_artifact_id`` edges)."""
        visited: set[str] = set()
        queue = [artifact_id]
        lineage: list[str] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if current != artifact_id:
                lineage.append(current)
            rows = self._conn.execute(
                "SELECT parent_artifact_id FROM artifact_edges WHERE child_artifact_id = ?",
                (current,),
            ).fetchall()
            for row in rows:
                if row[0] not in visited:
                    queue.append(row[0])
        return lineage
