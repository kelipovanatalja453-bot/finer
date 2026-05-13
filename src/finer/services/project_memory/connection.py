"""Thread-safe SQLite connection management for Project Memory."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from finer.paths import DATA_ROOT

PROJECT_MEMORY_ROOT = DATA_ROOT / "project_memory"
PROJECT_MEMORY_DB = PROJECT_MEMORY_ROOT / "finer.project.sqlite3"

_PRAGMAS: list[tuple[str, str]] = [
    ("journal_mode", "WAL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
]


class ConnectionPool:
    """Thread-safe connection pool backed by sqlite3."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[Path, sqlite3.Connection] = {}

    def get_connection(self, db_path: Path | str | None = None) -> sqlite3.Connection:
        """Return a connection to *db_path*, creating parent dirs if needed.

        When *db_path* is ``None`` the active project database is used.
        """
        path = Path(db_path) if db_path is not None else PROJECT_MEMORY_DB
        path = path.resolve()

        with self._lock:
            conn = self._connections.get(path)
            if conn is not None:
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.ProgrammingError:
                    # Connection was closed externally; remove and recreate.
                    self._connections.pop(path, None)

            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            for pragma, value in _PRAGMAS:
                conn.execute(f"PRAGMA {pragma}={value}")
            self._connections[path] = conn
            return conn

    def close_all(self) -> None:
        """Close every cached connection."""
        with self._lock:
            for conn in self._connections.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()


_pool = ConnectionPool()


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Module-level convenience wrapper around the singleton pool."""
    return _pool.get_connection(db_path)


def close_all() -> None:
    """Close all cached connections in the singleton pool."""
    _pool.close_all()


@contextmanager
def transaction(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and rolls back on error."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
