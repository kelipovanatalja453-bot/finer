"""Tests for ContentIdentityService."""

from __future__ import annotations

import sqlite3
import unittest

from finer.services.project_memory.identity import ContentIdentityService


def _create_tables(conn: sqlite3.Connection) -> None:
    """Create the required tables in an in-memory database."""
    conn.executescript("""
        CREATE TABLE content_identities (
          content_id TEXT PRIMARY KEY,
          identity_scheme TEXT NOT NULL,
          stable_key TEXT NOT NULL,
          created_at TEXT NOT NULL,
          retired_at TEXT,
          metadata_json TEXT,
          UNIQUE(identity_scheme, stable_key)
        );

        CREATE TABLE content_versions (
          content_version_id TEXT PRIMARY KEY,
          content_id TEXT NOT NULL REFERENCES content_identities(content_id),
          content_hash TEXT,
          manifest_id TEXT,
          version_no INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          change_reason TEXT,
          metadata_json TEXT,
          UNIQUE(content_id, version_no)
        );

        CREATE TABLE source_content_links (
          source_record_id TEXT NOT NULL,
          content_id TEXT NOT NULL REFERENCES content_identities(content_id),
          link_reason TEXT NOT NULL,
          confidence REAL NOT NULL DEFAULT 1.0,
          created_at TEXT NOT NULL,
          PRIMARY KEY (source_record_id, content_id)
        );

        CREATE TABLE contents (
          content_id TEXT PRIMARY KEY REFERENCES content_identities(content_id),
          active_content_version_id TEXT,
          primary_source_record_id TEXT,
          content_type TEXT,
          current_stage TEXT NOT NULL,
          canonical_title TEXT,
          frontend_display_name TEXT,
          latest_manifest_id TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          status TEXT NOT NULL
        );

        CREATE INDEX idx_content_versions_content
          ON content_versions(content_id, version_no DESC);

        CREATE INDEX idx_source_content_links_content
          ON source_content_links(content_id);

        CREATE INDEX idx_contents_current_stage
          ON contents(current_stage, status, updated_at DESC);
    """)


