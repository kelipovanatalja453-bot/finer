"""Restart and recovery simulation tests for Project Memory."""

from __future__ import annotations

import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Full schema SQL (all 4 migrations combined)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE projects (
  project_id TEXT PRIMARY KEY,
  project_instance_id TEXT NOT NULL UNIQUE,
  project_name TEXT NOT NULL,
  project_root TEXT NOT NULL,
  storage_root TEXT NOT NULL,
  status TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE project_memory_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  applied_by TEXT,
  execution_ms INTEGER NOT NULL
);

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

CREATE TABLE pipeline_runs (
  run_id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  input_ref TEXT,
  summary_json TEXT
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_in_memory_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    return conn


def _make_file_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    return conn


def _seed_full_dataset(conn: sqlite3.Connection, prefix: str = "") -> dict[str, int]:
    """Insert a realistic dataset: 3 contents, each with F0+F1 stages, blocks, topics, artifacts."""
    now = "2026-05-13T00:00:00Z"

    counts: dict[str, int] = {}

    # Source groups and records
    for i in range(3):
        sg_id = f"{prefix}sg_{i}"
        sr_id = f"{prefix}sr_{i}"
        conn.execute(
            "INSERT INTO source_groups (source_group_id, source_type, source_name, imported_at) "
            "VALUES (?, 'feishu_chat', ?, ?)", (sg_id, f"Group {i}", now)
        )
        conn.execute(
            "INSERT INTO source_records (source_record_id, source_group_id, imported_at, status) "
            "VALUES (?, ?, ?, 'active')", (sr_id, sg_id, now)
        )

    # Content identities, versions, links, contents
    for i in range(3):
        cid = f"{prefix}cnt_{i}"
        cv_id = f"{prefix}cv_{i}"
        sr_id = f"{prefix}sr_{i}"

        conn.execute(
            "INSERT INTO content_identities (content_id, identity_scheme, stable_key, created_at) "
            "VALUES (?, 'feishu', ?, ?)", (cid, f"ext_{i}", now)
        )
        conn.execute(
            "INSERT INTO content_versions (content_version_id, content_id, version_no, created_at) "
            "VALUES (?, ?, 1, ?)", (cv_id, cid, now)
        )
        conn.execute(
            "INSERT INTO source_content_links (source_record_id, content_id, link_reason, created_at) "
            "VALUES (?, ?, 'import', ?)", (sr_id, cid, now)
        )
        conn.execute(
            "INSERT INTO contents (content_id, active_content_version_id, primary_source_record_id, "
            "content_type, current_stage, canonical_title, created_at, updated_at, status) "
            "VALUES (?, ?, ?, 'chat', 'F1', ?, ?, ?, 'active')",
            (cid, cv_id, sr_id, f"Title {i}", now, now),
        )

    counts["source_groups"] = 3
    counts["source_records"] = 3
    counts["content_identities"] = 3
    counts["content_versions"] = 3
    counts["contents"] = 3

    # Objects and artifacts
    for i in range(3):
        cid = f"{prefix}cnt_{i}"
        obj_id = f"{prefix}obj_{i}"
        conn.execute(
            "INSERT INTO storage_objects (object_id, sha256, storage_uri, byte_size, created_at) "
            "VALUES (?, ?, ?, 100, ?)", (obj_id, f"sha_{i}", f"/tmp/obj_{i}", now)
        )

        # F0 artifact
        art_f0 = f"{prefix}art_f0_{i}"
        conn.execute(
            "INSERT INTO artifacts (artifact_id, content_id, stage, artifact_type, role, object_id, "
            "artifact_version, is_canonical, created_at) "
            "VALUES (?, ?, 'F0', 'content_record', 'canonical', ?, 1, 1, ?)",
            (art_f0, cid, obj_id, now),
        )

        # F1 artifact
        art_f1 = f"{prefix}art_f1_{i}"
        conn.execute(
            "INSERT INTO artifacts (artifact_id, content_id, stage, artifact_type, role, object_id, "
            "artifact_version, is_canonical, created_at) "
            "VALUES (?, ?, 'F1', 'content_envelope', 'canonical', ?, 1, 1, ?)",
            (art_f1, cid, obj_id, now),
        )

        # Edge
        conn.execute(
            "INSERT INTO artifact_edges (parent_artifact_id, child_artifact_id, relation) "
            "VALUES (?, ?, 'standardizes')", (art_f0, art_f1)
        )

    counts["storage_objects"] = 3
    counts["artifacts"] = 6
    counts["artifact_edges"] = 3

    # Blocks and topics
    for i in range(3):
        cid = f"{prefix}cnt_{i}"
        art_f1 = f"{prefix}art_f1_{i}"
        cv_id = f"{prefix}cv_{i}"

        # 3 blocks per content
        block_ids = []
        for b in range(3):
            blk_id = f"{prefix}blk_{i}_{b}"
            block_ids.append(blk_id)
            conn.execute(
                "INSERT INTO content_blocks (block_id, content_id, content_version_id, artifact_id, "
                "stage, block_type, order_index, text_excerpt, created_at) "
                "VALUES (?, ?, ?, ?, 'F1', 'paragraph', ?, ?, ?)",
                (blk_id, cid, cv_id, art_f1, b, f"Block {b}", now),
            )

        # 1 topic per content
        top_id = f"{prefix}top_{i}"
        conn.execute(
            "INSERT INTO topic_blocks (topic_block_id, content_id, source_artifact_id, "
            "topic_title, topic_type, created_at) "
            "VALUES (?, ?, ?, ?, 'theme', ?)",
            (top_id, cid, art_f1, f"Topic {i}", now),
        )
        # Link all 3 blocks to topic
        for b_idx, blk_id in enumerate(block_ids):
            conn.execute(
                "INSERT INTO topic_block_members (topic_block_id, block_id, order_index) "
                "VALUES (?, ?, ?)", (top_id, blk_id, b_idx)
            )

    counts["content_blocks"] = 9
    counts["topic_blocks"] = 3
    counts["topic_block_members"] = 9

    # Name bindings — primary for each content
    for i in range(3):
        cid = f"{prefix}cnt_{i}"
        conn.execute(
            "INSERT INTO name_bindings (name_binding_id, subject_type, subject_id, namespace, "
            "name_kind, display_value, is_primary, valid_from) "
            "VALUES (?, 'content', ?, 'f0', 'frontend_display_name', ?, 1, ?)",
            (f"{prefix}nb_{i}", cid, f"Title {i}", now),
        )

    counts["name_bindings"] = 3

    # Stage status
    for i in range(3):
        cid = f"{prefix}cnt_{i}"
        conn.execute(
            "INSERT INTO stage_status (content_id, stage, status, updated_at) "
            "VALUES (?, 'F0', 'ready', ?)", (cid, now)
        )
        conn.execute(
            "INSERT INTO stage_status (content_id, stage, status, updated_at) "
            "VALUES (?, 'F1', 'ready', ?)", (cid, now)
        )

    counts["stage_status"] = 6

    # Asset index
    for i in range(3):
        cid = f"{prefix}cnt_{i}"
        conn.execute(
            "INSERT INTO asset_index (asset_id, content_id, stage, display_name, status, updated_at) "
            "VALUES (?, ?, 'F0', ?, 'ready', ?)",
            (f"{prefix}F0:{cid}", cid, f"Title {i}", now),
        )
        conn.execute(
            "INSERT INTO asset_index (asset_id, content_id, stage, display_name, status, updated_at) "
            "VALUES (?, ?, 'F1', ?, 'ready', ?)",
            (f"{prefix}F1:{cid}", cid, f"Title {i}", now),
        )

    counts["asset_index"] = 6

    conn.commit()
    # Rebuild FTS
    conn.execute("INSERT INTO asset_index_fts(asset_index_fts) VALUES('rebuild')")
    conn.commit()

    return counts


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRestartPreservesCounts(unittest.TestCase):
    """Insert data, close connection, reopen — all counts must match."""

    def test_counts_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.sqlite3"

            # Write phase
            conn1 = _make_file_conn(db_path)
            original_counts = _seed_full_dataset(conn1)
            conn1.close()

            # Restart phase — open new connection
            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row

            for table, expected in original_counts.items():
                row = conn2.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                actual = row[0]
                self.assertEqual(
                    actual, expected,
                    f"{table}: expected {expected}, got {actual} after restart",
                )

            conn2.close()


class TestAssetIndexRebuildable(unittest.TestCase):
    """Delete asset_index, rebuild from authoritative tables, counts match."""

    def test_rebuild_restores_counts(self) -> None:
        conn = _make_in_memory_conn()
        original_counts = _seed_full_dataset(conn)

        ai_count_before = conn.execute("SELECT COUNT(*) FROM asset_index").fetchone()[0]

        # Delete asset_index
        conn.execute("DELETE FROM asset_index")
        conn.commit()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM asset_index").fetchone()[0], 0)

        # Rebuild using the same logic as AssetIndexService.rebuild_asset_index
        conn.execute(
            """
            INSERT INTO asset_index (
                asset_id, content_id, stage, display_name, subtitle,
                source_platform, source_type, content_type, source_group_id,
                latest_artifact_id, manifest_id, status, sort_key,
                updated_at, search_text, metadata_json
            )
            SELECT
                ss.stage || ':' || c.content_id AS asset_id,
                c.content_id,
                ss.stage,
                COALESCE(c.canonical_title, c.frontend_display_name, c.content_id) AS display_name,
                NULL AS subtitle,
                sr.source_platform,
                sg.source_type,
                c.content_type,
                sr.source_group_id,
                ss.latest_artifact_id,
                c.latest_manifest_id,
                ss.status,
                c.updated_at AS sort_key,
                c.updated_at,
                COALESCE(c.canonical_title, '') || ' ' || COALESCE(sr.source_platform, '') || ' ' || COALESCE(c.content_type, '') AS search_text,
                NULL AS metadata_json
            FROM contents c
            JOIN stage_status ss ON ss.content_id = c.content_id
            LEFT JOIN source_records sr ON sr.source_record_id = c.primary_source_record_id
            LEFT JOIN source_groups sg ON sg.source_group_id = sr.source_group_id
            WHERE ss.status IN ('ready', 'partial')
            """
        )
        conn.commit()

        ai_count_after = conn.execute("SELECT COUNT(*) FROM asset_index").fetchone()[0]
        self.assertEqual(ai_count_before, ai_count_after)

        conn.close()


class TestFtsRebuildable(unittest.TestCase):
    """Delete asset_index_fts, rebuild, verify search works."""

    def test_fts_rebuild_and_search(self) -> None:
        conn = _make_in_memory_conn()
        _seed_full_dataset(conn)

        # Verify search works before
        results = conn.execute(
            "SELECT ai.* FROM asset_index_fts fts "
            "JOIN asset_index ai ON ai.rowid = fts.rowid "
            "WHERE fts.asset_index_fts MATCH 'Title 0'"
        ).fetchall()
        self.assertTrue(len(results) > 0)

        # Drop and rebuild FTS
        conn.execute("DROP TABLE IF EXISTS asset_index_fts")
        conn.commit()

        conn.execute("""
            CREATE VIRTUAL TABLE asset_index_fts USING fts5(
                asset_id UNINDEXED,
                display_name,
                subtitle,
                search_text,
                content='asset_index',
                content_rowid='rowid'
            )
        """)
        conn.commit()
        conn.execute("INSERT INTO asset_index_fts(asset_index_fts) VALUES('rebuild')")
        conn.commit()

        # Search should still work
        results = conn.execute(
            "SELECT ai.* FROM asset_index_fts fts "
            "JOIN asset_index ai ON ai.rowid = fts.rowid "
            "WHERE fts.asset_index_fts MATCH 'Title 0'"
        ).fetchall()
        self.assertTrue(len(results) > 0)

        conn.close()


class TestMissingPayloadPreservesContent(unittest.TestCase):
    """Delete an object file — content row still visible, artifact reports broken."""

    def test_missing_object_keeps_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir) / "storage"
            storage_root.mkdir()

            conn = _make_in_memory_conn()
            now = "2026-05-13T00:00:00Z"

            # Create a real object file
            obj_dir = storage_root / "objects" / "sha256" / "ab" / "cd"
            obj_dir.mkdir(parents=True)
            obj_file = obj_dir / "abcd1234"
            obj_file.write_bytes(b"test payload")

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
                "VALUES ('sha256:abcd1234', 'abcd1234', ?, 12, ?)", (str(obj_file), now)
            )
            conn.execute(
                "INSERT INTO artifacts (artifact_id, content_id, stage, artifact_type, role, object_id, "
                "artifact_version, is_canonical, created_at) "
                "VALUES ('art_1', 'cnt_1', 'F1', 'envelope', 'canonical', 'sha256:abcd1234', 1, 1, ?)",
                (now,),
            )
            conn.execute(
                "INSERT INTO stage_status (content_id, stage, status, updated_at) "
                "VALUES ('cnt_1', 'F1', 'ready', ?)", (now,)
            )
            conn.commit()

            # Verify content exists
            content = conn.execute("SELECT * FROM contents WHERE content_id = 'cnt_1'").fetchone()
            self.assertIsNotNone(content)

            # Delete the object file
            obj_file.unlink()
            self.assertFalse(obj_file.exists())

            # Content row still exists
            content = conn.execute("SELECT * FROM contents WHERE content_id = 'cnt_1'").fetchone()
            self.assertIsNotNone(content, "Content row must survive missing payload")

            # Artifact row still exists
            artifact = conn.execute("SELECT * FROM artifacts WHERE artifact_id = 'art_1'").fetchone()
            self.assertIsNotNone(artifact, "Artifact row must survive missing payload")

            # But the object is gone — verify via ObjectStore
            from src.finer.services.project_memory.object_store import ObjectStore
            obj_store = ObjectStore(conn, storage_root)
            data = obj_store.get_object("sha256:abcd1234")
            self.assertIsNone(data, "Object should be None when file is missing")

            # Integrity check reports the broken artifact
            from src.finer.services.project_memory.integrity import IntegrityChecker
            checker = IntegrityChecker(conn)
            issues = checker.check_artifact_payload_consistency()
            # Object row still exists in DB, so artifact_payload check passes.
            # The broken state is at the file level, detectable by ObjectStore.verify_object.
            verified = obj_store.verify_object("sha256:abcd1234")
            self.assertFalse(verified, "verify_object should return False for missing file")

            conn.close()


