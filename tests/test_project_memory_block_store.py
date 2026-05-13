"""Tests for BlockStore — F1 block and F1.5 topic storage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from finer.services.project_memory.block_store import BlockStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "src" / "finer" / "services" / "project_memory" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """In-memory SQLite connection with the full schema applied."""
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row

    # Apply migration files in order
    for sql_file in sorted(_SCHEMA_DIR.glob("*.sql")):
        c.executescript(sql_file.read_text())

    # Seed prerequisite rows so FK constraints pass
    c.execute(
        "INSERT INTO content_identities "
        "(content_id, identity_scheme, stable_key, created_at) "
        "VALUES ('cnt_test', 'local', 'test_key', '2026-01-01T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO content_versions "
        "(content_version_id, content_id, version_no, created_at) "
        "VALUES ('cv_test', 'cnt_test', 1, '2026-01-01T00:00:00Z')"
    )
    c.execute(
        "INSERT INTO storage_objects "
        "(object_id, sha256, storage_uri, byte_size, created_at) "
        "VALUES ('obj_test', 'abc123', '/tmp/test', 100, '2026-01-01T00:00:00Z')"
    )
    c.commit()

    yield c
    c.close()


@pytest.fixture()
def store(conn: sqlite3.Connection) -> BlockStore:
    return BlockStore(conn)


# ---------------------------------------------------------------------------
# Content Block CRUD
# ---------------------------------------------------------------------------


class TestCreateBlock:
    def test_returns_block_id(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        assert bid.startswith("blk_")

    def test_persists_all_fields(self, store: BlockStore) -> None:
        bid = store.create_block(
            "cnt_test", "heading", 3,
            content_version_id="cv_test",
            artifact_id=None,
            text_object_id="obj_test",
            text_excerpt="Hello world",
            start_offset=10,
            end_offset=20,
            parent_block_id=None,
            metadata={"lang": "en"},
        )
        row = store.get_block(bid)
        assert row is not None
        assert row["block_id"] == bid
        assert row["content_id"] == "cnt_test"
        assert row["content_version_id"] == "cv_test"
        assert row["stage"] == "F1"
        assert row["block_type"] == "heading"
        assert row["order_index"] == 3
        assert row["text_object_id"] == "obj_test"
        assert row["text_excerpt"] == "Hello world"
        assert row["start_offset"] == 10
        assert row["end_offset"] == 20
        assert json.loads(row["metadata_json"]) == {"lang": "en"}


class TestGetBlock:
    def test_returns_none_for_missing(self, store: BlockStore) -> None:
        assert store.get_block("blk_nonexistent") is None


class TestListBlocks:
    def test_returns_ordered_asc(self, store: BlockStore) -> None:
        store.create_block("cnt_test", "text", 2)
        store.create_block("cnt_test", "text", 0)
        store.create_block("cnt_test", "text", 1)
        blocks = store.list_blocks("cnt_test", stage="F1", order_asc=True)
        assert [b["order_index"] for b in blocks] == [0, 1, 2]

    def test_returns_ordered_desc(self, store: BlockStore) -> None:
        store.create_block("cnt_test", "text", 0)
        store.create_block("cnt_test", "text", 1)
        store.create_block("cnt_test", "text", 2)
        blocks = store.list_blocks("cnt_test", stage="F1", order_asc=False)
        assert [b["order_index"] for b in blocks] == [2, 1, 0]

    def test_filters_by_stage(self, store: BlockStore) -> None:
        store.create_block("cnt_test", "text", 0)
        # Manually insert a non-F1 block
        store._conn.execute(
            "INSERT INTO content_blocks "
            "(block_id, content_id, stage, block_type, order_index, created_at) "
            "VALUES ('blk_other', 'cnt_test', 'F2', 'text', 0, '2026-01-01T00:00:00Z')"
        )
        store._conn.commit()
        f1_blocks = store.list_blocks("cnt_test", stage="F1")
        assert len(f1_blocks) == 1


class TestListBlocksForVersion:
    def test_filters_by_version(self, store: BlockStore) -> None:
        store.create_block("cnt_test", "text", 0, content_version_id="cv_test")
        store.create_block("cnt_test", "text", 1, content_version_id=None)
        blocks = store.list_blocks_for_version("cv_test")
        assert len(blocks) == 1
        assert blocks[0]["content_version_id"] == "cv_test"


class TestUpdateBlock:
    def test_updates_mutable_fields(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0, text_excerpt="old")
        store.update_block(bid, text_excerpt="new", order_index=5)
        row = store.get_block(bid)
        assert row["text_excerpt"] == "new"
        assert row["order_index"] == 5

    def test_noop_on_empty_fields(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        store.update_block(bid)  # should not raise
        assert store.get_block(bid) is not None


class TestDeleteBlock:
    def test_removes_block(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        store.delete_block(bid)
        assert store.get_block(bid) is None

    def test_removes_topic_memberships(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        tid = store.create_topic_block("cnt_test", "Topic", "single_topic")
        store.add_member(tid, bid, 0)
        store.delete_block(bid)
        assert store.get_members(tid) == []


class TestBulkCreateBlocks:
    def test_returns_ids_in_order(self, store: BlockStore) -> None:
        blocks = [
            {"block_type": "text", "order_index": 0},
            {"block_type": "heading", "order_index": 1},
            {"block_type": "list", "order_index": 2},
        ]
        ids = store.bulk_create_blocks("cnt_test", blocks)
        assert len(ids) == 3
        for bid in ids:
            assert bid.startswith("blk_")

    def test_persists_all_blocks(self, store: BlockStore) -> None:
        blocks = [
            {
                "block_type": "text",
                "order_index": i,
                "text_excerpt": f"block {i}",
                "metadata": {"idx": i},
            }
            for i in range(5)
        ]
        store.bulk_create_blocks(
            "cnt_test", blocks,
            content_version_id="cv_test",
            artifact_id=None,
        )
        stored = store.list_blocks("cnt_test")
        assert len(stored) == 5
        assert stored[0]["content_version_id"] == "cv_test"


# ---------------------------------------------------------------------------
# Topic Block CRUD
# ---------------------------------------------------------------------------


class TestCreateTopicBlock:
    def test_returns_topic_block_id(self, store: BlockStore) -> None:
        tid = store.create_topic_block("cnt_test", "Market Outlook", "single_topic")
        assert tid.startswith("top_")

    def test_persists_fields(self, store: BlockStore) -> None:
        tid = store.create_topic_block(
            "cnt_test", "Earnings", "multi_topic",
            source_artifact_id=None,
            start_block_index=2,
            end_block_index=5,
            metadata={"priority": "high"},
        )
        row = store.get_topic_block(tid)
        assert row is not None
        assert row["topic_title"] == "Earnings"
        assert row["topic_type"] == "multi_topic"
        assert row["start_block_index"] == 2
        assert row["end_block_index"] == 5
        assert json.loads(row["metadata_json"]) == {"priority": "high"}


class TestGetTopicBlock:
    def test_returns_none_for_missing(self, store: BlockStore) -> None:
        assert store.get_topic_block("top_nonexistent") is None


class TestListTopicBlocks:
    def test_returns_topics_for_content(self, store: BlockStore) -> None:
        store.create_topic_block("cnt_test", "A", "single_topic")
        store.create_topic_block("cnt_test", "B", "multi_topic")
        topics = store.list_topic_blocks("cnt_test")
        assert len(topics) == 2
        titles = {t["topic_title"] for t in topics}
        assert titles == {"A", "B"}


class TestDeleteTopicBlock:
    def test_removes_topic_and_members(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        tid = store.create_topic_block("cnt_test", "T", "single_topic")
        store.add_member(tid, bid, 0)
        store.delete_topic_block(tid)
        assert store.get_topic_block(tid) is None
        # Block itself should still exist
        assert store.get_block(bid) is not None


# ---------------------------------------------------------------------------
# Topic Block Members
# ---------------------------------------------------------------------------


class TestAddMember:
    def test_adds_member(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        tid = store.create_topic_block("cnt_test", "T", "single_topic")
        store.add_member(tid, bid, 0)
        members = store.get_members(tid)
        assert len(members) == 1
        assert members[0]["block_id"] == bid


class TestRemoveMember:
    def test_removes_member(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        tid = store.create_topic_block("cnt_test", "T", "single_topic")
        store.add_member(tid, bid, 0)
        store.remove_member(tid, bid)
        assert store.get_members(tid) == []


class TestGetMembers:
    def test_returns_ordered_blocks(self, store: BlockStore) -> None:
        b0 = store.create_block("cnt_test", "text", 0)
        b1 = store.create_block("cnt_test", "text", 1)
        b2 = store.create_block("cnt_test", "text", 2)
        tid = store.create_topic_block("cnt_test", "T", "single_topic")
        store.add_member(tid, b2, 2)
        store.add_member(tid, b0, 0)
        store.add_member(tid, b1, 1)
        members = store.get_members(tid)
        assert [m["block_id"] for m in members] == [b0, b1, b2]


class TestSetMembers:
    def test_replaces_all_members(self, store: BlockStore) -> None:
        b0 = store.create_block("cnt_test", "text", 0)
        b1 = store.create_block("cnt_test", "text", 1)
        b2 = store.create_block("cnt_test", "text", 2)
        tid = store.create_topic_block("cnt_test", "T", "single_topic")
        store.add_member(tid, b0, 0)
        store.set_members(tid, [b1, b2])
        members = store.get_members(tid)
        assert len(members) == 2
        assert [m["block_id"] for m in members] == [b1, b2]

    def test_empty_list_clears_members(self, store: BlockStore) -> None:
        bid = store.create_block("cnt_test", "text", 0)
        tid = store.create_topic_block("cnt_test", "T", "single_topic")
        store.add_member(tid, bid, 0)
        store.set_members(tid, [])
        assert store.get_members(tid) == []


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestGetBlocksWithoutTopic:
    def test_returns_unassigned_blocks(self, store: BlockStore) -> None:
        b0 = store.create_block("cnt_test", "text", 0)
        b1 = store.create_block("cnt_test", "text", 1)
        b2 = store.create_block("cnt_test", "text", 2)
        tid = store.create_topic_block("cnt_test", "T", "single_topic")
        store.add_member(tid, b0, 0)
        store.add_member(tid, b1, 1)

        orphan = store.get_blocks_without_topic("cnt_test")
        assert len(orphan) == 1
        assert orphan[0]["block_id"] == b2

    def test_returns_all_when_no_topics(self, store: BlockStore) -> None:
        store.create_block("cnt_test", "text", 0)
        store.create_block("cnt_test", "text", 1)
        orphan = store.get_blocks_without_topic("cnt_test")
        assert len(orphan) == 2


class TestCountBlocks:
    def test_counts_all_stages(self, store: BlockStore) -> None:
        store.create_block("cnt_test", "text", 0)
        store.create_block("cnt_test", "text", 1)
        assert store.count_blocks("cnt_test") == 2

    def test_counts_filtered_stage(self, store: BlockStore) -> None:
        store.create_block("cnt_test", "text", 0)
        store._conn.execute(
            "INSERT INTO content_blocks "
            "(block_id, content_id, stage, block_type, order_index, created_at) "
            "VALUES ('blk_x', 'cnt_test', 'F2', 'text', 0, '2026-01-01T00:00:00Z')"
        )
        store._conn.commit()
        assert store.count_blocks("cnt_test", stage="F1") == 1
        assert store.count_blocks("cnt_test", stage="F2") == 1


class TestCountTopicBlocks:
    def test_counts_topics(self, store: BlockStore) -> None:
        store.create_topic_block("cnt_test", "A", "single_topic")
        store.create_topic_block("cnt_test", "B", "multi_topic")
        assert store.count_topic_blocks("cnt_test") == 2

    def test_zero_when_none(self, store: BlockStore) -> None:
        assert store.count_topic_blocks("cnt_test") == 0
