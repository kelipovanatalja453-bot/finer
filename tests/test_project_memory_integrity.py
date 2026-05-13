"""Tests for IntegrityChecker — all 11 integrity checks."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

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
  retired_at TEXT,
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

CREATE TABLE artifact_edges (
  parent_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  child_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
  relation TEXT NOT NULL,
  PRIMARY KEY (parent_artifact_id, child_artifact_id, relation)
);

CREATE TABLE content_blocks (
  block_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_identities(content_id),
  content_version_id TEXT REFERENCES content_versions(content_version_id),
  artifact_id TEXT REFERENCES artifacts(artifact_id),
  stage TEXT NOT NULL,
  block_type TEXT NOT NULL,
  order_index INTEGER NOT NULL,
  parent_block_id TEXT REFERENCES content_blocks(block_id),
  text_object_id TEXT REFERENCES storage_objects(object_id),
  text_excerpt TEXT,
  start_offset INTEGER,
  end_offset INTEGER,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE topic_blocks (
  topic_block_id TEXT PRIMARY KEY,
  content_id TEXT NOT NULL REFERENCES content_identities(content_id),
  source_artifact_id TEXT REFERENCES artifacts(artifact_id),
  topic_title TEXT NOT NULL,
  topic_type TEXT NOT NULL,
  start_block_index INTEGER,
  end_block_index INTEGER,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE topic_block_members (
  topic_block_id TEXT NOT NULL REFERENCES topic_blocks(topic_block_id),
  block_id TEXT NOT NULL REFERENCES content_blocks(block_id),
  order_index INTEGER NOT NULL,
  PRIMARY KEY (topic_block_id, block_id)
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

CREATE VIRTUAL TABLE asset_index_fts USING fts5(
  asset_id UNINDEXED,
  display_name,
  subtitle,
  search_text,
  content='asset_index',
  content_rowid='rowid'
);
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    return conn


def _seed_healthy(conn: sqlite3.Connection) -> None:
    """Insert a minimal healthy dataset: source → content → artifact → asset."""
    now = "2026-05-13T00:00:00Z"

    conn.execute(
        "INSERT INTO source_groups (source_group_id, source_type, source_name, imported_at) "
        "VALUES ('sg_1', 'feishu_chat', 'Group', ?)", (now,)
    )
    conn.execute(
        "INSERT INTO source_records (source_record_id, source_group_id, imported_at, status) "
        "VALUES ('sr_1', 'sg_1', ?, 'active')", (now,)
    )
    conn.execute(
        "INSERT INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
        "VALUES ('cnt_1', 'feishu', 'ext_1', ?)", (now,)
    )
    conn.execute(
        "INSERT INTO source_content_links (source_record_id, content_id, link_reason, created_at) "
        "VALUES ('sr_1', 'cnt_1', 'import', ?)", (now,)
    )
    conn.execute(
        "INSERT INTO contents (content_id, primary_source_record_id, content_type, current_stage, "
        "canonical_title, created_at, updated_at, status) "
        "VALUES ('cnt_1', 'sr_1', 'chat', 'F1', 'Title', ?, ?, 'active')",
        (now, now),
    )
    conn.execute(
        "INSERT INTO storage_objects (object_id, sha256, storage_uri, byte_size, created_at) "
        "VALUES ('obj_1', 'abc123', '/tmp/obj_1', 100, ?)", (now,)
    )
    conn.execute(
        "INSERT INTO artifacts (artifact_id, content_id, stage, artifact_type, role, object_id, "
        "artifact_version, is_canonical, created_at) "
        "VALUES ('art_1', 'cnt_1', 'F1', 'content_envelope', 'canonical', 'obj_1', 1, 1, ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO name_bindings (name_binding_id, subject_type, subject_id, stage, namespace, "
        "name_kind, display_value, is_primary, valid_from) "
        "VALUES ('nb_1', 'content', 'cnt_1', NULL, 'f0', 'frontend_display_name', 'Title', 1, ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO name_bindings (name_binding_id, subject_type, subject_id, stage, namespace, "
        "name_kind, display_value, is_primary, valid_from) "
        "VALUES ('nb_2', 'artifact', 'art_1', 'F1', 'artifact', 'materialized_filename', 'title.json', 1, ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO stage_status (content_id, stage, status, updated_at) "
        "VALUES ('cnt_1', 'F0', 'ready', ?)", (now,)
    )
    conn.execute(
        "INSERT INTO stage_status (content_id, stage, status, updated_at) "
        "VALUES ('cnt_1', 'F1', 'ready', ?)", (now,)
    )
    conn.execute(
        "INSERT INTO asset_index (asset_id, content_id, stage, display_name, status, updated_at) "
        "VALUES ('F0:cnt_1', 'cnt_1', 'F0', 'Title', 'ready', ?)", (now,)
    )
    conn.execute(
        "INSERT INTO asset_index (asset_id, content_id, stage, display_name, status, updated_at) "
        "VALUES ('F1:cnt_1', 'cnt_1', 'F1', 'Title', 'ready', ?)", (now,)
    )
    conn.commit()
    # Rebuild FTS
    conn.execute("INSERT INTO asset_index_fts(asset_index_fts) VALUES('rebuild')")
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthyDatabase(unittest.TestCase):
    """A properly seeded database should pass all checks."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_run_all_clean(self) -> None:
        report = self.checker.run_all_checks()
        self.assertTrue(report.is_clean, f"Expected clean, got: {[i.message for i in report.issues]}")
        self.assertEqual(report.error_count, 0)

    def test_content_identity_consistency_passes(self) -> None:
        issues = self.checker.check_content_identity_consistency()
        self.assertEqual(len(issues), 0)

    def test_source_link_consistency_passes(self) -> None:
        issues = self.checker.check_source_link_consistency()
        self.assertEqual(len(issues), 0)

    def test_artifact_payload_consistency_passes(self) -> None:
        issues = self.checker.check_artifact_payload_consistency()
        self.assertEqual(len(issues), 0)

    def test_primary_name_consistency_passes(self) -> None:
        issues = self.checker.check_primary_name_consistency()
        self.assertEqual(len(issues), 0)

    def test_asset_index_consistency_passes(self) -> None:
        issues = self.checker.check_asset_index_consistency()
        self.assertEqual(len(issues), 0)

    def test_topic_member_consistency_passes(self) -> None:
        issues = self.checker.check_topic_member_consistency()
        self.assertEqual(len(issues), 0)

    def test_no_legacy_stages_passes(self) -> None:
        issues = self.checker.check_no_legacy_stages()
        self.assertEqual(len(issues), 0)

    def test_asset_index_count_match_passes(self) -> None:
        issues = self.checker.check_asset_index_count_match()
        self.assertEqual(len(issues), 0)

    def test_fts_rebuildable_passes(self) -> None:
        issues = self.checker.check_fts_rebuildable()
        self.assertEqual(len(issues), 0)