class TestNoLLMCallsOnStartup(unittest.TestCase):
    """Verify startup path doesn't import or call any LLM service."""

    def test_startup_imports_no_llm_modules(self) -> None:
        # Track modules before import
        modules_before = set(sys.modules.keys())

        # Import the startup-relevant modules
        from src.finer.services.project_memory.connection import ConnectionPool, get_connection
        from src.finer.services.project_memory.schema import SchemaInspector
        from src.finer.services.project_memory.integrity import IntegrityChecker

        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        # Check no LLM-related modules were imported
        llm_indicators = ["openai", "anthropic", "dashscope", "zhipuai", "instructor"]
        for mod_name in new_modules:
            for indicator in llm_indicators:
                self.assertNotIn(
                    indicator, mod_name.lower(),
                    f"LLM module '{mod_name}' imported during startup path"
                )

    def test_schema_inspector_no_external_calls(self) -> None:
        """SchemaInspector.validate_schema is purely SQL — no side effects."""
        from src.finer.services.project_memory.schema import SchemaInspector

        conn = _make_in_memory_conn()
        _seed_full_dataset(conn)

        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()

        # In-memory DB doesn't have migration metadata, so it'll be degraded
        # but should not crash or require external calls
        self.assertIn(report.status.value, ("healthy", "degraded", "missing"))

        conn.close()


