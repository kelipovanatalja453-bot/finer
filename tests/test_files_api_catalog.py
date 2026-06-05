"""Tests for /api/files catalog-first query path."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from finer.api.routes.files import router


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

    # Seed source group + source record
    conn.execute(
        "INSERT INTO source_groups VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("sg_test", "feishu", "Test Chat", "feishu", "feishu_importer", None, "2026-05-13T00:00:00Z", None),
    )
    conn.execute(
        "INSERT INTO source_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("sr_test", "sg_test", "ext_001", None, "test_doc.txt", "Test Document", "feishu", "abc123", "2026-05-13T00:00:00Z", "imported", None),
    )

    # Seed content identity + version + content
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
        ("cnt_abc123", "cv_v1", "sr_test", "chat", "F1", "Test Document", "Test Display", None, "2026-05-13T00:00:00Z", "2026-05-13T00:00:00Z", "active"),
    )
    conn.execute(
        "INSERT INTO source_content_links VALUES (?, ?, ?, ?, ?)",
        ("sr_test", "cnt_abc123", "imported", 1.0, "2026-05-13T00:00:00Z"),
    )

    # Seed asset_index
    conn.execute(
        "INSERT INTO asset_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("F1:cnt_abc123", "cnt_abc123", "F1", "Test Display", None, "feishu", "feishu", "chat", "sg_test", None, None, "ready", "2026-05-13T00:00:00Z", "2026-05-13T00:00:00Z", "Test Display feishu chat", None),
    )

    # Seed a second content for F0 stage
    conn.execute(
        "INSERT INTO content_identities VALUES (?, ?, ?, ?, ?, ?)",
        ("cnt_def456", "local", "manual_001", "2026-05-13T00:00:00Z", None, None),
    )
    conn.execute(
        "INSERT INTO content_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("cv_v2", "cnt_def456", "hash2", None, 1, "2026-05-13T00:00:00Z", "initial", None),
    )
    conn.execute(
        "INSERT INTO contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("cnt_def456", "cv_v2", None, "document", "F0", "Raw Upload", None, None, "2026-05-13T00:00:00Z", "2026-05-13T00:00:00Z", "active"),
    )
    conn.execute(
        "INSERT INTO asset_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("F0:cnt_def456", "cnt_def456", "F0", "Raw Upload", None, "local", "local", "document", None, None, None, "ready", "2026-05-13T00:00:00Z", "2026-05-13T00:00:00Z", "Raw Upload local document", None),
    )

    # Seed name lineage
    conn.execute(
        "INSERT INTO name_bindings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("nb_1", "content", "cnt_abc123", None, "source", "original_filename", "test_doc.txt", "test_doc.txt", "test_doc.txt", 1, "2026-05-13T00:00:00Z", None),
    )
    conn.execute(
        "INSERT INTO name_bindings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("nb_2", "content", "cnt_abc123", None, "f1", "envelope_title", "F1 Envelope Title", None, None, 0, "2026-05-13T00:00:00Z", None),
    )

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a minimal FastAPI app with the files router."""
    application = FastAPI()
    application.include_router(router, prefix="/api/files")
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
# Tests — catalog-first success path
# ---------------------------------------------------------------------------