class TestContentIdentityConsistency(unittest.TestCase):
    """Test: content row without identity triggers error."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_orphan_content_detected(self) -> None:
        # Insert a content row whose content_id has no identity
        now = "2026-05-13T00:00:00Z"
        # Temporarily disable FK to insert orphan
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute(
            "INSERT INTO contents (content_id, current_stage, created_at, updated_at, status) "
            "VALUES ('orphan_1', 'F0', ?, ?, 'active')", (now, now)
        )
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.commit()

        issues = self.checker.check_content_identity_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "error")
        self.assertIn("orphan_1", issues[0].affected_ids)


class TestSourceLinkConsistency(unittest.TestCase):
    """Test: content identity without source link triggers warning."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_identity_without_source_link(self) -> None:
        now = "2026-05-13T00:00:00Z"
        # Insert identity without source link
        self.conn.execute(
            "INSERT INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
            "VALUES ('cnt_nolink', 'local', 'key_nolink', ?)", (now,)
        )
        self.conn.commit()

        issues = self.checker.check_source_link_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "warning")
        self.assertIn("cnt_nolink", issues[0].affected_ids)


class TestArtifactPayloadConsistency(unittest.TestCase):
    """Test: canonical artifact without object triggers error."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_canonical_artifact_without_object(self) -> None:
        now = "2026-05-13T00:00:00Z"
        # Insert artifact pointing to non-existent object
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute(
            "INSERT INTO artifacts (artifact_id, content_id, stage, artifact_type, role, "
            "object_id, artifact_version, is_canonical, created_at) "
            "VALUES ('art_broken', 'cnt_1', 'F1', 'envelope', 'canonical', 'obj_missing', 2, 1, ?)",
            (now,),
        )
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.commit()

        issues = self.checker.check_artifact_payload_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "error")
        self.assertIn("art_broken", issues[0].affected_ids)


class TestPrimaryNameConsistency(unittest.TestCase):
    """Test: content without primary name triggers warning."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_content_without_primary_name(self) -> None:
        now = "2026-05-13T00:00:00Z"
        # Close existing name binding
        self.conn.execute(
            "UPDATE name_bindings SET valid_to = ? WHERE name_binding_id = 'nb_1'", (now,)
        )
        self.conn.commit()

        issues = self.checker.check_primary_name_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "warning")
        self.assertIn("cnt_1", issues[0].affected_ids)


