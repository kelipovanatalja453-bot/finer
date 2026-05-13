"""Tests for ObjectStore — content-addressed object store."""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path

import pytest

from finer.services.project_memory.object_store import ObjectStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        """
        CREATE TABLE storage_objects (
            object_id TEXT PRIMARY KEY,
            sha256 TEXT NOT NULL UNIQUE,
            storage_uri TEXT NOT NULL,
            byte_size INTEGER NOT NULL,
            mime_type TEXT,
            created_at TEXT NOT NULL,
            exists_verified_at TEXT
        )
        """
    )
    return c


@pytest.fixture()
def store(conn: sqlite3.Connection, tmp_root: Path) -> ObjectStore:
    return ObjectStore(conn, tmp_root)


# ---------------------------------------------------------------------------
# put_object / get_object
# ---------------------------------------------------------------------------


class TestPutGetObject:
    def test_put_returns_content_addressed_id(self, store: ObjectStore) -> None:
        data = b"hello world"
        oid = store.put_object(data)
        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        assert oid == expected

    def test_put_stores_bytes_on_disk(self, store: ObjectStore, tmp_root: Path) -> None:
        data = b"payload"
        oid = store.put_object(data)
        hex_part = oid.removeprefix("sha256:")
        path = tmp_root / "objects" / "sha256" / hex_part[:2] / hex_part[2:4] / hex_part
        assert path.exists()
        assert path.read_bytes() == data

    def test_get_object_roundtrip(self, store: ObjectStore) -> None:
        data = b"roundtrip"
        oid = store.put_object(data)
        assert store.get_object(oid) == data

    def test_get_object_missing(self, store: ObjectStore) -> None:
        assert store.get_object("sha256:does_not_exist") is None

    def test_put_stores_mime_type(self, store: ObjectStore) -> None:
        oid = store.put_object(b"x", mime_type="text/plain")
        info = store.get_object_info(oid)
        assert info is not None
        assert info["mime_type"] == "text/plain"

    def test_put_stores_byte_size(self, store: ObjectStore) -> None:
        data = b"12345"
        oid = store.put_object(data)
        info = store.get_object_info(oid)
        assert info["byte_size"] == 5

    def test_put_deduplicates(self, store: ObjectStore, conn: sqlite3.Connection) -> None:
        data = b"same"
        oid1 = store.put_object(data)
        oid2 = store.put_object(data)
        assert oid1 == oid2
        count = conn.execute("SELECT COUNT(*) FROM storage_objects").fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# get_object_info
# ---------------------------------------------------------------------------


class TestGetObjectInfo:
    def test_returns_row(self, store: ObjectStore) -> None:
        oid = store.put_object(b"info")
        row = store.get_object_info(oid)
        assert row is not None
        assert row["object_id"] == oid

    def test_returns_none_for_missing(self, store: ObjectStore) -> None:
        assert store.get_object_info("sha256:nope") is None


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------


class TestDeleteObject:
    def test_removes_file_and_row(self, store: ObjectStore, conn: sqlite3.Connection) -> None:
        oid = store.put_object(b"delete-me")
        store.delete_object(oid)
        assert store.get_object(oid) is None
        assert conn.execute(
            "SELECT 1 FROM storage_objects WHERE object_id = ?", (oid,)
        ).fetchone() is None

    def test_delete_nonexistent_is_noop(self, store: ObjectStore) -> None:
        store.delete_object("sha256:ghost")  # should not raise


# ---------------------------------------------------------------------------
# verify_object / object_exists
# ---------------------------------------------------------------------------


class TestVerify:
    def test_verify_valid(self, store: ObjectStore) -> None:
        oid = store.put_object(b"verify")
        assert store.verify_object(oid) is True

    def test_verify_missing_file(self, store: ObjectStore, tmp_root: Path) -> None:
        oid = store.put_object(b"willvanish")
        # Manually delete the file.
        hex_part = oid.removeprefix("sha256:")
        path = tmp_root / "objects" / "sha256" / hex_part[:2] / hex_part[2:4] / hex_part
        path.unlink()
        assert store.verify_object(oid) is False

    def test_verify_corrupted_file(self, store: ObjectStore, tmp_root: Path) -> None:
        oid = store.put_object(b"intact")
        hex_part = oid.removeprefix("sha256:")
        path = tmp_root / "objects" / "sha256" / hex_part[:2] / hex_part[2:4] / hex_part
        path.write_bytes(b"corrupted")
        assert store.verify_object(oid) is False

    def test_object_exists_true(self, store: ObjectStore) -> None:
        oid = store.put_object(b"exists")
        assert store.object_exists(oid) is True

    def test_object_exists_false(self, store: ObjectStore) -> None:
        assert store.object_exists("sha256:no") is False


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


class TestBatch:
    def test_put_objects(self, store: ObjectStore) -> None:
        items = [(b"a", "text/plain"), (b"b", None), (b"c", "application/json")]
        ids = store.put_objects(items)
        assert len(ids) == 3
        for oid, (data, _) in zip(ids, items):
            assert store.get_object(oid) == data

    def test_verify_all(self, store: ObjectStore) -> None:
        oid1 = store.put_object(b"one")
        oid2 = store.put_object(b"two")
        results = store.verify_all()
        assert results[oid1] is True
        assert results[oid2] is True

    def test_verify_all_detects_corruption(
        self, store: ObjectStore, tmp_root: Path
    ) -> None:
        oid_good = store.put_object(b"good")
        oid_bad = store.put_object(b"bad")
        # Corrupt the bad file.
        hex_part = oid_bad.removeprefix("sha256:")
        path = tmp_root / "objects" / "sha256" / hex_part[:2] / hex_part[2:4] / hex_part
        path.write_bytes(b"tampered")
        results = store.verify_all()
        assert results[oid_good] is True
        assert results[oid_bad] is False


# ---------------------------------------------------------------------------
# Atomic write edge cases
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_no_temp_file_left_behind(self, store: ObjectStore, tmp_root: Path) -> None:
        store.put_object(b"clean")
        tmp_files = list(tmp_root.rglob("*.tmp"))
        assert tmp_files == []

    def test_nested_directory_creation(self, store: ObjectStore, tmp_root: Path) -> None:
        """Directories are created on the fly for the two-level hash split."""
        oid = store.put_object(b"nested")
        hex_part = oid.removeprefix("sha256:")
        expected_dir = tmp_root / "objects" / "sha256" / hex_part[:2] / hex_part[2:4]
        assert expected_dir.is_dir()
