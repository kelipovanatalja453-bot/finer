"""Asset index and FTS5 search — rebuildable frontend projection."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AssetIndexService:
    """Manages the ``asset_index`` derived table and ``asset_index_fts`` FTS5
    virtual table for frontend asset browsing and search."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Asset CRUD
    # ------------------------------------------------------------------

    def upsert_asset(
        self,
        asset_id: str,
        content_id: str,
        stage: str,
        display_name: str,
        *,
        subtitle: Optional[str] = None,
        source_platform: Optional[str] = None,
        source_type: Optional[str] = None,
        content_type: Optional[str] = None,
        source_group_id: Optional[str] = None,
        latest_artifact_id: Optional[str] = None,
        manifest_id: Optional[str] = None,
        status: str = "ready",
        sort_key: Optional[str] = None,
        metadata_json: Optional[str] = None,
    ) -> None:
        """Insert or update an asset index row.

        Also updates the FTS content table implicitly (FTS mirrors
        ``asset_index`` via ``content='asset_index'``).
        """
        now = _utc_now()
        search_text = self._compose_search_text(
            display_name, subtitle, source_platform, content_type
        )

        self._conn.execute(
            """
            INSERT INTO asset_index (
                asset_id, content_id, stage, display_name, subtitle,
                source_platform, source_type, content_type, source_group_id,
                latest_artifact_id, manifest_id, status, sort_key,
                updated_at, search_text, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                content_id = excluded.content_id,
                stage = excluded.stage,
                display_name = excluded.display_name,
                subtitle = excluded.subtitle,
                source_platform = excluded.source_platform,
                source_type = excluded.source_type,
                content_type = excluded.content_type,
                source_group_id = excluded.source_group_id,
                latest_artifact_id = excluded.latest_artifact_id,
                manifest_id = excluded.manifest_id,
                status = excluded.status,
                sort_key = excluded.sort_key,
                updated_at = excluded.updated_at,
                search_text = excluded.search_text,
                metadata_json = excluded.metadata_json
            """,
            (
                asset_id, content_id, stage, display_name, subtitle,
                source_platform, source_type, content_type, source_group_id,
                latest_artifact_id, manifest_id, status, sort_key,
                now, search_text, metadata_json,
            ),
        )
        self._conn.commit()

    def get_asset(self, asset_id: str) -> Optional[dict[str, Any]]:
        """Return an asset_index row by asset_id, or None."""
        cur = self._conn.execute(
            "SELECT * FROM asset_index WHERE asset_id = ?",
            (asset_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_assets(
        self,
        stage: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict[str, Any]]:
        """List assets for a stage, optionally filtered by status."""
        order = "DESC" if sort_desc else "ASC"
        if status is not None:
            cur = self._conn.execute(
                f"SELECT * FROM asset_index "
                f"WHERE stage = ? AND status = ? "
                f"ORDER BY sort_key {order} LIMIT ? OFFSET ?",
                (stage, status, limit, offset),
            )
        else:
            cur = self._conn.execute(
                f"SELECT * FROM asset_index "
                f"WHERE stage = ? "
                f"ORDER BY sort_key {order} LIMIT ? OFFSET ?",
                (stage, limit, offset),
            )
        return [dict(r) for r in cur.fetchall()]

    def count_assets(
        self,
        stage: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """Count assets, optionally filtered by stage and/or status."""
        clauses: list[str] = []
        params: list[Any] = []
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        row = self._conn.execute(
            f"SELECT COUNT(*) FROM asset_index{where}", params
        ).fetchone()
        return row[0] if row else 0

    def delete_asset(self, asset_id: str) -> None:
        """Remove an asset from asset_index. FTS5 content= table auto-syncs."""
        self._conn.execute(
            "DELETE FROM asset_index WHERE asset_id = ?", (asset_id,)
        )
        self._conn.commit()

    def delete_assets_for_content(self, content_id: str) -> None:
        """Remove all assets for a content item. FTS5 content= table auto-syncs."""
        self._conn.execute(
            "DELETE FROM asset_index WHERE content_id = ?", (content_id,)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Rebuild
    # ------------------------------------------------------------------

    def rebuild_asset_index(self) -> int:
        """Truncate and rebuild ``asset_index`` from authoritative tables.

        Returns the number of asset rows inserted.
        """
        now = _utc_now()

        # Truncate
        self._conn.execute("DELETE FROM asset_index")
        self._conn.commit()

        # Rebuild from contents JOIN stage_status, with left joins to
        # artifacts, name_bindings, and source_records.
        #
        # Each content-stage combination with ready or partial status
        # gets an asset row.
        rows = self._conn.execute(
            """
            SELECT
                c.content_id,
                ss.stage,
                ss.status,
                ss.latest_artifact_id,
                c.content_type,
                c.canonical_title,
                c.frontend_display_name,
                c.primary_source_record_id,
                c.updated_at,
                c.latest_manifest_id AS content_manifest_id,
                sr.source_platform,
                sr.source_group_id,
                sg.source_type
            FROM contents c
            JOIN stage_status ss ON ss.content_id = c.content_id
            LEFT JOIN source_records sr
                ON sr.source_record_id = c.primary_source_record_id
            LEFT JOIN source_groups sg
                ON sg.source_group_id = sr.source_group_id
            WHERE ss.status IN ('ready', 'partial')
            """
        ).fetchall()

        count = 0
        for row in rows:
            content_id = row["content_id"]
            stage = row["stage"]
            asset_id = f"{stage}:{content_id}"

            # Display name: primary name_binding → canonical_title → frontend_display_name
            display_name = self._resolve_display_name(content_id, stage)
            if not display_name:
                display_name = (
                    row["canonical_title"]
                    or row["frontend_display_name"]
                    or content_id
                )

            source_platform = row["source_platform"]
            content_type = row["content_type"]
            search_text = self._compose_search_text(
                display_name, None, source_platform, content_type
            )

            self._conn.execute(
                """
                INSERT OR REPLACE INTO asset_index (
                    asset_id, content_id, stage, display_name, subtitle,
                    source_platform, source_type, content_type, source_group_id,
                    latest_artifact_id, manifest_id, status, sort_key,
                    updated_at, search_text, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    asset_id,
                    content_id,
                    stage,
                    display_name,
                    None,  # subtitle
                    source_platform,
                    row["source_type"],
                    content_type,
                    row["source_group_id"],
                    row["latest_artifact_id"],
                    row["content_manifest_id"],
                    row["status"],
                    row["updated_at"],
                    now,
                    search_text,
                ),
            )
            count += 1

        self._conn.commit()
        return count

    def rebuild_fts(self) -> None:
        """Drop and recreate ``asset_index_fts`` from ``asset_index``."""
        # Drop existing FTS table
        try:
            self._conn.execute("DROP TABLE IF EXISTS asset_index_fts")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass

        # Create FTS5 virtual table
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE asset_index_fts USING fts5(
                asset_id UNINDEXED,
                display_name,
                subtitle,
                search_text,
                content='asset_index',
                content_rowid='rowid'
            )
            """
        )
        self._conn.commit()

        # Populate from asset_index — FTS5 content tables auto-sync on
        # INSERT/UPDATE/DELETE, but we do an explicit rebuild by
        # reinserting the content. For content= tables, FTS5 reads from
        # the content table on rebuild.
        # The rebuild command tells FTS5 to re-read the content table:
        self._conn.execute(
            "INSERT INTO asset_index_fts(asset_index_fts) VALUES('rebuild')"
        )
        self._conn.commit()

    def rebuild_all(self) -> int:
        """Rebuild both ``asset_index`` and ``asset_index_fts``.

        Returns the number of asset rows inserted.
        """
        count = self.rebuild_asset_index()
        self.rebuild_fts()
        return count

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        stage: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search assets using FTS5.

        Returns matching asset_index rows ordered by FTS5 relevance.
        """
        if stage is not None:
            cur = self._conn.execute(
                """
                SELECT ai.*
                FROM asset_index_fts fts
                JOIN asset_index ai ON ai.rowid = fts.rowid
                WHERE fts.asset_index_fts MATCH ? AND ai.stage = ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, stage, limit),
            )
        else:
            cur = self._conn.execute(
                """
                SELECT ai.*
                FROM asset_index_fts fts
                JOIN asset_index ai ON ai.rowid = fts.rowid
                WHERE fts.asset_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_display_name(
        self, content_id: str, stage: str
    ) -> Optional[str]:
        """Resolve display name: stage primary → global primary → None."""
        # Try stage-specific primary name first
        row = self._conn.execute(
            """
            SELECT display_value FROM name_bindings
            WHERE subject_type = 'content' AND subject_id = ?
              AND stage = ? AND is_primary = 1 AND valid_to IS NULL
            LIMIT 1
            """,
            (content_id, stage),
        ).fetchone()
        if row:
            return row["display_value"]

        # Fallback to global primary (stage IS NULL)
        row = self._conn.execute(
            """
            SELECT display_value FROM name_bindings
            WHERE subject_type = 'content' AND subject_id = ?
              AND stage IS NULL AND is_primary = 1 AND valid_to IS NULL
            LIMIT 1
            """,
            (content_id,),
        ).fetchone()
        return row["display_value"] if row else None

    @staticmethod
    def _compose_search_text(
        display_name: Optional[str],
        subtitle: Optional[str],
        source_platform: Optional[str],
        content_type: Optional[str],
    ) -> str:
        """Compose space-separated search text for FTS5 indexing."""
        parts = [p for p in (display_name, subtitle, source_platform, content_type) if p]
        return " ".join(parts)

