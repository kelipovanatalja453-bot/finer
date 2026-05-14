"""F0 Project Memory contract tests — schema, query, startup, API, error codes."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finer.schemas.f0_index import F0IndexHealth, F0IndexQuery, F0IndexResult, F0IndexSchema
from finer.startup import F0IndexStartupState, F0StartupResult, check_f0_index_on_startup, rebuild_f0_index


# ---------------------------------------------------------------------------
# 1. Schema contract tests
# ---------------------------------------------------------------------------

class TestF0IndexSchema:
    """Validate F0 index schema definitions."""

    def test_content_records_columns_include_required_fields(self):
        cols = F0IndexSchema.CONTENT_RECORDS_COLUMNS
        required = {"content_id", "source_type", "raw_path", "file_type", "collected_at"}
        assert required.issubset(set(cols.keys()))

    def test_content_records_primary_key(self):
        assert "PRIMARY KEY" in F0IndexSchema.CONTENT_RECORDS_COLUMNS["content_id"]

    def test_import_runs_columns_include_status(self):
        cols = F0IndexSchema.IMPORT_RUNS_COLUMNS
        assert "status" in cols
        assert "source_channel" in cols

    def test_index_metadata_table_exists(self):
        assert F0IndexSchema.INDEX_METADATA_TABLE == "index_metadata"
        assert "key" in F0IndexSchema.INDEX_METADATA_COLUMNS


# ---------------------------------------------------------------------------
# 2. Health model tests
# ---------------------------------------------------------------------------

class TestF0IndexHealth:
    """Validate F0IndexHealth behavior."""

    def _make_health(self, **overrides):
        defaults = dict(
            status="healthy",
            record_count=100,
            last_rebuild_at="2026-05-11T09:00:00",
            last_rebuild_duration_ms=500,
            manifest_count_on_disk=100,
            drift=0,
            db_path="/tmp/f0_index.db",
            db_size_bytes=4096,
        )
        defaults.update(overrides)
        return F0IndexHealth(**defaults)

    def test_healthy_no_drift_not_needs_rebuild(self):
        h = self._make_health(status="healthy", drift=0)
        assert h.needs_rebuild is False

    def test_missing_needs_rebuild(self):
        h = self._make_health(status="missing")
        assert h.needs_rebuild is True

    def test_stale_needs_rebuild(self):
        h = self._make_health(status="stale")
        assert h.needs_rebuild is True

    def test_drift_nonzero_needs_rebuild(self):
        h = self._make_health(status="healthy", drift=5)
        assert h.needs_rebuild is True

    def test_frozen(self):
        h = self._make_health()
        with pytest.raises(AttributeError):
            h.status = "stale"


# ---------------------------------------------------------------------------
# 3. Query shape tests
# ---------------------------------------------------------------------------

class TestF0IndexQuery:
    """Validate query shape defaults."""

    def test_default_query_values(self):
        q = F0IndexQuery()
        assert q.sort_by == "collected_at"
        assert q.sort_order == "desc"
        assert q.limit == 50
        assert q.offset == 0

    def test_query_frozen(self):
        q = F0IndexQuery()
        with pytest.raises(AttributeError):
            q.limit = 100

    def test_all_filters_none_by_default(self):
        q = F0IndexQuery()
        assert q.source_type is None
        assert q.source_platform is None
        assert q.creator_id is None


# ---------------------------------------------------------------------------
# 4. Startup tests (real behavior, no NotImplementedError)
# ---------------------------------------------------------------------------

class TestF0Startup:
    """Validate startup behavior with real schema inspection."""

    def test_startup_missing_db_returns_missing(self, tmp_path: Path):
        db = tmp_path / "nonexistent.db"
        result = check_f0_index_on_startup(db)
        assert result.state == F0IndexStartupState.MISSING
        assert result.health is None
        assert result.action_taken == "none"

    def test_startup_empty_db_returns_missing(self, tmp_path: Path):
        db = tmp_path / "empty.db"
        # Create empty DB (no Project Memory tables)
        conn = sqlite3.connect(str(db))
        conn.close()
        result = check_f0_index_on_startup(db)
        assert result.state == F0IndexStartupState.MISSING
        assert result.health is None

    def test_startup_state_enum_values(self):
        assert F0IndexStartupState.READY == "ready"
        assert F0IndexStartupState.STALE == "stale"
        assert F0IndexStartupState.MISSING == "missing"
        assert F0IndexStartupState.CORRUPT == "corrupt"

    def test_startup_result_dataclass(self):
        r = F0StartupResult(
            state=F0IndexStartupState.MISSING,
            health=None,
            message="no index",
            action_taken="none",
        )
        assert r.state == F0IndexStartupState.MISSING
        assert r.health is None

    def test_rebuild_sync_returns_string(self, tmp_path: Path):
        db = tmp_path / "test.db"
        # Create minimal schema so rebuild doesn't crash
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE project_memory_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE source_groups (source_group_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_name TEXT NOT NULL, imported_at TEXT NOT NULL);
            CREATE TABLE source_records (source_record_id TEXT PRIMARY KEY, source_group_id TEXT NOT NULL, imported_at TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE content_identities (content_id TEXT PRIMARY KEY, identity_scheme TEXT NOT NULL, stable_key TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE content_versions (content_version_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, version_no INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE source_content_links (source_record_id TEXT NOT NULL, content_id TEXT NOT NULL, link_reason TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (source_record_id, content_id));
            CREATE TABLE contents (content_id TEXT PRIMARY KEY, content_type TEXT, current_stage TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE storage_objects (object_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, storage_uri TEXT NOT NULL, byte_size INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE manifests (manifest_id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, schema_name TEXT NOT NULL, schema_version TEXT NOT NULL, object_id TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE artifacts (artifact_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, stage TEXT NOT NULL, artifact_type TEXT NOT NULL, role TEXT NOT NULL, object_id TEXT NOT NULL, artifact_version INTEGER NOT NULL, is_canonical INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
            CREATE TABLE name_bindings (name_binding_id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, namespace TEXT NOT NULL, name_kind TEXT NOT NULL, display_value TEXT NOT NULL, is_primary INTEGER NOT NULL DEFAULT 0, valid_from TEXT NOT NULL);
            CREATE TABLE stage_status (content_id TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (content_id, stage));
            CREATE TABLE asset_index (asset_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, stage TEXT NOT NULL, display_name TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL, search_text TEXT);
            CREATE TABLE content_blocks (block_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, block_type TEXT NOT NULL, block_index INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE topic_blocks (topic_block_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, topic_index INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE topic_block_members (topic_block_id TEXT NOT NULL, block_id TEXT NOT NULL, PRIMARY KEY (topic_block_id, block_id));
            CREATE TABLE artifact_edges (from_artifact_id TEXT NOT NULL, to_artifact_id TEXT NOT NULL, edge_type TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (from_artifact_id, to_artifact_id));
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL, applied_by TEXT, execution_ms INTEGER NOT NULL);
            CREATE TABLE project_memory_meta2 (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        """)
        conn.close()
        result = rebuild_f0_index(db, background=False)
        assert result == "sync_complete"

    def test_rebuild_background_returns_task_id(self, tmp_path: Path):
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE project_memory_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE asset_index (asset_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, stage TEXT NOT NULL, display_name TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL, search_text TEXT);
        """)
        conn.close()
        result = rebuild_f0_index(db, background=True)
        assert result.startswith("f0-rebuild-")


# ---------------------------------------------------------------------------
# 5. API tests (real endpoints)
# ---------------------------------------------------------------------------

class TestF0IndexAPI:
    """Validate API endpoint behavior."""

    @pytest.fixture()
    def client(self):
        from finer.api.server import app
        return TestClient(app, raise_server_exceptions=False)

    def test_health_endpoint_returns_200(self, client):
        resp = client.get("/api/f0-index/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "data" in data
        assert "status" in data["data"]

    def test_records_endpoint_returns_200_or_error(self, client):
        resp = client.get("/api/f0-index/records")
        # Either 200 (if DB exists) or 503/500 (if index missing/failed)
        assert resp.status_code in (200, 503, 500)
        data = resp.json()
        assert "ok" in data

    def test_rebuild_endpoint_returns_200(self, client):
        resp = client.post("/api/f0-index/rebuild")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "data" in data


# ---------------------------------------------------------------------------
# 6. Error code tests
# ---------------------------------------------------------------------------

class TestF0IndexErrorCodes:
    """Validate F0 index error codes exist."""

    def test_error_codes_defined(self):
        from finer.errors.codes import ErrorCode
        assert hasattr(ErrorCode, 'F0_INDEX_001')
        assert hasattr(ErrorCode, 'F0_INDEX_002')
        assert hasattr(ErrorCode, 'F0_INDEX_003')

    def test_error_codes_have_metadata(self):
        from finer.errors import get_error_info, ErrorCode
        for code in (ErrorCode.F0_INDEX_001, ErrorCode.F0_INDEX_002, ErrorCode.F0_INDEX_003):
            info = get_error_info(code)
            assert info.fix_hint
            assert info.title
