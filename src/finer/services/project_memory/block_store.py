"""F1 block and F1.5 topic storage service for Project Memory."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _block_id() -> str:
    return f"blk_{uuid.uuid4().hex}"


def _topic_block_id() -> str:
    return f"top_{uuid.uuid4().hex}"


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


class BlockStore:
    """F1 content block and F1.5 topic block CRUD with member management."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Content Block CRUD (F1)
    # ------------------------------------------------------------------

    def create_block(
        self,
        content_id: str,
        block_type: str,
        order_index: int,
        content_version_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
        text_object_id: Optional[str] = None,
        text_excerpt: Optional[str] = None,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
        parent_block_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a content block. Returns block_id."""
        block_id = _block_id()
        now = _utc_now()
        metadata_json = json.dumps(metadata) if metadata else None

        self._conn.execute(
            "INSERT INTO content_blocks "
            "(block_id, content_id, content_version_id, artifact_id, stage, "
            " block_type, order_index, parent_block_id, text_object_id, "
            " text_excerpt, start_offset, end_offset, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, 'F1', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                block_id, content_id, content_version_id, artifact_id,
                block_type, order_index, parent_block_id, text_object_id,
                text_excerpt, start_offset, end_offset, metadata_json, now,
            ),
        )
        self._conn.commit()
        return block_id

    def get_block(self, block_id: str) -> Optional[dict[str, Any]]:
        """Return a content_blocks row by block_id."""
        cur = self._conn.execute(
            "SELECT * FROM content_blocks WHERE block_id = ?",
            (block_id,),
        )
        cur.row_factory = sqlite3.Row
        return _row_to_dict(cur.fetchone())

    def list_blocks(
        self,
        content_id: str,
        stage: str = "F1",
        order_asc: bool = True,
    ) -> list[dict[str, Any]]:
        """Return ordered blocks for a content item."""
        direction = "ASC" if order_asc else "DESC"
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"Invalid sort direction: {direction}")
        cur = self._conn.execute(
            "SELECT * FROM content_blocks "
            "WHERE content_id = ? AND stage = ? "
            f"ORDER BY order_index {direction}",
            (content_id, stage),
        )
        cur.row_factory = sqlite3.Row
        return _rows_to_list(cur.fetchall())

    def list_blocks_for_version(
        self, content_version_id: str
    ) -> list[dict[str, Any]]:
        """Return ordered blocks for a specific content version."""
        cur = self._conn.execute(
            "SELECT * FROM content_blocks "
            "WHERE content_version_id = ? "
            "ORDER BY order_index ASC",
            (content_version_id,),
        )
        cur.row_factory = sqlite3.Row
        return _rows_to_list(cur.fetchall())

    def update_block(self, block_id: str, **fields: Any) -> None:
        """Update mutable fields on a content block."""
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [block_id]
        self._conn.execute(
            f"UPDATE content_blocks SET {set_clause} WHERE block_id = ?",
            values,
        )
        self._conn.commit()

    def delete_block(self, block_id: str) -> None:
        """Delete a block and its topic memberships."""
        self._conn.execute(
            "DELETE FROM topic_block_members WHERE block_id = ?",
            (block_id,),
        )
        self._conn.execute(
            "DELETE FROM content_blocks WHERE block_id = ?",
            (block_id,),
        )
        self._conn.commit()

    def bulk_create_blocks(
        self,
        content_id: str,
        blocks: list[dict[str, Any]],
        content_version_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
    ) -> list[str]:
        """Batch insert multiple blocks. Returns list of block_ids.

        Each dict in *blocks* may contain: block_type, order_index,
        text_object_id, text_excerpt, start_offset, end_offset,
        parent_block_id, metadata.
        """
        now = _utc_now()
        block_ids: list[str] = []
        rows: list[tuple[Any, ...]] = []

        for b in blocks:
            bid = _block_id()
            block_ids.append(bid)
            metadata = b.get("metadata")
            rows.append(
                (
                    bid, content_id, content_version_id, artifact_id, "F1",
                    b["block_type"], b["order_index"],
                    b.get("parent_block_id"),
                    b.get("text_object_id"), b.get("text_excerpt"),
                    b.get("start_offset"), b.get("end_offset"),
                    json.dumps(metadata) if metadata else None,
                    now,
                )
            )

        self._conn.executemany(
            "INSERT INTO content_blocks "
            "(block_id, content_id, content_version_id, artifact_id, stage, "
            " block_type, order_index, parent_block_id, text_object_id, "
            " text_excerpt, start_offset, end_offset, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()
        return block_ids

    # ------------------------------------------------------------------
    # Topic Block CRUD (F1.5)
    # ------------------------------------------------------------------

    def create_topic_block(
        self,
        content_id: str,
        topic_title: str,
        topic_type: str,
        source_artifact_id: Optional[str] = None,
        start_block_index: Optional[int] = None,
        end_block_index: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a topic block. Returns topic_block_id."""
        tid = _topic_block_id()
        now = _utc_now()
        metadata_json = json.dumps(metadata) if metadata else None

        self._conn.execute(
            "INSERT INTO topic_blocks "
            "(topic_block_id, content_id, source_artifact_id, topic_title, "
            " topic_type, start_block_index, end_block_index, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tid, content_id, source_artifact_id, topic_title,
             topic_type, start_block_index, end_block_index, metadata_json, now),
        )
        self._conn.commit()
        return tid

    def get_topic_block(self, topic_block_id: str) -> Optional[dict[str, Any]]:
        """Return a topic_blocks row by topic_block_id."""
        cur = self._conn.execute(
            "SELECT * FROM topic_blocks WHERE topic_block_id = ?",
            (topic_block_id,),
        )
        cur.row_factory = sqlite3.Row
        return _row_to_dict(cur.fetchone())

    def list_topic_blocks(self, content_id: str) -> list[dict[str, Any]]:
        """Return topic blocks for a content item, ordered by creation."""
        cur = self._conn.execute(
            "SELECT * FROM topic_blocks "
            "WHERE content_id = ? "
            "ORDER BY created_at DESC",
            (content_id,),
        )
        cur.row_factory = sqlite3.Row
        return _rows_to_list(cur.fetchall())

    def delete_topic_block(self, topic_block_id: str) -> None:
        """Delete a topic block and its member links."""
        self._conn.execute(
            "DELETE FROM topic_block_members WHERE topic_block_id = ?",
            (topic_block_id,),
        )
        self._conn.execute(
            "DELETE FROM topic_blocks WHERE topic_block_id = ?",
            (topic_block_id,),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Topic Block Members
    # ------------------------------------------------------------------

    def add_member(
        self, topic_block_id: str, block_id: str, order_index: int
    ) -> None:
        """Add a block as a member of a topic block."""
        self._conn.execute(
            "INSERT OR REPLACE INTO topic_block_members "
            "(topic_block_id, block_id, order_index) VALUES (?, ?, ?)",
            (topic_block_id, block_id, order_index),
        )
        self._conn.commit()

    def remove_member(self, topic_block_id: str, block_id: str) -> None:
        """Remove a block from a topic block."""
        self._conn.execute(
            "DELETE FROM topic_block_members "
            "WHERE topic_block_id = ? AND block_id = ?",
            (topic_block_id, block_id),
        )
        self._conn.commit()

    def get_members(self, topic_block_id: str) -> list[dict[str, Any]]:
        """Return ordered list of blocks belonging to a topic block."""
        cur = self._conn.execute(
            "SELECT cb.* FROM content_blocks cb "
            "JOIN topic_block_members tbm ON cb.block_id = tbm.block_id "
            "WHERE tbm.topic_block_id = ? "
            "ORDER BY tbm.order_index ASC",
            (topic_block_id,),
        )
        cur.row_factory = sqlite3.Row
        return _rows_to_list(cur.fetchall())

    def set_members(
        self, topic_block_id: str, block_ids: list[str]
    ) -> None:
        """Replace all members of a topic block atomically."""
        self._conn.execute(
            "DELETE FROM topic_block_members WHERE topic_block_id = ?",
            (topic_block_id,),
        )
        rows = [(topic_block_id, bid, idx) for idx, bid in enumerate(block_ids)]
        self._conn.executemany(
            "INSERT INTO topic_block_members "
            "(topic_block_id, block_id, order_index) VALUES (?, ?, ?)",
            rows,
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_blocks_without_topic(self, content_id: str) -> list[dict[str, Any]]:
        """Return blocks that are not in any topic block."""
        cur = self._conn.execute(
            "SELECT cb.* FROM content_blocks cb "
            "WHERE cb.content_id = ? AND cb.stage = 'F1' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM topic_block_members tbm "
            "  WHERE tbm.block_id = cb.block_id"
            ") "
            "ORDER BY cb.order_index ASC",
            (content_id,),
        )
        cur.row_factory = sqlite3.Row
        return _rows_to_list(cur.fetchall())

    def count_blocks(
        self, content_id: str, stage: Optional[str] = None
    ) -> int:
        """Count blocks for a content item, optionally filtered by stage."""
        if stage is not None:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM content_blocks "
                "WHERE content_id = ? AND stage = ?",
                (content_id, stage),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM content_blocks WHERE content_id = ?",
                (content_id,),
            ).fetchone()
        return row[0] if row else 0

    def count_topic_blocks(self, content_id: str) -> int:
        """Count topic blocks for a content item."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM topic_blocks WHERE content_id = ?",
            (content_id,),
        ).fetchone()
        return row[0] if row else 0
