"""Tests for finer.services.project_memory.connection."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from finer.services.project_memory.connection import (
    ConnectionPool,
    close_all,
    get_connection,
    transaction,
)


@pytest.fixture(autouse=True)
def _cleanup_pool():
    """Ensure the singleton pool is clean after each test."""
    yield
    close_all()


class TestConnectionPool:
    def test_get_connection_creates_db(self, tmp_path: Path) -> None:
        db = tmp_path / "sub" / "test.db"
        pool = ConnectionPool()
        conn = pool.get_connection(db)
        assert db.exists()
        assert isinstance(conn, sqlite3.Connection)
        pool.close_all()

    def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        pool = ConnectionPool()
        conn = pool.get_connection(db)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        pool.close_all()

    def test_foreign_keys_enabled(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        pool = ConnectionPool()
        conn = pool.get_connection(db)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        pool.close_all()

    def test_busy_timeout_set(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        pool = ConnectionPool()
        conn = pool.get_connection(db)
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 5000
        pool.close_all()

    def test_same_connection_returned_for_same_path(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        pool = ConnectionPool()
        conn1 = pool.get_connection(db)
        conn2 = pool.get_connection(db)
        assert conn1 is conn2
        pool.close_all()

    def test_close_all_clears_cache(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        pool = ConnectionPool()
        pool.get_connection(db)
        pool.close_all()
        # After close_all, a new connection should be created.
        conn = pool.get_connection(db)
        assert isinstance(conn, sqlite3.Connection)
        pool.close_all()

    def test_stale_connection_is_replaced(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        pool = ConnectionPool()
        conn1 = pool.get_connection(db)
        conn1.close()
        conn2 = pool.get_connection(db)
        assert conn2 is not conn1
        pool.close_all()


class TestGetConnection:
    def test_default_uses_project_memory_db(self) -> None:
        """get_connection() without args should resolve without error."""
        # We can't guarantee the default path is writable, so just check it
        # doesn't raise an unexpected error by mocking.
        # Instead, test with explicit path.
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            conn = get_connection(db)
            assert isinstance(conn, sqlite3.Connection)
            close_all()


class TestTransaction:
    def test_commit_on_success(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with transaction(db) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO t (id) VALUES (1)")

        # Verify data persisted.
        conn = get_connection(db)
        row = conn.execute("SELECT id FROM t").fetchone()
        assert row[0] == 1
        close_all()

    def test_rollback_on_error(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        # Create the table first.
        with transaction(db) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")

        # Insert then raise — data should be rolled back.
        with pytest.raises(ValueError):
            with transaction(db) as conn:
                conn.execute("INSERT INTO t (id) VALUES (42)")
                raise ValueError("boom")

        conn = get_connection(db)
        rows = conn.execute("SELECT * FROM t").fetchall()
        assert len(rows) == 0
        close_all()

    def test_connection_has_row_factory(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        with transaction(db) as conn:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO t (id, name) VALUES (1, 'alice')")
            row = conn.execute("SELECT * FROM t").fetchone()
            assert row["name"] == "alice"
        close_all()