class TestCatalogFirstSuccess:
    """When Project Memory is available and healthy, return catalog results."""

    def test_catalog_returns_source_catalog(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.files.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.services.project_memory.connection.PROJECT_MEMORY_DB", db_path, create=True), \
             patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            # Also patch the connection module's PROJECT_MEMORY_DB
            with patch("finer.api.routes.files._try_catalog_query") as mock_query:
                mock_query.return_value = {
                    "files": [
                        {
                            "id": "F1:cnt_abc123",
                            "contentId": "cnt_abc123",
                            "contentVersionId": "cv_v1",
                            "stage": "F1",
                            "name": "Test Display",
                            "sourceRecordId": "sr_test",
                            "sourceGroupId": "sg_test",
                            "latestArtifactId": None,
                            "manifestId": None,
                            "nameLineage": {
                                "originalFilename": "test_doc.txt",
                                "f0DisplayName": None,
                                "f1EnvelopeTitle": "F1 Envelope Title",
                                "splitFilename": None,
                                "materializedFilename": None,
                            },
                        }
                    ],
                    "projectMemory": {
                        "projectId": "proj_test",
                        "schemaVersion": "1",
                        "dbPath": str(db_path),
                        "assetIndexUpdatedAt": "2026-05-13T00:00:00Z",
                        "degraded": False,
                    },
                }
                client = TestClient(app)
                resp = client.get("/api/files?tier=F1")
                assert resp.status_code == 200
                data = resp.json()
                assert data["source"] == "catalog"
                assert data["contract"] == "canonical_asset_v1"
                assert data["tier"] == "F1"
                assert len(data["files"]) == 1
                assert data["files"][0]["id"] == "F1:cnt_abc123"
                assert data["files"][0]["nameLineage"]["originalFilename"] == "test_doc.txt"
                assert data["projectMemory"]["projectId"] == "proj_test"

    def test_catalog_respects_limit_and_offset(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.files._try_catalog_query") as mock_query:
            mock_query.return_value = {
                "files": [],
                "projectMemory": {"projectId": "proj_test", "schemaVersion": "1", "dbPath": str(db_path), "assetIndexUpdatedAt": None, "degraded": False},
            }
            client = TestClient(app)
            resp = client.get("/api/files?tier=F1&limit=10&offset=5")
            assert resp.status_code == 200
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args
            assert call_kwargs[1]["limit"] == 10
            assert call_kwargs[1]["offset"] == 5

    def test_catalog_passes_q_param(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.files._try_catalog_query") as mock_query:
            mock_query.return_value = {
                "files": [],
                "projectMemory": {"projectId": "proj_test", "schemaVersion": "1", "dbPath": str(db_path), "assetIndexUpdatedAt": None, "degraded": False},
            }
            client = TestClient(app)
            resp = client.get("/api/files?tier=F1&q=search_term")
            assert resp.status_code == 200
            call_kwargs = mock_query.call_args
            assert call_kwargs[1]["q"] == "search_term"

    def test_catalog_passes_source_filters(self, app, pm_db):
        db_path, conn = pm_db
        with patch("finer.api.routes.files._try_catalog_query") as mock_query:
            mock_query.return_value = {
                "files": [],
                "projectMemory": {"projectId": "proj_test", "schemaVersion": "1", "dbPath": str(db_path), "assetIndexUpdatedAt": None, "degraded": False},
            }
            client = TestClient(app)
            resp = client.get("/api/files?tier=F1&source_type=feishu&source_group_id=sg_test")
            assert resp.status_code == 200
            call_kwargs = mock_query.call_args
            assert call_kwargs[1]["source_type"] == "feishu"
            assert call_kwargs[1]["source_group_id"] == "sg_test"


# ---------------------------------------------------------------------------
# Tests — degraded fallback path
# ---------------------------------------------------------------------------

class TestDegradedFallback:
    """When Project Memory is unavailable, fall back to filesystem scan."""

    def test_degraded_returns_source_degraded_scan(self, app):
        with patch("finer.api.routes.files._try_catalog_query", return_value=None), \
             patch("finer.api.routes.files.build_workflow_assets", return_value=[]):
            client = TestClient(app)
            resp = client.get("/api/files?tier=F1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "degraded_scan"
            assert data["projectMemory"] is None

    def test_degraded_preserves_contract(self, app):
        with patch("finer.api.routes.files._try_catalog_query", return_value=None), \
             patch("finer.api.routes.files.build_workflow_assets", return_value=[]):
            client = TestClient(app)
            resp = client.get("/api/files?tier=F1")
            data = resp.json()
            assert data["contract"] == "canonical_asset_v1"
            assert "tier" in data
            assert "workflow" in data
            assert "files" in data

    def test_unsupported_tier_skips_catalog(self, app):
        """Tiers not in _TIER_TO_STAGE should go directly to degraded scan."""
        with patch("finer.api.routes.files.build_workflow_assets", return_value=[]):
            client = TestClient(app)
            resp = client.get("/api/files?tier=unknown")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "degraded_scan"


# ---------------------------------------------------------------------------
# Tests — _try_catalog_query internals
# ---------------------------------------------------------------------------

class TestTryCatalogQuery:
    """Test the catalog query function directly."""

    def test_returns_none_when_db_missing(self, tmp_path):
        from finer.api.routes.files import _try_catalog_query
        fake_path = tmp_path / "nonexistent" / "db.sqlite3"
        with patch("finer.paths.PROJECT_MEMORY_DB", fake_path):
            result = _try_catalog_query("F1", 50, 0, None, None, None)
            assert result is None

    def test_returns_none_on_schema_mismatch(self, pm_db):
        from finer.api.routes.files import _try_catalog_query
        db_path, conn = pm_db
        # Drop a required table to trigger schema_mismatch
        conn.execute("DROP TABLE asset_index")
        conn.commit()
        with patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            result = _try_catalog_query("F1", 50, 0, None, None, None)
            assert result is None

    def test_catalog_query_returns_files(self, pm_db):
        from finer.api.routes.files import _try_catalog_query
        db_path, conn = pm_db
        with patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            result = _try_catalog_query("F1", 50, 0, None, None, None)
            assert result is not None
            assert len(result["files"]) == 1
            assert result["files"][0]["contentId"] == "cnt_abc123"
            assert result["files"][0]["stage"] == "F1"
            assert result["projectMemory"]["projectId"] == "proj_test"

    def test_catalog_query_filters_by_stage(self, pm_db):
        from finer.api.routes.files import _try_catalog_query
        db_path, conn = pm_db
        with patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            result = _try_catalog_query("F0", 50, 0, None, None, None)
            assert result is not None
            assert len(result["files"]) == 1
            assert result["files"][0]["stage"] == "F0"

    def test_catalog_query_includes_name_lineage(self, pm_db):
        from finer.api.routes.files import _try_catalog_query
        db_path, conn = pm_db
        with patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            result = _try_catalog_query("F1", 50, 0, None, None, None)
            lineage = result["files"][0]["nameLineage"]
            assert lineage["originalFilename"] == "test_doc.txt"
            assert lineage["f1EnvelopeTitle"] == "F1 Envelope Title"

    def test_catalog_query_with_source_type_filter(self, pm_db):
        from finer.api.routes.files import _try_catalog_query
        db_path, conn = pm_db
        with patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            # Filter by matching source_type
            result = _try_catalog_query("F1", 50, 0, None, "feishu", None)
            assert result is not None
            assert len(result["files"]) == 1

            # Filter by non-matching source_type
            result = _try_catalog_query("F1", 50, 0, None, "bilibili", None)
            assert result is not None
            assert len(result["files"]) == 0

    def test_catalog_query_with_fts_search(self, pm_db):
        from finer.api.routes.files import _try_catalog_query
        db_path, conn = pm_db
        # Rebuild FTS to pick up seeded data
        conn.execute("INSERT INTO asset_index_fts(asset_index_fts) VALUES('rebuild')")
        conn.commit()
        with patch("finer.paths.PROJECT_MEMORY_DB", db_path):
            result = _try_catalog_query("F1", 50, 0, "Test", None, None)
            assert result is not None
            assert len(result["files"]) == 1


# ---------------------------------------------------------------------------
# Tests — edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases for the files API."""

    def test_upload_still_works(self, app, tmp_path, monkeypatch):
        # Isolate the data root so the upload lands its raw payload + ContentRecord
        # under tmp_path (and its Project Memory write targets a tmp DB), keeping
        # this test hermetic instead of polluting the real data/ dir.
        monkeypatch.setattr("finer.api.routes.files.DATA_ROOT", tmp_path)
        client = TestClient(app)
        resp = client.post(
            "/api/files",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["contentId"]

    def test_empty_catalog_returns_empty_list(self, app, pm_db):
        db_path, conn = pm_db
        # Clear asset_index
        conn.execute("DELETE FROM asset_index")
        conn.commit()
        with patch("finer.api.routes.files._try_catalog_query") as mock_query:
            mock_query.return_value = {
                "files": [],
                "projectMemory": {"projectId": "proj_test", "schemaVersion": "1", "dbPath": str(db_path), "assetIndexUpdatedAt": None, "degraded": False},
            }
            client = TestClient(app)
            resp = client.get("/api/files?tier=F1")
            data = resp.json()
            assert data["files"] == []
