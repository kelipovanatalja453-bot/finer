"""Content-addressed object store backed by SQLite and filesystem."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ObjectStore:
    """Content-addressed store: SHA-256 keyed files on disk, metadata in SQLite."""

    def __init__(self, conn: sqlite3.Connection, storage_root: Path) -> None:
        self._conn = conn
        self._storage_root = storage_root
        self._objects_root = storage_root / "objects" / "sha256"

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def put_object(
        self, data: bytes, mime_type: Optional[str] = None
    ) -> str:
        """Store *data* atomically and return ``object_id`` (``sha256:<hex>``)."""
        sha256_hex = hashlib.sha256(data).hexdigest()
        object_id = f"sha256:{sha256_hex}"

        # Fast path: already registered.
        if self.object_exists(object_id):
            return object_id

        dest = self._object_path(sha256_hex)
        self._atomic_write(dest, data)

        now = _utcnow_iso()
        self._conn.execute(
            """
            INSERT OR IGNORE INTO storage_objects
                (object_id, sha256, storage_uri, byte_size, mime_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (object_id, sha256_hex, str(dest), len(data), mime_type, now),
        )
        self._conn.commit()
        return object_id

    def get_object(self, object_id: str) -> Optional[bytes]:
        """Return raw bytes for *object_id*, or ``None`` if not found."""
        row = self._conn.execute(
            "SELECT storage_uri FROM storage_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            return None
        path = Path(row[0])
        if not path.exists():
            return None
        return path.read_bytes()

    def get_object_info(self, object_id: str) -> Optional[sqlite3.Row]:
        """Return the ``storage_objects`` row, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM storage_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        return row

    def delete_object(self, object_id: str) -> None:
        """Remove file and DB row for *object_id*."""
        row = self._conn.execute(
            "SELECT storage_uri FROM storage_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        if row is not None:
            path = Path(row[0])
            if path.exists():
                path.unlink()
            self._conn.execute(
                "DELETE FROM storage_objects WHERE object_id = ?",
                (object_id,),
            )
            self._conn.commit()

    def verify_object(self, object_id: str) -> bool:
        """Check that the file exists on disk and its SHA-256 matches."""
        row = self._conn.execute(
            "SELECT sha256, storage_uri FROM storage_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        if row is None:
            return False
        expected_hash, storage_uri = row[0], row[1]
        path = Path(storage_uri)
        if not path.exists():
            return False
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        return actual_hash == expected_hash

    def object_exists(self, object_id: str) -> bool:
        """Quick DB-only existence check."""
        row = self._conn.execute(
            "SELECT 1 FROM storage_objects WHERE object_id = ?",
            (object_id,),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def put_objects(
        self, items: list[tuple[bytes, Optional[str]]]
    ) -> list[str]:
        """Store multiple ``(data, mime_type)`` pairs; return list of object_ids."""
        return [self.put_object(data, mime) for data, mime in items]

    def verify_all(self) -> dict[str, bool]:
        """Verify every registered object; return ``{object_id: is_valid}``."""
        rows = self._conn.execute(
            "SELECT object_id, sha256, storage_uri FROM storage_objects"
        ).fetchall()
        results: dict[str, bool] = {}
        for object_id, expected_hash, storage_uri in rows:
            path = Path(storage_uri)
            if not path.exists():
                results[object_id] = False
                continue
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            results[object_id] = actual_hash == expected_hash
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _object_path(self, sha256_hex: str) -> Path:
        """Return the on-disk path for a given hex hash."""
        return self._objects_root / sha256_hex[:2] / sha256_hex[2:4] / sha256_hex

    @staticmethod
    def _atomic_write(dest: Path, data: bytes) -> None:
        """Write *data* to *dest* via temp file + fsync + rename."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest.with_suffix(dest.suffix + ".tmp")
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(str(tmp_path), str(dest))