class TestAssetIndexConsistency(unittest.TestCase):
    """Test: asset referencing missing content triggers error."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_asset_with_missing_content(self) -> None:
        now = "2026-05-13T00:00:00Z"
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute(
            "INSERT INTO asset_index (asset_id, content_id, stage, display_name, status, updated_at) "
            "VALUES ('F0:cnt_ghost', 'cnt_ghost', 'F0', 'Ghost', 'ready', ?)", (now,)
        )
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.commit()

        issues = self.checker.check_asset_index_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "error")
        self.assertIn("F0:cnt_ghost", issues[0].affected_ids)


class TestTopicMemberConsistency(unittest.TestCase):
    """Test: topic member pointing at missing block triggers error."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_topic_member_missing_block(self) -> None:
        now = "2026-05-13T00:00:00Z"
        # Create a topic block
        self.conn.execute(
            "INSERT INTO topic_blocks (topic_block_id, content_id, topic_title, topic_type, created_at) "
            "VALUES ('top_1', 'cnt_1', 'Topic', 'theme', ?)", (now,)
        )
        # Create a real block, insert member, then remove the block
        self.conn.execute(
            "INSERT INTO content_blocks (block_id, content_id, stage, block_type, order_index, created_at) "
            "VALUES ('blk_temp', 'cnt_1', 'F1', 'paragraph', 0, ?)", (now,)
        )
        self.conn.execute(
            "INSERT INTO topic_block_members (topic_block_id, block_id, order_index) "
            "VALUES ('top_1', 'blk_temp', 0)"
        )
        self.conn.commit()
        # Remove the member, delete the block, commit to end implicit txn
        self.conn.execute(
            "DELETE FROM topic_block_members WHERE topic_block_id = 'top_1' AND block_id = 'blk_temp'"
        )
        self.conn.execute("DELETE FROM content_blocks WHERE block_id = 'blk_temp'")
        self.conn.commit()
        # PRAGMA changes require no active transaction
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute(
            "INSERT INTO topic_block_members (topic_block_id, block_id, order_index) "
            "VALUES ('top_1', 'blk_temp', 0)"
        )
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.commit()

        issues = self.checker.check_topic_member_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "error")
        self.assertTrue(any("blk_temp" in aid for aid in issues[0].affected_ids))


class TestStageConsistency(unittest.TestCase):
    """Test: F1 canonical artifact without reachable source_record_id."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_f1_artifact_without_source(self) -> None:
        now = "2026-05-13T00:00:00Z"
        # Create content without primary_source_record_id
        self.conn.execute(
            "INSERT INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
            "VALUES ('cnt_nosrc', 'local', 'key_nosrc', ?)", (now,)
        )
        self.conn.execute(
            "INSERT INTO contents (content_id, current_stage, created_at, updated_at, status) "
            "VALUES ('cnt_nosrc', 'F1', ?, ?, 'active')", (now, now)
        )
        self.conn.execute(
            "INSERT INTO storage_objects (object_id, sha256, storage_uri, byte_size, created_at) "
            "VALUES ('obj_2', 'def456', '/tmp/obj_2', 50, ?)", (now,)
        )
        self.conn.execute(
            "INSERT INTO artifacts (artifact_id, content_id, stage, artifact_type, role, object_id, "
            "artifact_version, is_canonical, created_at) "
            "VALUES ('art_2', 'cnt_nosrc', 'F1', 'envelope', 'canonical', 'obj_2', 1, 1, ?)",
            (now,),
        )
        self.conn.commit()

        issues = self.checker.check_stage_consistency()
        self.assertEqual(len(issues), 1)
        self.assertIn("art_2", issues[0].affected_ids)


class TestNameBindingConsistency(unittest.TestCase):
    """Test: F1 materialized artifact without name_bindings."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_f1_artifact_without_name_binding(self) -> None:
        now = "2026-05-13T00:00:00Z"
        # Close existing artifact name binding
        self.conn.execute(
            "UPDATE name_bindings SET valid_to = ? WHERE name_binding_id = 'nb_2'", (now,)
        )
        self.conn.commit()

        issues = self.checker.check_name_binding_consistency()
        self.assertEqual(len(issues), 1)
        self.assertIn("art_1", issues[0].affected_ids)