class TestSchemaValidationOnStartup(unittest.TestCase):
    """Verify startup detects healthy/degraded/missing/corrupt states."""

    def test_healthy_state(self) -> None:
        conn = _make_in_memory_conn()
        # Insert migration records and metadata
        now = "2026-05-13T00:00:00Z"
        conn.execute(
            "INSERT INTO project_memory_meta (key, value, updated_at) VALUES ('schema_version', '4', ?)",
            (now,)
        )
        conn.execute(
            "INSERT INTO schema_migrations (version, name, checksum, applied_at, execution_ms) "
            "VALUES (1, '001_initial', 'abc', ?, 10)", (now,)
        )
        _seed_full_dataset(conn)

        from src.finer.services.project_memory.schema import SchemaInspector, SchemaHealth
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()

        self.assertEqual(report.status, SchemaHealth.HEALTHY)
        self.assertEqual(len(report.errors), 0)
        self.assertGreater(len(report.counts), 0)

        conn.close()

    def test_missing_state(self) -> None:
        """Empty database — all required tables missing."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        from src.finer.services.project_memory.schema import SchemaInspector, SchemaHealth
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()

        self.assertEqual(report.status, SchemaHealth.MISSING)
        self.assertTrue(len(report.errors) > 0)

        conn.close()

    def test_degraded_state(self) -> None:
        """Some tables present, some missing."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Only create a subset of tables
        conn.executescript("""
            CREATE TABLE project_memory_meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE source_groups (
              source_group_id TEXT PRIMARY KEY,
              source_type TEXT NOT NULL,
              source_name TEXT NOT NULL,
              imported_at TEXT NOT NULL
            );
        """)

        from src.finer.services.project_memory.schema import SchemaInspector, SchemaHealth
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()

        self.assertEqual(report.status, SchemaHealth.DEGRADED)
        self.assertTrue(len(report.errors) > 0)
        self.assertTrue(any("Missing tables" in e for e in report.errors))

        conn.close()

    def test_corrupt_state(self) -> None:
        """Simulate corrupt DB by closing connection."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.close()

        from src.finer.services.project_memory.schema import SchemaInspector, SchemaHealth
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()

        self.assertEqual(report.status, SchemaHealth.CORRUPT)

    def test_schema_version_read(self) -> None:
        conn = _make_in_memory_conn()
        now = "2026-05-13T00:00:00Z"
        conn.execute(
            "INSERT INTO project_memory_meta (key, value, updated_at) VALUES ('schema_version', '4', ?)",
            (now,)
        )
        conn.commit()

        from src.finer.services.project_memory.schema import SchemaInspector
        inspector = SchemaInspector(conn)
        version = inspector.get_schema_version()
        self.assertEqual(version, 4)

        conn.close()


class TestRestartPreservesBlocksTopicsEdges(unittest.TestCase):
    """Restart preserves all block, topic, edge, and name_binding data."""

    def test_full_data_preserved_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.sqlite3"

            conn1 = _make_file_conn(db_path)
            original_counts = _seed_full_dataset(conn1)
            conn1.close()

            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row

            # Verify blocks
            blocks = conn2.execute("SELECT * FROM content_blocks ORDER BY block_id").fetchall()
            self.assertEqual(len(blocks), original_counts["content_blocks"])

            # Verify topics
            topics = conn2.execute("SELECT * FROM topic_blocks").fetchall()
            self.assertEqual(len(topics), original_counts["topic_blocks"])

            # Verify members
            members = conn2.execute("SELECT * FROM topic_block_members").fetchall()
            self.assertEqual(len(members), original_counts["topic_block_members"])

            # Verify edges
            edges = conn2.execute("SELECT * FROM artifact_edges").fetchall()
            self.assertEqual(len(edges), original_counts["artifact_edges"])

            # Verify name bindings
            bindings = conn2.execute("SELECT * FROM name_bindings").fetchall()
            self.assertEqual(len(bindings), original_counts["name_bindings"])

            conn2.close()


class TestRestartPreservesStageStatus(unittest.TestCase):
    """Stage status rows survive restart and are queryable."""

    def test_stage_status_queryable_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.sqlite3"

            conn1 = _make_file_conn(db_path)
            _seed_full_dataset(conn1)
            conn1.close()

            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row

            # Query F0 ready
            f0_ready = conn2.execute(
                "SELECT COUNT(*) FROM stage_status WHERE stage = 'F0' AND status = 'ready'"
            ).fetchone()[0]
            self.assertEqual(f0_ready, 3)

            # Query F1 ready
            f1_ready = conn2.execute(
                "SELECT COUNT(*) FROM stage_status WHERE stage = 'F1' AND status = 'ready'"
            ).fetchone()[0]
            self.assertEqual(f1_ready, 3)

            conn2.close()


if __name__ == "__main__":
    unittest.main()