class TestContentIdentityCRUD(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        _create_tables(self.conn)
        self.svc = ContentIdentityService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_create_and_get_content_id(self) -> None:
        cid = self.svc.create_content_id("feishu", "msg_123")
        self.assertTrue(cid.startswith("cnt_"))
        self.assertEqual(len(cid), 20)  # cnt_ + 16 hex chars

        row = self.svc.get_content_id("feishu", "msg_123")
        self.assertIsNotNone(row)
        self.assertEqual(row["content_id"], cid)
        self.assertEqual(row["identity_scheme"], "feishu")
        self.assertEqual(row["stable_key"], "msg_123")

    def test_deterministic_id_same_input(self) -> None:
        cid1 = self.svc.create_content_id("feishu", "msg_456")
        cid2 = self.svc.create_content_id("feishu", "msg_456")
        self.assertEqual(cid1, cid2)

    def test_different_inputs_different_ids(self) -> None:
        cid1 = self.svc.create_content_id("feishu", "msg_a")
        cid2 = self.svc.create_content_id("feishu", "msg_b")
        self.assertNotEqual(cid1, cid2)

    def test_different_schemes_different_ids(self) -> None:
        cid1 = self.svc.create_content_id("feishu", "msg_x")
        cid2 = self.svc.create_content_id("bilibili", "msg_x")
        self.assertNotEqual(cid1, cid2)

    def test_create_with_metadata(self) -> None:
        meta = {"source": "test", "priority": 1}
        cid = self.svc.create_content_id("local", "file_1", metadata=meta)
        row = self.svc.get_content_id("local", "file_1")
        self.assertIsNotNone(row)
        self.assertIn("test", row["metadata_json"])

    def test_get_nonexistent(self) -> None:
        row = self.svc.get_content_id("feishu", "nonexistent")
        self.assertIsNone(row)

    def test_retire_content_id(self) -> None:
        cid = self.svc.create_content_id("feishu", "msg_retire")
        self.svc.retire_content_id(cid)
        row = self.svc.get_content_id("feishu", "msg_retire")
        self.assertIsNotNone(row)
        self.assertIsNotNone(row["retired_at"])

    def test_create_random_id(self) -> None:
        cid = self.svc.create_content_id_random("local")
        self.assertTrue(cid.startswith("cnt_"))
        row = self.svc.get_content_id("local", cid)
        self.assertIsNotNone(row)


class TestContentVersionCRUD(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        _create_tables(self.conn)
        self.svc = ContentIdentityService(self.conn)
        self.cid = self.svc.create_content_id("feishu", "msg_ver")

    def tearDown(self) -> None:
        self.conn.close()

    def test_create_version(self) -> None:
        vid = self.svc.create_version(self.cid, content_hash="abc123")
        self.assertTrue(vid.startswith("cv_"))

        versions = self.svc.get_versions(self.cid)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["version_no"], 1)
        self.assertEqual(versions[0]["content_hash"], "abc123")

    def test_version_auto_increment(self) -> None:
        vid1 = self.svc.create_version(self.cid, change_reason="first")
        vid2 = self.svc.create_version(self.cid, change_reason="second")

        versions = self.svc.get_versions(self.cid)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["version_no"], 1)
        self.assertEqual(versions[1]["version_no"], 2)

    def test_get_latest_version(self) -> None:
        self.svc.create_version(self.cid, change_reason="v1")
        vid2 = self.svc.create_version(self.cid, change_reason="v2")

        latest = self.svc.get_latest_version(self.cid)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["content_version_id"], vid2)
        self.assertEqual(latest["change_reason"], "v2")

    def test_get_latest_version_empty(self) -> None:
        cid2 = self.svc.create_content_id("feishu", "msg_empty")
        latest = self.svc.get_latest_version(cid2)
        self.assertIsNone(latest)

    def test_version_with_manifest_id(self) -> None:
        vid = self.svc.create_version(self.cid, manifest_id="m_001")
        v = self.svc.get_latest_version(self.cid)
        self.assertEqual(v["manifest_id"], "m_001")

    def test_version_with_metadata(self) -> None:
        vid = self.svc.create_version(self.cid, metadata={"note": "test"})
        v = self.svc.get_latest_version(self.cid)
        self.assertIn("test", v["metadata_json"])


