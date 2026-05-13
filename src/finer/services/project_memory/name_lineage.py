"""Name lineage service — structured name_bindings writes and queries."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_binding_id() -> str:
    return f"nb_{uuid.uuid4()}"


class NameLineageService:
    """Manages name_bindings rows for subject identity across F-stages."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ── Write operations ─────────────────────────────────────────────

    def bind_name(
        self,
        subject_type: str,
        subject_id: str,
        namespace: str,
        name_kind: str,
        display_value: str,
        normalized_value: Optional[str] = None,
        path_safe_value: Optional[str] = None,
        stage: Optional[str] = None,
        is_primary: bool = False,
    ) -> str:
        """Insert a new name binding. Returns name_binding_id."""
        binding_id = _new_binding_id()
        now = _now_iso()
        self._conn.execute(
            """
            INSERT INTO name_bindings
                (name_binding_id, subject_type, subject_id, stage,
                 namespace, name_kind, display_value,
                 normalized_value, path_safe_value,
                 is_primary, valid_from, valid_to)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                binding_id,
                subject_type,
                subject_id,
                stage,
                namespace,
                name_kind,
                display_value,
                normalized_value,
                path_safe_value,
                1 if is_primary else 0,
                now,
            ),
        )
        self._conn.commit()
        return binding_id

    def set_primary(
        self,
        subject_type: str,
        subject_id: str,
        namespace: str,
        name_kind: str,
        display_value: str,
        stage: Optional[str] = None,
    ) -> str:
        """Clear existing primary for same subject+namespace+stage, insert new primary.

        Returns the new name_binding_id.
        """
        now = _now_iso()

        # Close existing primary bindings for this subject+namespace+stage
        if stage is None:
            self._conn.execute(
                """
                UPDATE name_bindings
                SET valid_to = ?
                WHERE subject_type = ? AND subject_id = ?
                  AND namespace = ? AND name_kind = ?
                  AND stage IS NULL AND is_primary = 1
                  AND valid_to IS NULL
                """,
                (now, subject_type, subject_id, namespace, name_kind),
            )
        else:
            self._conn.execute(
                """
                UPDATE name_bindings
                SET valid_to = ?
                WHERE subject_type = ? AND subject_id = ?
                  AND namespace = ? AND name_kind = ?
                  AND stage = ? AND is_primary = 1
                  AND valid_to IS NULL
                """,
                (now, subject_type, subject_id, namespace, name_kind, stage),
            )

        return self.bind_name(
            subject_type=subject_type,
            subject_id=subject_id,
            namespace=namespace,
            name_kind=name_kind,
            display_value=display_value,
            stage=stage,
            is_primary=True,
        )

    def close_binding(self, name_binding_id: str) -> None:
        """Set valid_to to now for the given binding."""
        self._conn.execute(
            "UPDATE name_bindings SET valid_to = ? WHERE name_binding_id = ?",
            (_now_iso(), name_binding_id),
        )
        self._conn.commit()

    def rename(
        self,
        subject_type: str,
        subject_id: str,
        namespace: str,
        name_kind: str,
        new_display_value: str,
        stage: Optional[str] = None,
    ) -> str:
        """Close old primary, create new primary. Returns new name_binding_id."""
        return self.set_primary(
            subject_type=subject_type,
            subject_id=subject_id,
            namespace=namespace,
            name_kind=name_kind,
            display_value=new_display_value,
            stage=stage,
        )

    # ── Read operations ──────────────────────────────────────────────

    def get_names(
        self,
        subject_type: str,
        subject_id: str,
        namespace: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> list[dict]:
        """Return current (valid_to IS NULL) name bindings for a subject."""
        clauses = [
            "subject_type = ?",
            "subject_id = ?",
            "valid_to IS NULL",
        ]
        params: list[object] = [subject_type, subject_id]

        if namespace is not None:
            clauses.append("namespace = ?")
            params.append(namespace)
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)

        where = " AND ".join(clauses)
        rows = self._conn.execute(
            f"SELECT * FROM name_bindings WHERE {where} ORDER BY namespace, name_kind",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_primary_name(
        self,
        subject_type: str,
        subject_id: str,
        namespace: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> Optional[str]:
        """Return display_value of the current primary binding, or None."""
        clauses = [
            "subject_type = ?",
            "subject_id = ?",
            "is_primary = 1",
            "valid_to IS NULL",
        ]
        params: list[object] = [subject_type, subject_id]

        if namespace is not None:
            clauses.append("namespace = ?")
            params.append(namespace)
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)

        where = " AND ".join(clauses)
        row = self._conn.execute(
            f"SELECT display_value FROM name_bindings WHERE {where} LIMIT 1",
            params,
        ).fetchone()
        return row["display_value"] if row else None

    def get_name_history(
        self,
        subject_type: str,
        subject_id: str,
        namespace: str,
        name_kind: str,
    ) -> list[dict]:
        """Return all bindings (including closed) for a subject+namespace+kind, ordered by valid_from."""
        rows = self._conn.execute(
            """
            SELECT * FROM name_bindings
            WHERE subject_type = ? AND subject_id = ?
              AND namespace = ? AND name_kind = ?
            ORDER BY valid_from
            """,
            (subject_type, subject_id, namespace, name_kind),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_names_for_content(self, content_id: str) -> dict[str, list[dict]]:
        """Return all current name bindings for a content_id, grouped by namespace.kind."""
        rows = self._conn.execute(
            """
            SELECT * FROM name_bindings
            WHERE subject_id = ? AND valid_to IS NULL
            ORDER BY namespace, name_kind
            """,
            (content_id,),
        ).fetchall()

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            r = dict(row)
            key = f"{r['namespace']}.{r['name_kind']}"
            grouped.setdefault(key, []).append(r)
        return grouped

    def search_by_name(
        self,
        display_value: str,
        subject_type: Optional[str] = None,
    ) -> list[dict]:
        """Search current bindings by display_value (exact match)."""
        if subject_type is not None:
            rows = self._conn.execute(
                """
                SELECT * FROM name_bindings
                WHERE display_value = ? AND subject_type = ?
                  AND valid_to IS NULL
                """,
                (display_value, subject_type),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM name_bindings
                WHERE display_value = ? AND valid_to IS NULL
                """,
                (display_value,),
            ).fetchall()
        return [dict(r) for r in rows]