class TestNoLegacyStages(unittest.TestCase):
    """Test: legacy stage names trigger errors."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_legacy_stage_in_artifacts(self) -> None:
        now = "2026-05-13T00:00:00Z"
        self.conn.execute(
            "INSERT INTO storage_objects (object_id, sha256, storage_uri, byte_size, created_at) "
            "VALUES ('obj_legacy', 'leg123', '/tmp/obj_legacy', 10, ?)", (now,)
        )
        self.conn.execute(
            "INSERT INTO artifacts (artifact_id, content_id, stage, artifact_type, role, object_id, "
            "artifact_version, is_canonical, created_at) "
            "VALUES ('art_legacy', 'cnt_1', 'L3', 'perception', 'canonical', 'obj_legacy', 1, 0, ?)",
            (now,),
        )
        self.conn.commit()

        issues = self.checker.check_no_legacy_stages()
        self.assertTrue(any(i.severity.value == "error" for i in issues))
        self.assertTrue(any("art_legacy" in str(i.affected_ids) for i in issues))

    def test_legacy_stage_in_stage_status(self) -> None:
        now = "2026-05-13T00:00:00Z"
        self.conn.execute(
            "INSERT INTO stage_status (content_id, stage, status, updated_at) "
            "VALUES ('cnt_1', 'V2', 'ready', ?)", (now,)
        )
        self.conn.commit()

        issues = self.checker.check_no_legacy_stages()
        self.assertTrue(any(i.severity.value == "error" for i in issues))
        self.assertTrue(any("V2" in str(i.affected_ids) for i in issues))


class TestAssetIndexCountMatch(unittest.TestCase):
    """Test: asset_index count mismatch with stage_status."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_count_mismatch_detected(self) -> None:
        # Remove one asset_index row to create mismatch
        self.conn.execute("DELETE FROM asset_index WHERE asset_id = 'F0:cnt_1'")
        self.conn.commit()

        issues = self.checker.check_asset_index_count_match()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "warning")

    def test_count_match_passes(self) -> None:
        issues = self.checker.check_asset_index_count_match()
        self.assertEqual(len(issues), 0)


class TestFtsRebuildable(unittest.TestCase):
    """Test: FTS rebuildable check."""

    def setUp(self) -> None:
        self.conn = _make_conn()
        _seed_healthy(self.conn)
        from src.finer.services.project_memory.integrity import IntegrityChecker
        self.checker = IntegrityChecker(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_fts_missing_reports_info(self) -> None:
        self.conn.execute("DROP TABLE IF EXISTS asset_index_fts")
        self.conn.commit()

        issues = self.checker.check_fts_rebuildable()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity.value, "info")

    def test_fts_count_mismatch_reports_warning(self) -> None:
        # FTS5 content= tables auto-sync from their content table, so we
        # simulate a mismatch by mocking the check itself via direct SQL.
        # Add an extra row to asset_index (bypassing upsert) without
        # triggering FTS sync by inserting after dropping and recreating FTS
        # without the content= link.
        now = "2026-05-13T00:00:00Z"
        self.conn.execute("DROP TABLE IF EXISTS asset_index_fts")
        self.conn.execute(
            "INSERT INTO asset_index (asset_id, content_id, stage, display_name, status, updated_at, search_text) "
            "VALUES ('F99:cnt_1', 'cnt_1', 'F99', 'Extra', 'ready', ?, 'Extra')", (now,)
        )
        # Recreate FTS as a standalone (not content=) table with fewer rows
        self.conn.execute(
            "CREATE VIRTUAL TABLE asset_index_fts USING fts5("
            "asset_id UNINDEXED, display_name, subtitle, search_text)"
        )
        # Insert only one row into FTS (vs 3 in asset_index)
        self.conn.execute(
            "INSERT INTO asset_index_fts(asset_id, display_name, subtitle, search_text) "
            "VALUES ('F0:cnt_1', 'Title', '', 'Title feishu chat')"
        )
        self.conn.commit()

        issues = self.checker.check_fts_rebuildable()
        self.assertTrue(any(i.severity.value == "warning" for i in issues))


class TestIntegrityReport(unittest.TestCase):
    """Test IntegrityReport aggregation."""

    def test_is_clean_with_no_issues(self) -> None:
        from src.finer.services.project_memory.integrity import IntegrityReport
        report = IntegrityReport()
        self.assertTrue(report.is_clean)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)

    def test_is_clean_false_with_errors(self) -> None:
        from src.finer.services.project_memory.integrity import (
            IntegrityReport, IntegrityIssue, Severity,
        )
        report = IntegrityReport(issues=[
            IntegrityIssue("test", Severity.ERROR, "bad"),
        ])
        self.assertFalse(report.is_clean)
        self.assertEqual(report.error_count, 1)

    def test_counts_by_severity(self) -> None:
        from src.finer.services.project_memory.integrity import (
            IntegrityReport, IntegrityIssue, Severity,
        )
        report = IntegrityReport(issues=[
            IntegrityIssue("a", Severity.ERROR, "e1"),
            IntegrityIssue("b", Severity.ERROR, "e2"),
            IntegrityIssue("c", Severity.WARNING, "w1"),
            IntegrityIssue("d", Severity.INFO, "i1"),
        ])
        self.assertEqual(report.error_count, 2)
        self.assertEqual(report.warning_count, 1)
        self.assertEqual(report.info_count, 1)


if __name__ == "__main__":
    unittest.main()
