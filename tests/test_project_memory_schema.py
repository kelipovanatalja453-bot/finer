"""Tests for finer.services.project_memory.schema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from finer.services.project_memory.connection import close_all, get_connection
from finer.services.project_memory.schema import (
    SchemaHealth,
    SchemaHealthReport,
    SchemaInspector,
)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    close_all()


def _make_db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def _create_meta_tables(conn: sqlite3.Connection) -> None:
    """Create the minimum tables needed for a basic health check."""
    conn.executescript(
        """
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
        """
    )


def _create_all_required_tables(conn: sqlite3.Connection) -> None:
    """Create all tables required by SchemaInspector._REQUIRED_TABLES."""
    conn.executescript(
        """
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

        CREATE TABLE content_blocks (
          block_id TEXT PRIMARY KEY,
          content_id TEXT NOT NULL,
          block_type TEXT NOT NULL,
          block_index INTEGER NOT NULL,
          object_id TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE topic_blocks (
          topic_block_id TEXT PRIMARY KEY,
          content_id TEXT NOT NULL,
          topic_index INTEGER NOT NULL,
          title TEXT,
          object_id TEXT,
          created_at TEXT NOT NULL
        );

        CREATE TABLE topic_block_members (
          topic_block_id TEXT NOT NULL REFERENCES topic_blocks(topic_block_id),
          block_id TEXT NOT NULL REFERENCES content_blocks(block_id),
          PRIMARY KEY (topic_block_id, block_id)
        );

        CREATE TABLE artifact_edges (
          from_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
          to_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
          edge_type TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (from_artifact_id, to_artifact_id)
        );

        CREATE TABLE name_bindings (
          name_id TEXT PRIMARY KEY,
          subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          name_type TEXT NOT NULL,
          name_value TEXT NOT NULL,
          source TEXT NOT NULL,
          confidence REAL NOT NULL DEFAULT 1.0,
          created_at TEXT NOT NULL
        );

        CREATE TABLE stage_status (
          content_id TEXT NOT NULL,
          stage TEXT NOT NULL,
          status TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          artifact_id TEXT,
          PRIMARY KEY (content_id, stage)
        );

        CREATE TABLE asset_index (
          asset_id TEXT PRIMARY KEY,
          content_id TEXT NOT NULL,
          stage TEXT NOT NULL,
          display_name TEXT,
          search_text TEXT,
          updated_at TEXT NOT NULL
        );
        """
    )


class TestGetSchemaVersion:
    def test_returns_none_when_no_meta_table(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        inspector = SchemaInspector(conn)
        assert inspector.get_schema_version() is None

    def test_returns_none_when_no_schema_version_key(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        _create_meta_tables(conn)
        conn.commit()
        inspector = SchemaInspector(conn)
        assert inspector.get_schema_version() is None

    def test_returns_version_from_meta(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        _create_meta_tables(conn)
        conn.execute(
            "INSERT INTO project_memory_meta (key, value, updated_at) "
            "VALUES ('schema_version', '3', '2026-05-13T00:00:00Z')"
        )
        conn.commit()
        inspector = SchemaInspector(conn)
        assert inspector.get_schema_version() == 3

    def test_returns_none_for_non_integer_value(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        _create_meta_tables(conn)
        conn.execute(
            "INSERT INTO project_memory_meta (key, value, updated_at) "
            "VALUES ('schema_version', 'not_a_number', '2026-05-13T00:00:00Z')"
        )
        conn.commit()
        inspector = SchemaInspector(conn)
        assert inspector.get_schema_version() is None


class TestGetAppliedMigrations:
    def test_returns_empty_when_no_table(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        inspector = SchemaInspector(conn)
        assert inspector.get_applied_migrations() == []

    def test_returns_migrations_ordered(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        _create_meta_tables(conn)
        conn.executemany(
            "INSERT INTO schema_migrations (version, name, checksum, applied_at, applied_by, execution_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (2, "second", "abc", "2026-05-13T01:00:00Z", "test", 10),
                (1, "first", "def", "2026-05-13T00:00:00Z", "test", 5),
            ],
        )
        conn.commit()
        inspector = SchemaInspector(conn)
        migrations = inspector.get_applied_migrations()
        assert len(migrations) == 2
        assert migrations[0]["version"] == 1
        assert migrations[1]["version"] == 2


class TestGetTableCounts:
    def test_returns_empty_when_no_tables(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        inspector = SchemaInspector(conn)
        counts = inspector.get_table_counts()
        assert counts == {}

    def test_counts_tables(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        _create_meta_tables(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, checksum, applied_at, applied_by, execution_ms) "
            "VALUES (1, 'init', 'abc', '2026-05-13T00:00:00Z', 'test', 5)"
        )
        conn.commit()
        inspector = SchemaInspector(conn)
        counts = inspector.get_table_counts()
        assert counts["schema_migrations"] == 1
        assert counts["projects"] == 0
        assert counts["project_memory_meta"] == 0


class TestValidateSchema:
    def test_missing_all_tables(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()
        assert report.status == SchemaHealth.MISSING
        assert len(report.errors) == 1
        assert "Missing tables" in report.errors[0]

    def test_degraded_with_some_tables(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        _create_meta_tables(conn)
        conn.commit()
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()
        assert report.status == SchemaHealth.DEGRADED
        assert len(report.errors) == 1
        assert "Missing tables" in report.errors[0]

    def test_healthy_with_all_tables(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        _create_all_required_tables(conn)
        conn.execute(
            "INSERT INTO project_memory_meta (key, value, updated_at) "
            "VALUES ('schema_version', '1', '2026-05-13T00:00:00Z')"
        )
        conn.commit()
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()
        assert report.status == SchemaHealth.HEALTHY
        assert report.version == 1
        assert report.errors == []
        assert "projects" in report.counts

    def test_health_report_dataclass_fields(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        conn = get_connection(db)
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()
        assert isinstance(report, SchemaHealthReport)
        assert isinstance(report.status, SchemaHealth)
        assert isinstance(report.counts, dict)
        assert isinstance(report.errors, list)

    def test_corrupt_db_returns_corrupt(self, tmp_path: Path) -> None:
        """A closed connection should surface as corrupt."""
        db = _make_db(tmp_path)
        conn = get_connection(db)
        conn.close()
        inspector = SchemaInspector(conn)
        report = inspector.validate_schema()
        assert report.status == SchemaHealth.CORRUPT
        assert len(report.errors) == 1


class TestSchemaHealthEnum:
    def test_all_values(self) -> None:
        assert SchemaHealth.HEALTHY.value == "healthy"
        assert SchemaHealth.DEGRADED.value == "degraded"
        assert SchemaHealth.MISSING.value == "missing"
        assert SchemaHealth.CORRUPT.value == "corrupt"
        assert SchemaHealth.SCHEMA_MISMATCH.value == "schema_mismatch"
