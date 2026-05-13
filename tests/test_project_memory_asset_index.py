"""Tests for AssetIndexService — asset index CRUD, rebuild, and FTS5 search."""

from __future__ import annotations

import sqlite3
import unittest


# ---------------------------------------------------------------------------
# Test helpers — create all required tables in-memory
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE source_groups (
  source_group_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_platform TEXT,
  importer TEXT,
  source_uri TEXT,
  imported_at TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE source_records (
  source_record_id TEXT PRIMARY KEY,
  source_group_id TEXT NOT NULL REFERENCES source_groups(source_group_id),
  external_id TEXT,
  source_uri TEXT,
  original_filename TEXT,
  original_title TEXT,
  source_platform TEXT,
  content_hash TEXT,
  imported_at TEXT NOT NULL,
  status TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE content_identities (
  content_id TEXT PRIMARY KEY,
  identity_scheme TEXT NOT NULL,
  stable_key TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT,
  retired_at TEXT
);

CREATE TABLE content_versions (
  content_version_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_identities(content_id),
  content_hash TEXT,
  manifest_id TEXT,
  version_no INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  change_reason TEXT,
  metadata_json TEXT
);

CREATE TABLE source_content_links (
  source_record_id TEXT NOT NULL REFERENCES source_records(source_record_id),
  content_id TEXT NOT NULL REFERENCES content_identities(content_id),
  link_reason TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL,
  PRIMARY KEY (source_record_id, content_id)
);

CREATE TABLE contents (
  content_id TEXT PRIMARY KEY REFERENCES content_identities(content_id),
  active_content_version_id TEXT REFERENCES content_versions(content_version_id),
  primary_source_record_id TEXT REFERENCES source_records(source_record_id),
  content_type TEXT,
  current_stage TEXT NOT NULL,
  canonical_title TEXT,
  frontend_display_name TEXT,
  latest_manifest_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE storage_objects (
  object_id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  storage_uri TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  mime_type TEXT,
  created_at TEXT NOT NULL,
  exists_verified_at TEXT
);

CREATE TABLE manifests (
  manifest_id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  schema_name TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  object_id TEXT NOT NULL REFERENCES storage_objects(object_id),
  created_at TEXT NOT NULL
);

CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES contents(content_id),
  stage TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  role TEXT NOT NULL,
  object_id TEXT NOT NULL REFERENCES storage_objects(object_id),
  manifest_id TEXT REFERENCES manifests(manifest_id),
  schema_name TEXT,
  schema_version TEXT,
  run_id TEXT,
  artifact_version INTEGER NOT NULL,
  is_canonical INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  metadata_json TEXT
);

CREATE TABLE name_bindings (
  name_binding_id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  stage TEXT,
  namespace TEXT NOT NULL,
  name_kind TEXT NOT NULL,
  display_value TEXT NOT NULL,
  normalized_value TEXT,
  path_safe_value TEXT,
  is_primary INTEGER NOT NULL DEFAULT 0,
  valid_from TEXT NOT NULL,
  valid_to TEXT
);

CREATE TABLE stage_status (
  content_id TEXT NOT NULL REFERENCES contents(content_id),
  stage TEXT NOT NULL,
  status TEXT NOT NULL,
  latest_artifact_id TEXT REFERENCES artifacts(artifact_id),
  error_code TEXT,
  error_message TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (content_id, stage)
);

CREATE TABLE asset_index (
  asset_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES contents(content_id),
  stage TEXT NOT NULL,
  display_name TEXT NOT NULL,
  subtitle TEXT,
  source_platform TEXT,
  source_type TEXT,
  content_type TEXT,
  source_group_id TEXT,
  latest_artifact_id TEXT REFERENCES artifacts(artifact_id),
  manifest_id TEXT REFERENCES manifests(manifest_id),
  status TEXT NOT NULL,
  sort_key TEXT,
  updated_at TEXT NOT NULL,
  search_text TEXT,
  metadata_json TEXT
);
"""


def _make_conn() -> sqlite3.Connection:
    """Create an in-memory SQLite connection with all required tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    return conn


def _seed_content_row(conn: sqlite3.Connection, content_id: str, **overrides: object) -> None:
    """Insert minimal content_identities + contents rows for FK satisfaction."""
    now = overrides.get("now", "2026-05-13T00:00:00Z")
    conn.execute(
        "INSERT OR IGNORE INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
        "VALUES (?, 'test', ?, ?)",
        (content_id, f"key_{content_id}", now),
    )
    conn.execute(
        "INSERT OR IGNORE INTO contents (content_id, content_type, current_stage, created_at, updated_at, status) "
        "VALUES (?, 'chat', 'F0', ?, ?, 'active')",
        (content_id, now, now),
    )
    conn.commit()


def _seed_basic_data(conn: sqlite3.Connection) -> None:
    """Insert minimal seed data for one content item with two stages."""
    conn.execute(
        "INSERT INTO source_groups (source_group_id, source_type, source_name, source_platform, imported_at) "
        "VALUES ('sg_1', 'feishu_chat', 'Test Group', 'feishu', '2026-05-13T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO source_records (source_record_id, source_group_id, source_platform, original_title, imported_at, status) "
        "VALUES ('sr_1', 'sg_1', 'feishu', 'Original Title', '2026-05-13T00:00:00Z', 'active')"
    )
    conn.execute(
        "INSERT INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
        "VALUES ('cnt_abc', 'feishu', 'ext_123', '2026-05-13T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO contents (content_id, primary_source_record_id, content_type, current_stage, canonical_title, frontend_display_name, created_at, updated_at, status) "
        "VALUES ('cnt_abc', 'sr_1', 'chat', 'F1', 'My Chat Title', 'F0 Display Name', '2026-05-13T00:00:00Z', '2026-05-13T01:00:00Z', 'active')"
    )
    # Stage statuses: F0 ready, F1 partial
    conn.execute(
        "INSERT INTO stage_status (content_id, stage, status, updated_at) "
        "VALUES ('cnt_abc', 'F0', 'ready', '2026-05-13T00:30:00Z')"
    )
    conn.execute(
        "INSERT INTO stage_status (content_id, stage, status, updated_at) "
        "VALUES ('cnt_abc', 'F1', 'partial', '2026-05-13T01:00:00Z')"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAssetIndexCRUD(unittest.TestCase):
    """Test upsert, get, list, count, delete operations."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        # Import here to avoid circular issues at module load
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.finer.services.project_memory.asset_index import AssetIndexService
        self.svc = AssetIndexService(self.conn)
        # Seed content rows for FK constraints
        for cid in ("cnt_abc", "cnt_a", "cnt_b", "cnt_0", "cnt_1", "cnt_2", "cnt_3", "cnt_4", "test"):
            _seed_content_row(self.conn, cid)

    def tearDown(self) -> None:
        self.conn.close()

    def test_upsert_and_get(self) -> None:
        self.svc.upsert_asset(
            asset_id="F0:cnt_abc",
            content_id="cnt_abc",
            stage="F0",
            display_name="Test Asset",
            source_platform="feishu",
            content_type="chat",
        )
        asset = self.svc.get_asset("F0:cnt_abc")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["asset_id"], "F0:cnt_abc")
        self.assertEqual(asset["display_name"], "Test Asset")
        self.assertEqual(asset["source_platform"], "feishu")
        self.assertEqual(asset["content_type"], "chat")

    def test_upsert_updates_existing(self) -> None:
        self.svc.upsert_asset(
            asset_id="F0:cnt_abc",
            content_id="cnt_abc",
            stage="F0",
            display_name="Old Name",
        )
        self.svc.upsert_asset(
            asset_id="F0:cnt_abc",
            content_id="cnt_abc",
            stage="F0",
            display_name="New Name",
        )
        asset = self.svc.get_asset("F0:cnt_abc")
        self.assertEqual(asset["display_name"], "New Name")

    def test_get_nonexistent(self) -> None:
        self.assertIsNone(self.svc.get_asset("F99:missing"))

    def test_list_assets_by_stage(self) -> None:
        self.svc.upsert_asset(asset_id="F0:cnt_a", content_id="cnt_a", stage="F0", display_name="A")
        self.svc.upsert_asset(asset_id="F0:cnt_b", content_id="cnt_b", stage="F0", display_name="B")
        self.svc.upsert_asset(asset_id="F1:cnt_a", content_id="cnt_a", stage="F1", display_name="A-F1")

        f0_assets = self.svc.list_assets(stage="F0")
        self.assertEqual(len(f0_assets), 2)
        f1_assets = self.svc.list_assets(stage="F1")
        self.assertEqual(len(f1_assets), 1)

    def test_list_assets_with_status_filter(self) -> None:
        self.svc.upsert_asset(asset_id="F0:cnt_a", content_id="cnt_a", stage="F0", display_name="A", status="ready")
        self.svc.upsert_asset(asset_id="F0:cnt_b", content_id="cnt_b", stage="F0", display_name="B", status="partial")

        ready = self.svc.list_assets(stage="F0", status="ready")
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["asset_id"], "F0:cnt_a")

    def test_list_assets_limit_offset(self) -> None:
        for i in range(5):
            self.svc.upsert_asset(
                asset_id=f"F0:cnt_{i}",
                content_id=f"cnt_{i}",
                stage="F0",
                display_name=f"Asset {i}",
            )
        page = self.svc.list_assets(stage="F0", limit=2, offset=1)
        self.assertEqual(len(page), 2)

    def test_count_assets(self) -> None:
        self.svc.upsert_asset(asset_id="F0:cnt_a", content_id="cnt_a", stage="F0", display_name="A")
        self.svc.upsert_asset(asset_id="F0:cnt_b", content_id="cnt_b", stage="F0", display_name="B")
        self.svc.upsert_asset(asset_id="F1:cnt_a", content_id="cnt_a", stage="F1", display_name="A-F1")

        self.assertEqual(self.svc.count_assets(), 3)
        self.assertEqual(self.svc.count_assets(stage="F0"), 2)
        self.assertEqual(self.svc.count_assets(stage="F1"), 1)
        self.assertEqual(self.svc.count_assets(stage="F0", status="ready"), 2)  # default status is "ready"

    def test_delete_asset(self) -> None:
        self.svc.upsert_asset(asset_id="F0:cnt_a", content_id="cnt_a", stage="F0", display_name="A")
        self.assertIsNotNone(self.svc.get_asset("F0:cnt_a"))
        self.svc.delete_asset("F0:cnt_a")
        self.assertIsNone(self.svc.get_asset("F0:cnt_a"))

    def test_delete_assets_for_content(self) -> None:
        self.svc.upsert_asset(asset_id="F0:cnt_a", content_id="cnt_a", stage="F0", display_name="A")
        self.svc.upsert_asset(asset_id="F1:cnt_a", content_id="cnt_a", stage="F1", display_name="A-F1")
        self.svc.upsert_asset(asset_id="F0:cnt_b", content_id="cnt_b", stage="F0", display_name="B")

        self.svc.delete_assets_for_content("cnt_a")
        self.assertIsNone(self.svc.get_asset("F0:cnt_a"))
        self.assertIsNone(self.svc.get_asset("F1:cnt_a"))
        self.assertIsNotNone(self.svc.get_asset("F0:cnt_b"))


class TestAssetIndexRebuild(unittest.TestCase):
    """Test rebuild_asset_index, rebuild_fts, rebuild_all."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_basic_data(self.conn)
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.finer.services.project_memory.asset_index import AssetIndexService
        self.svc = AssetIndexService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_rebuild_asset_index_creates_rows(self) -> None:
        count = self.svc.rebuild_asset_index()
        # stage_status has F0 ready + F1 partial → 2 rows
        self.assertEqual(count, 2)

        f0 = self.svc.get_asset("F0:cnt_abc")
        self.assertIsNotNone(f0)
        self.assertEqual(f0["stage"], "F0")
        self.assertEqual(f0["status"], "ready")

        f1 = self.svc.get_asset("F1:cnt_abc")
        self.assertIsNotNone(f1)
        self.assertEqual(f1["stage"], "F1")
        self.assertEqual(f1["status"], "partial")

    def test_rebuild_asset_index_is_idempotent(self) -> None:
        self.svc.rebuild_asset_index()
        count = self.svc.rebuild_asset_index()
        self.assertEqual(count, 2)
        self.assertEqual(self.svc.count_assets(), 2)

    def test_rebuild_skips_non_ready_partial(self) -> None:
        # Add a failed stage
        self.conn.execute(
            "INSERT INTO stage_status (content_id, stage, status, updated_at) "
            "VALUES ('cnt_abc', 'F2', 'failed', '2026-05-13T02:00:00Z')"
        )
        self.conn.commit()

        count = self.svc.rebuild_asset_index()
        self.assertEqual(count, 2)  # only ready/partial
        self.assertIsNone(self.svc.get_asset("F2:cnt_abc"))

    def test_rebuild_uses_name_binding_display_name(self) -> None:
        self.conn.execute(
            "INSERT INTO name_bindings "
            "(name_binding_id, subject_type, subject_id, stage, namespace, name_kind, display_value, is_primary, valid_from) "
            "VALUES ('nb_1', 'content', 'cnt_abc', 'F0', 'f0', 'frontend_display_name', 'Custom F0 Name', 1, '2026-05-13T00:00:00Z')"
        )
        self.conn.commit()

        self.svc.rebuild_asset_index()
        f0 = self.svc.get_asset("F0:cnt_abc")
        self.assertEqual(f0["display_name"], "Custom F0 Name")

    def test_rebuild_falls_back_to_canonical_title(self) -> None:
        self.svc.rebuild_asset_index()
        # No name_bindings exist, should use canonical_title
        f0 = self.svc.get_asset("F0:cnt_abc")
        self.assertEqual(f0["display_name"], "My Chat Title")

    def test_rebuild_falls_back_to_frontend_display_name(self) -> None:
        # Remove canonical_title
        self.conn.execute(
            "UPDATE contents SET canonical_title = NULL WHERE content_id = 'cnt_abc'"
        )
        self.conn.commit()

        self.svc.rebuild_asset_index()
        f0 = self.svc.get_asset("F0:cnt_abc")
        self.assertEqual(f0["display_name"], "F0 Display Name")

    def test_rebuild_includes_source_platform(self) -> None:
        self.svc.rebuild_asset_index()
        f0 = self.svc.get_asset("F0:cnt_abc")
        self.assertEqual(f0["source_platform"], "feishu")
        self.assertEqual(f0["source_group_id"], "sg_1")

    def test_rebuild_fts_creates_virtual_table(self) -> None:
        self.svc.rebuild_asset_index()
        self.svc.rebuild_fts()

        # FTS table should exist
        row = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_index_fts'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_rebuild_fts_drops_and_recreates(self) -> None:
        self.svc.rebuild_asset_index()
        self.svc.rebuild_fts()
        # Rebuild again — should not error
        self.svc.rebuild_fts()

    def test_rebuild_all(self) -> None:
        count = self.svc.rebuild_all()
        self.assertEqual(count, 2)
        self.assertEqual(self.svc.count_assets(), 2)

        # FTS table should exist
        row = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_index_fts'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_rebuild_with_multiple_contents(self) -> None:
        # Add a second content item
        self.conn.execute(
            "INSERT INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
            "VALUES ('cnt_def', 'local', 'local_456', '2026-05-13T02:00:00Z')"
        )
        self.conn.execute(
            "INSERT INTO contents (content_id, content_type, current_stage, canonical_title, created_at, updated_at, status) "
            "VALUES ('cnt_def', 'document', 'F0', 'Doc Title', '2026-05-13T02:00:00Z', '2026-05-13T02:00:00Z', 'active')"
        )
        self.conn.execute(
            "INSERT INTO stage_status (content_id, stage, status, updated_at) "
            "VALUES ('cnt_def', 'F0', 'ready', '2026-05-13T02:00:00Z')"
        )
        self.conn.commit()

        count = self.svc.rebuild_asset_index()
        self.assertEqual(count, 3)

        # Verify asset_id format
        self.assertIsNotNone(self.svc.get_asset("F0:cnt_abc"))
        self.assertIsNotNone(self.svc.get_asset("F1:cnt_abc"))
        self.assertIsNotNone(self.svc.get_asset("F0:cnt_def"))


class TestAssetIndexSearch(unittest.TestCase):
    """Test FTS5 search functionality."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_basic_data(self.conn)
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.finer.services.project_memory.asset_index import AssetIndexService
        self.svc = AssetIndexService(self.conn)
        self.svc.rebuild_all()

    def tearDown(self) -> None:
        self.conn.close()

    def test_search_by_display_name(self) -> None:
        results = self.svc.search("My Chat Title")
        self.assertEqual(len(results), 2)  # F0 and F1 both match

    def test_search_by_source_platform(self) -> None:
        results = self.svc.search("feishu")
        self.assertEqual(len(results), 2)

    def test_search_by_content_type(self) -> None:
        results = self.svc.search("chat")
        self.assertEqual(len(results), 2)

    def test_search_with_stage_filter(self) -> None:
        results = self.svc.search("feishu", stage="F0")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["asset_id"], "F0:cnt_abc")

    def test_search_no_results(self) -> None:
        results = self.svc.search("nonexistent_term_xyz")
        self.assertEqual(len(results), 0)

    def test_search_limit(self) -> None:
        # Add more content items
        for i in range(5):
            cid = f"cnt_{i}"
            self.conn.execute(
                "INSERT INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
                "VALUES (?, 'local', ?, '2026-05-13T00:00:00Z')",
                (cid, f"key_{i}")
            )
            self.conn.execute(
                "INSERT INTO contents (content_id, content_type, current_stage, canonical_title, created_at, updated_at, status) "
                "VALUES (?, 'chat', 'F0', 'Chat Number', '2026-05-13T00:00:00Z', '2026-05-13T00:00:00Z', 'active')",
                (cid,)
            )
            self.conn.execute(
                "INSERT INTO stage_status (content_id, stage, status, updated_at) "
                "VALUES (?, 'F0', 'ready', '2026-05-13T00:00:00Z')",
                (cid,)
            )
        self.conn.commit()
        self.svc.rebuild_all()

        # All 6 items (original + 5 new) have "Chat" in display name or search_text
        results = self.svc.search("Chat", limit=3)
        self.assertEqual(len(results), 3)

    def test_search_returns_dict(self) -> None:
        results = self.svc.search("feishu")
        self.assertTrue(len(results) > 0)
        self.assertIsInstance(results[0], dict)
        self.assertIn("asset_id", results[0])


class TestSearchTextComposition(unittest.TestCase):
    """Test search_text field composition."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.finer.services.project_memory.asset_index import AssetIndexService
        self.svc = AssetIndexService(self.conn)
        _seed_content_row(self.conn, "test")

    def tearDown(self) -> None:
        self.conn.close()

    def test_search_text_includes_all_fields(self) -> None:
        self.svc.upsert_asset(
            asset_id="F0:test",
            content_id="test",
            stage="F0",
            display_name="Display Name",
            subtitle="Some Subtitle",
            source_platform="feishu",
            content_type="chat",
        )
        asset = self.svc.get_asset("F0:test")
        self.assertIn("Display Name", asset["search_text"])
        self.assertIn("Some Subtitle", asset["search_text"])
        self.assertIn("feishu", asset["search_text"])
        self.assertIn("chat", asset["search_text"])

    def test_search_text_omits_none_fields(self) -> None:
        self.svc.upsert_asset(
            asset_id="F0:test",
            content_id="test",
            stage="F0",
            display_name="Display",
        )
        asset = self.svc.get_asset("F0:test")
        self.assertEqual(asset["search_text"], "Display")

    def test_compose_search_text_static(self) -> None:
        from src.finer.services.project_memory.asset_index import AssetIndexService
        result = AssetIndexService._compose_search_text("A", "B", "C", "D")
        self.assertEqual(result, "A B C D")

    def test_compose_search_text_with_nones(self) -> None:
        from src.finer.services.project_memory.asset_index import AssetIndexService
        result = AssetIndexService._compose_search_text("A", None, None, "D")
        self.assertEqual(result, "A D")


if __name__ == "__main__":
    unittest.main()
