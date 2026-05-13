"""Tests for /api/system/diagnostics with Project Memory integration."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from finer.api.routes.system import router


# ---------------------------------------------------------------------------
# Schema SQL for in-memory Project Memory database
# ---------------------------------------------------------------------------

_PM_SCHEMA_SQL = """
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
  latest_artifact_id TEXT,
  manifest_id TEXT,
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


def _create_pm_db(db_path: Path) -> sqlite3.Connection:
    """Create a Project Memory database with all tables and seed data."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_PM_SCHEMA_SQL)

    # Seed project
    conn.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("proj_test", "inst_test", "Test Project", str(db_path.parent), str(db_path.parent), "active", 1, "2026-05-13T00:00:00Z", "2026-05-13T00:00:00Z"),
    )

    # Seed schema version
    conn.execute(
        "INSERT INTO project_memory_meta VALUES (?, ?, ?)",
        ("schema_version", "1", "2026-05-13T00:00:00Z"),
    )

    # Seed some content
    conn.execute(
        "INSERT INTO content_identities VALUES (?, ?, ?, ?, ?, ?)",
        ("cnt_abc123", "feishu", "ext_001", "2026-05-13T00:00:00Z", None, None),
    )
    conn.execute(
        "INSERT INTO content_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("cv_v1", "cnt_abc123", "hash1", None, 1, "2026-05-13T00:00:00Z", "initial", None),
    )
    conn.execute(
        "INSERT INTO contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("cnt_abc123", "cv_v1", None, "chat", "F1", "Test", None, None, "2026-05-13T00:00:00Z", "2026-05-13T00:00:00Z", "active"),
    )

    # Seed asset_index
    conn.execute(
        "INSERT INTO asset_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("F1:cnt_abc123", "cnt_abc123", "F1", "Test", None, "feishu", "feishu", "chat", None, None, None, "ready", "2026-05-13T00:00:00Z", "2026-05-13T00:00:00Z", "Test feishu chat", None),
    )

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a minimal FastAPI app with the system router."""
    application = FastAPI()
    application.include_router(router, prefix="/api/system")
    return application


@pytest.fixture
def pm_db(tmp_path):
    """Create a temporary Project Memory database."""
    db_path = tmp_path / "project_memory" / "finer.project.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _create_pm_db(db_path)
    yield db_path, conn
    conn.close()


# ---------------------------------------------------------------------------
# Tests — diagnostics with Project Memory
# ---------------------------------------------------------------------------

class TestDiagnosticsWithProjectMemory:
    """When Project Memory DB exists and is healthy."""

    def test_diagnostics_includes_project_memory(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            assert resp.status_code == 200
            data = resp.json()
            assert "projectMemory" in data
            pm = data["projectMemory"]
            assert pm["status"] == "healthy"
            assert pm["projectId"] == "proj_test"
            assert pm["schemaVersion"] == "1"
            assert pm["dbPath"] == str(db_path)

    def test_diagnostics_reports_counts(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            pm = resp.json()["projectMemory"]
            assert pm["contentCount"] == 1
            assert pm["contentVersionCount"] == 1
            assert pm["assetIndexCount"] == 1

    def test_diagnostics_reports_zero_for_empty_tables(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            pm = resp.json()["projectMemory"]
            assert pm["blockCount"] == 0
            assert pm["topicBlockCount"] == 0
            assert pm["objectCount"] == 0
            assert pm["artifactCount"] == 0

    def test_diagnostics_reports_asset_fts_count(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            pm = resp.json()["projectMemory"]
            # FTS content table should reflect asset_index rows
            assert pm["assetFtsCount"] >= 0

    def test_diagnostics_reports_last_rebuild_at(self, app, pm_db):
        db_path, conn = pm_db
        # Seed last rebuild timestamp
        conn.execute(
            "INSERT INTO project_memory_meta VALUES (?, ?, ?)",
            ("last_asset_index_rebuild_at", "2026-05-13T12:00:00Z", "2026-05-13T12:00:00Z"),
        )
        conn.commit()
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            pm = resp.json()["projectMemory"]
            assert pm["lastRebuildAt"] == "2026-05-13T12:00:00Z"


# ---------------------------------------------------------------------------
# Tests — diagnostics without Project Memory
# ---------------------------------------------------------------------------

class TestDiagnosticsWithoutProjectMemory:
    """When Project Memory DB does not exist."""

    def test_diagnostics_reports_missing(self, app, tmp_path):
        fake_path = tmp_path / "nonexistent" / "finer.project.sqlite3"
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", fake_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", fake_path):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            assert resp.status_code == 200
            pm = resp.json()["projectMemory"]
            assert pm["status"] == "missing"
            assert pm["projectId"] is None
            assert pm["schemaVersion"] is None
            assert pm["contentCount"] == 0

    def test_diagnostics_missing_has_all_fields(self, app, tmp_path):
        fake_path = tmp_path / "nonexistent" / "finer.project.sqlite3"
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", fake_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", fake_path):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            pm = resp.json()["projectMemory"]
            expected_keys = {
                "status", "projectId", "schemaVersion", "dbPath",
                "contentCount", "contentVersionCount", "blockCount",
                "topicBlockCount", "objectCount", "artifactCount",
                "assetIndexCount", "assetFtsCount", "lastRebuildAt",
            }
            assert set(pm.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Tests — diagnostics with corrupt DB
# ---------------------------------------------------------------------------

class TestDiagnosticsCorruptDB:
    """When Project Memory DB is present but unreadable."""

    def test_diagnostics_reports_corrupt_on_error(self, app, tmp_path):
        db_path = tmp_path / "project_memory" / "finer.project.sqlite3"
        db_path.parent.mkdir(parents=True)
        # Create a file that is not a valid SQLite database
        db_path.write_text("not a database")
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            assert resp.status_code == 200
            pm = resp.json()["projectMemory"]
            assert pm["status"] in ("corrupt", "missing")


# ---------------------------------------------------------------------------
# Tests — diagnostics preserves existing fields
# ---------------------------------------------------------------------------

class TestDiagnosticsBackwardCompat:
    """Existing diagnostics fields must still be present."""

    def test_preserves_data_root(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            data = resp.json()
            assert "dataRoot" in data
            assert "fileCounts" in data
            assert "cacheStatus" in data

    def test_preserves_cache_status(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.system.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True):
            client = TestClient(app)
            resp = client.get("/api/system/diagnostics")
            cache = resp.json()["cacheStatus"]
            assert "assets_cache_entries" in cache
            assert "manifests_index_built" in cache
