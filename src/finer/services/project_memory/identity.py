"""Content identity service — long-lived content_id, versions, and source links."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deterministic_id(scheme: str, stable_key: str) -> str:
    """Deterministic content_id from identity scheme + stable key."""
    raw = f"{scheme}:{stable_key}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"cnt_{h}"


def _random_id() -> str:
    """Random content_id for local/manual uploads."""
    return f"cnt_{uuid.uuid4().hex[:16]}"


def _random_version_id() -> str:
    return f"cv_{uuid.uuid4().hex[:16]}"


class ContentIdentityService:
    """Manages content_id, content versions, source-content links, and the
    contents projection table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Content Identity CRUD
    # ------------------------------------------------------------------

    def create_content_id(
        self,
        identity_scheme: str,
        stable_key: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create or return an existing content identity.

        Returns the content_id (deterministic from scheme+stable_key).
        """
        content_id = _deterministic_id(identity_scheme, stable_key)
        now = _utc_now()
        metadata_json = json.dumps(metadata) if metadata else None

        try:
            self._conn.execute(
                "INSERT INTO content_identities "
                "(content_id, identity_scheme, stable_key, created_at, metadata_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (content_id, identity_scheme, stable_key, now, metadata_json),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            # Already exists — that's fine for a deterministic ID
            pass

        return content_id

    def create_content_id_random(
        self,
        identity_scheme: str = "local",
        stable_key: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a random content_id for local/manual uploads.

        stable_key defaults to the random id itself.
        """
        content_id = _random_id()
        if stable_key is None:
            stable_key = content_id
        now = _utc_now()
        metadata_json = json.dumps(metadata) if metadata else None

        self._conn.execute(
            "INSERT INTO content_identities "
            "(content_id, identity_scheme, stable_key, created_at, metadata_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (content_id, identity_scheme, stable_key, now, metadata_json),
        )
        self._conn.commit()
        return content_id

    def get_content_id(
        self, identity_scheme: str, stable_key: str
    ) -> Optional[sqlite3.Row]:
        """Look up a content identity by scheme + stable key."""
        cur = self._conn.execute(
            "SELECT * FROM content_identities "
            "WHERE identity_scheme = ? AND stable_key = ?",
            (identity_scheme, stable_key),
        )
        cur.row_factory = sqlite3.Row
        return cur.fetchone()

    def retire_content_id(self, content_id: str) -> None:
        """Mark a content identity as retired."""
        self._conn.execute(
            "UPDATE content_identities SET retired_at = ? WHERE content_id = ?",
            (_utc_now(), content_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Content Version CRUD
    # ------------------------------------------------------------------

    def create_version(
        self,
        content_id: str,
        content_hash: Optional[str] = None,
        manifest_id: Optional[str] = None,
        change_reason: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a new version for a content item.

        Returns the content_version_id.
        """
        # Compute next version number
        row = self._conn.execute(
            "SELECT COALESCE(MAX(version_no), 0) FROM content_versions "
            "WHERE content_id = ?",
            (content_id,),
        ).fetchone()
        next_no = row[0] + 1

        version_id = _random_version_id()
        now = _utc_now()
        metadata_json = json.dumps(metadata) if metadata else None

        self._conn.execute(
            "INSERT INTO content_versions "
            "(content_version_id, content_id, content_hash, manifest_id, "
            " version_no, created_at, change_reason, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (version_id, content_id, content_hash, manifest_id,
             next_no, now, change_reason, metadata_json),
        )
        self._conn.commit()
        return version_id

    def get_versions(self, content_id: str) -> list[sqlite3.Row]:
        """Return all versions for a content item, ordered by version_no."""
        cur = self._conn.execute(
            "SELECT * FROM content_versions WHERE content_id = ? "
            "ORDER BY version_no ASC",
            (content_id,),
        )
        cur.row_factory = sqlite3.Row
        return cur.fetchall()

    def get_latest_version(self, content_id: str) -> Optional[sqlite3.Row]:
        """Return the latest version for a content item."""
        cur = self._conn.execute(
            "SELECT * FROM content_versions WHERE content_id = ? "
            "ORDER BY version_no DESC LIMIT 1",
            (content_id,),
        )
        cur.row_factory = sqlite3.Row
        return cur.fetchone()

    # ------------------------------------------------------------------
    # Source-Content Links
    # ------------------------------------------------------------------

    def link_source_to_content(
        self,
        source_record_id: str,
        content_id: str,
        link_reason: str,
        confidence: float = 1.0,
    ) -> None:
        """Link a source record to a content identity."""
        self._conn.execute(
            "INSERT OR REPLACE INTO source_content_links "
            "(source_record_id, content_id, link_reason, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_record_id, content_id, link_reason, confidence, _utc_now()),
        )
        self._conn.commit()

    def get_content_for_source(self, source_record_id: str) -> list[str]:
        """Return content_ids linked to a source record."""
        cur = self._conn.execute(
            "SELECT content_id FROM source_content_links "
            "WHERE source_record_id = ?",
            (source_record_id,),
        )
        return [row[0] for row in cur.fetchall()]

    def get_sources_for_content(self, content_id: str) -> list[str]:
        """Return source_record_ids linked to a content item."""
        cur = self._conn.execute(
            "SELECT source_record_id FROM source_content_links "
            "WHERE content_id = ?",
            (content_id,),
        )
        return [row[0] for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Content Row (current-state projection)
    # ------------------------------------------------------------------

    def upsert_content(self, content_id: str, **fields: Any) -> None:
        """Upsert into the contents table.

        On INSERT, created_at and updated_at are set to now, status defaults
        to 'active', current_stage defaults to 'F0'.
        On UPDATE, only the provided fields and updated_at are changed.
        """
        now = _utc_now()

        existing = self._conn.execute(
            "SELECT content_id FROM contents WHERE content_id = ?",
            (content_id,),
        ).fetchone()

        if existing is None:
            # Insert
            fields.setdefault("created_at", now)
            fields.setdefault("updated_at", now)
            fields.setdefault("status", "active")
            fields.setdefault("current_stage", "F0")
            cols = ["content_id"] + list(fields.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            values = [content_id] + list(fields.values())
            self._conn.execute(
                f"INSERT INTO contents ({col_names}) VALUES ({placeholders})",
                values,
            )
        else:
            # Update
            fields["updated_at"] = now
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [content_id]
            self._conn.execute(
                f"UPDATE contents SET {set_clause} WHERE content_id = ?",
                values,
            )

        self._conn.commit()

    def get_content(self, content_id: str) -> Optional[sqlite3.Row]:
        """Return the contents row for a content item."""
        cur = self._conn.execute(
            "SELECT * FROM contents WHERE content_id = ?",
            (content_id,),
        )
        cur.row_factory = sqlite3.Row
        return cur.fetchone()

    def list_contents_by_stage(
        self,
        stage: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """List contents by current stage, optionally filtered by status."""
        if status is not None:
            cur = self._conn.execute(
                "SELECT * FROM contents "
                "WHERE current_stage = ? AND status = ? "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (stage, status, limit, offset),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM contents "
                "WHERE current_stage = ? "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (stage, limit, offset),
            )
        cur.row_factory = sqlite3.Row
        return cur.fetchall()

    def update_current_stage(self, content_id: str, stage: str) -> None:
        """Update the current stage for a content item."""
        self._conn.execute(
            "UPDATE contents SET current_stage = ?, updated_at = ? "
            "WHERE content_id = ?",
            (stage, _utc_now(), content_id),
        )
        self._conn.commit()