class TestSourceContentLinks(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        _create_tables(self.conn)
        self.svc = ContentIdentityService(self.conn)
        self.cid1 = self.svc.create_content_id("feishu", "msg_link1")
        self.cid2 = self.svc.create_content_id("feishu", "msg_link2")

    def tearDown(self) -> None:
        self.conn.close()

    def test_link_and_query(self) -> None:
        self.svc.link_source_to_content("src_001", self.cid1, "import")

        contents = self.svc.get_content_for_source("src_001")
        self.assertEqual(contents, [self.cid1])

        sources = self.svc.get_sources_for_content(self.cid1)
        self.assertEqual(sources, ["src_001"])

    def test_multiple_sources_one_content(self) -> None:
        self.svc.link_source_to_content("src_a", self.cid1, "import")
        self.svc.link_source_to_content("src_b", self.cid1, "dedupe")

        sources = self.svc.get_sources_for_content(self.cid1)
        self.assertEqual(sorted(sources), ["src_a", "src_b"])

    def test_one_source_multiple_contents(self) -> None:
        self.svc.link_source_to_content("src_multi", self.cid1, "import")
        self.svc.link_source_to_content("src_multi", self.cid2, "split")

        contents = self.svc.get_content_for_source("src_multi")
        self.assertEqual(sorted(contents), sorted([self.cid1, self.cid2]))

    def test_confidence_default(self) -> None:
        self.svc.link_source_to_content("src_conf", self.cid1, "import")
        cur = self.conn.execute(
            "SELECT confidence FROM source_content_links "
            "WHERE source_record_id = 'src_conf'"
        )
        row = cur.fetchone()
        self.assertEqual(row[0], 1.0)

    def test_custom_confidence(self) -> None:
        self.svc.link_source_to_content("src_low", self.cid1, "dedupe", confidence=0.7)
        cur = self.conn.execute(
            "SELECT confidence FROM source_content_links "
            "WHERE source_record_id = 'src_low'"
        )
        row = cur.fetchone()
        self.assertAlmostEqual(row[0], 0.7)

    def test_empty_results(self) -> None:
        self.assertEqual(self.svc.get_content_for_source("nonexistent"), [])
        self.assertEqual(self.svc.get_sources_for_content("cnt_nonexistent"), [])


class TestContentsProjection(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        _create_tables(self.conn)
        self.svc = ContentIdentityService(self.conn)
        self.cid = self.svc.create_content_id("feishu", "msg_proj")

    def tearDown(self) -> None:
        self.conn.close()

    def test_upsert_insert(self) -> None:
        self.svc.upsert_content(
            self.cid,
            canonical_title="My Content",
            current_stage="F1",
            status="active",
        )
        row = self.svc.get_content(self.cid)
        self.assertIsNotNone(row)
        self.assertEqual(row["canonical_title"], "My Content")
        self.assertEqual(row["current_stage"], "F1")
        self.assertEqual(row["status"], "active")

    def test_upsert_update(self) -> None:
        self.svc.upsert_content(self.cid, canonical_title="Title v1")
        self.svc.upsert_content(self.cid, canonical_title="Title v2")

        row = self.svc.get_content(self.cid)
        self.assertEqual(row["canonical_title"], "Title v2")

    def test_defaults_on_insert(self) -> None:
        self.svc.upsert_content(self.cid)
        row = self.svc.get_content(self.cid)
        self.assertEqual(row["current_stage"], "F0")
        self.assertEqual(row["status"], "active")
        self.assertIsNotNone(row["created_at"])
        self.assertIsNotNone(row["updated_at"])

    def test_get_nonexistent(self) -> None:
        row = self.svc.get_content("cnt_nope")
        self.assertIsNone(row)

    def test_list_by_stage(self) -> None:
        cid2 = self.svc.create_content_id("feishu", "msg_stage2")
        cid3 = self.svc.create_content_id("feishu", "msg_stage3")

        self.svc.upsert_content(self.cid, current_stage="F1")
        self.svc.upsert_content(cid2, current_stage="F1")
        self.svc.upsert_content(cid3, current_stage="F2")

        f1_items = self.svc.list_contents_by_stage("F1")
        self.assertEqual(len(f1_items), 2)

        f2_items = self.svc.list_contents_by_stage("F2")
        self.assertEqual(len(f2_items), 1)

    def test_list_by_stage_and_status(self) -> None:
        cid2 = self.svc.create_content_id("feishu", "msg_status2")

        self.svc.upsert_content(self.cid, current_stage="F1", status="active")
        self.svc.upsert_content(cid2, current_stage="F1", status="retired")

        active = self.svc.list_contents_by_stage("F1", status="active")
        self.assertEqual(len(active), 1)

        retired = self.svc.list_contents_by_stage("F1", status="retired")
        self.assertEqual(len(retired), 1)

    def test_list_by_stage_pagination(self) -> None:
        for i in range(5):
            c = self.svc.create_content_id("feishu", f"msg_page_{i}")
            self.svc.upsert_content(c, current_stage="F3")

        page1 = self.svc.list_contents_by_stage("F3", limit=2, offset=0)
        self.assertEqual(len(page1), 2)

        page2 = self.svc.list_contents_by_stage("F3", limit=2, offset=2)
        self.assertEqual(len(page2), 2)

        page3 = self.svc.list_contents_by_stage("F3", limit=2, offset=4)
        self.assertEqual(len(page3), 1)

    def test_update_current_stage(self) -> None:
        self.svc.upsert_content(self.cid, current_stage="F0")
        self.svc.update_current_stage(self.cid, "F3")

        row = self.svc.get_content(self.cid)
        self.assertEqual(row["current_stage"], "F3")


if __name__ == "__main__":
    unittest.main()
