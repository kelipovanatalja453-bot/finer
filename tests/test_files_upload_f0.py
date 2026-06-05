"""BK4 — local upload F0 intake tests.

Covers the upload contract added to ``POST /api/files``:
- a successful upload persists a canonical ContentRecord + ImportReceipt on disk
  and registers exactly one new F0 row in Project Memory (R-16);
- path-traversal / unsafe filenames are rejected before any file is written
  (R-17);
- oversize and non-whitelisted payloads are rejected with a canonical Line F
  error envelope (R-28).

All writes are anchored on a tmp data root + a freshly-migrated tmp Project
Memory DB so the live catalog is never touched.
"""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from finer.api.routes.files import router
from finer.api.routes.files_utils import MAX_UPLOAD_BYTES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _migrate_pm_db(db_path: Path) -> None:
    """Apply the real Project Memory migrations to a fresh DB file."""
    from finer.scripts.project_memory_migrate import discover_migrations, _apply_migration

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    for migration in discover_migrations():
        _apply_migration(conn, migration)
    conn.commit()
    conn.close()


@pytest.fixture()
def app() -> FastAPI:
    from finer.errors import register_error_handlers

    application = FastAPI()
    register_error_handlers(application)
    application.include_router(router, prefix="/api/files")
    return application


@pytest.fixture()
def upload_env(tmp_path: Path, monkeypatch):
    """Point the upload handler's data root + PM DB at tmp_path.

    Yields ``(data_root, pm_db_path)``. The PM DB is fully migrated so the
    upload's ``F0IndexWriter`` write succeeds against a real schema.
    """
    data_root = tmp_path / "data"
    pm_db = data_root / "project_memory" / "finer.project.sqlite3"
    _migrate_pm_db(pm_db)

    # Make sure the pooled connection for this path is fresh (avoid leakage
    # across tests) and gets closed afterwards.
    from finer.services.project_memory import connection as pm_conn

    monkeypatch.setattr("finer.api.routes.files.DATA_ROOT", data_root)

    yield data_root, pm_db

    pm_conn.close_all()


@pytest.fixture()
def client(app) -> TestClient:
    """TestClient that surfaces FinerError as JSON envelopes (no re-raise)."""
    return TestClient(app, raise_server_exceptions=False)


def _pm_count(pm_db: Path, where: str = "stage = 'F0'") -> int:
    conn = sqlite3.connect(str(pm_db))
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM asset_index WHERE {where}"
        ).fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Success path — R-16
# ---------------------------------------------------------------------------

class TestUploadCreatesRecord:
    def test_upload_persists_record_and_increments_pm(self, client, app, upload_env):
        data_root, pm_db = upload_env
        before = _pm_count(pm_db)

        resp = client.post(
            "/api/files",
            files={"file": ("notes.txt", io.BytesIO(b"hello finer"), "text/plain")},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["stageBadge"] == "F0"
        assert body["workflow"] == "intake"
        content_id = body["contentId"]
        assert content_id

        # ContentRecord JSON persisted under data/F0_intake/local/<id>.json
        record_path = data_root / "F0_intake" / "local" / f"{content_id}.json"
        receipt_path = data_root / "F0_intake" / "local" / f"{content_id}.receipt.json"
        assert record_path.exists(), "ContentRecord JSON not written"
        assert receipt_path.exists(), "ImportReceipt JSON not written"

        # Raw payload landed under data/raw/local/
        raw_path = data_root / "raw" / "local" / "notes.txt"
        assert raw_path.exists()
        assert raw_path.read_bytes() == b"hello finer"

        # ContentRecord round-trips and carries canonical F0 fields
        from finer.schemas.content import ContentRecord

        record = ContentRecord.model_validate_json(record_path.read_text())
        assert record.content_id == content_id
        assert record.source_type == "manual_upload"
        assert record.source_platform == "local"
        assert record.file_type == "text"
        assert record.dedupe_fingerprint == body["dedupeFingerprint"]
        assert record.raw_path == "raw/local/notes.txt"

        # Project Memory gained exactly one F0 asset row
        after = _pm_count(pm_db)
        assert after == before + 1
        assert body["projectMemoryRegistered"] is True

        # The asset_index row is keyed by F0:<content_id>
        conn = sqlite3.connect(str(pm_db))
        try:
            row = conn.execute(
                "SELECT asset_id, source_type, source_platform, status "
                "FROM asset_index WHERE content_id = ?",
                (content_id,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == f"F0:{content_id}"
        assert row[1] == "manual_upload"
        assert row[2] == "local"
        assert row[3] == "ready"

    def test_upload_returns_deterministic_source_record_id(self, client, app, upload_env):
        import hashlib

        _, pm_db = upload_env
        resp = client.post(
            "/api/files",
            files={"file": ("doc.md", io.BytesIO(b"# title"), "text/markdown")},
        )
        body = resp.json()
        cid = body["contentId"]
        expected = "sr_" + hashlib.sha256(f"sr:{cid}".encode()).hexdigest()[:16]
        assert body["sourceRecordId"] == expected

        # And it matches the row the writer actually persisted.
        conn = sqlite3.connect(str(pm_db))
        try:
            row = conn.execute(
                "SELECT primary_source_record_id FROM contents WHERE content_id = ?",
                (cid,),
            ).fetchone()
        finally:
            conn.close()
        assert row[0] == expected


# ---------------------------------------------------------------------------
# Path traversal / unsafe filenames — R-17
# ---------------------------------------------------------------------------

class TestUploadFilenameSafety:
    """R-17: an untrusted filename can never write outside data/raw/local.

    The secure contract is *neutralize-or-reject*: directory components and
    absolute prefixes are stripped to a bare basename (which then still has to
    pass the extension allowlist), and a filename with no usable basename (``..``)
    is rejected outright. Either way, nothing escapes data/raw/local.
    """

    # These keep a valid, whitelisted extension after their directory parts are
    # stripped, so the secure outcome is "land as basename inside raw/local",
    # NOT a 500 / escape.
    @pytest.mark.parametrize(
        ("evil_name", "expected_basename"),
        [
            ("../escape.txt", "escape.txt"),
            ("/abs/path/secret.txt", "secret.txt"),
            ("..\\..\\windows\\system32\\evil.txt", "evil.txt"),
            ("....//evil.txt", "evil.txt"),
        ],
    )
    def test_traversal_is_neutralized_to_basename(
        self, client, app, upload_env, evil_name, expected_basename
    ):
        data_root, _ = upload_env
        resp = client.post(
            "/api/files",
            files={"file": (evil_name, io.BytesIO(b"payload"), "text/plain")},
        )
        assert resp.status_code == 200, resp.text
        # Landed strictly inside data/raw/local under the safe basename.
        landed = data_root / "raw" / "local" / expected_basename
        assert landed.exists()
        # Resolve and confirm containment — no escape above raw/local.
        raw_local = (data_root / "raw" / "local").resolve()
        assert str(landed.resolve()).startswith(str(raw_local))
        # The on-disk ContentRecord records the safe relative path only.
        from finer.schemas.content import ContentRecord

        cid = resp.json()["contentId"]
        rec = ContentRecord.model_validate_json(
            (data_root / "F0_intake" / "local" / f"{cid}.json").read_text()
        )
        assert rec.raw_path == f"raw/local/{expected_basename}"
        assert ".." not in rec.raw_path

    # These have no usable basename and MUST be rejected.
    @pytest.mark.parametrize("evil_name", ["..", ".", "../../"])
    def test_no_basename_is_rejected(self, client, app, upload_env, evil_name):
        _, pm_db = upload_env
        before = _pm_count(pm_db)
        resp = client.post(
            "/api/files",
            files={"file": (evil_name, io.BytesIO(b"payload"), "text/plain")},
        )
        assert resp.status_code >= 400
        err = resp.json()["error"]
        assert err["code"] == "F0_IO_001"
        assert err["details"]["source_channel"] == "local"
        assert err["details"]["retryable"] is False
        assert _pm_count(pm_db) == before

    def test_no_write_ever_escapes_raw_local(self, client, app, upload_env):
        data_root, _ = upload_env
        # A traversal string whose basename also lacks a valid extension is
        # rejected at the allowlist; the key invariant is that no file named
        # 'passwd' is ever created anywhere under (or above) the data root.
        client.post(
            "/api/files",
            files={"file": ("../../etc/passwd", io.BytesIO(b"x"), "text/plain")},
        )
        assert list(data_root.rglob("passwd")) == []
        assert not (data_root.parent / "etc" / "passwd").exists()


# ---------------------------------------------------------------------------
# Whitelist + size cap — R-28
# ---------------------------------------------------------------------------

class TestUploadWhitelistAndSize:
    def test_disallowed_extension_rejected(self, client, app, upload_env):
        _, pm_db = upload_env
        before = _pm_count(pm_db)
        resp = client.post(
            "/api/files",
            files={"file": ("malware.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        )
        assert resp.status_code >= 400
        err = resp.json()["error"]
        assert err["code"] == "F0_IO_001"
        assert err["details"]["source_channel"] == "local"
        assert "Allowed extensions" in (err["details"].get("fix_hint") or "")
        assert _pm_count(pm_db) == before

    def test_no_extension_rejected(self, client, app, upload_env):
        resp = client.post(
            "/api/files",
            files={"file": ("README", io.BytesIO(b"text"), "text/plain")},
        )
        assert resp.status_code >= 400
        assert resp.json()["error"]["code"] == "F0_IO_001"

    def test_oversize_rejected(self, client, app, upload_env, monkeypatch):
        # Shrink the cap so we don't have to allocate 100MB in the test.
        monkeypatch.setattr("finer.api.routes.files.MAX_UPLOAD_BYTES", 16)
        _, pm_db = upload_env
        before = _pm_count(pm_db)
        resp = client.post(
            "/api/files",
            files={"file": ("big.txt", io.BytesIO(b"x" * 64), "text/plain")},
        )
        assert resp.status_code >= 400
        err = resp.json()["error"]
        assert err["code"] == "F0_IO_001"
        assert err["details"]["retryable"] is False
        assert _pm_count(pm_db) == before

    def test_empty_file_rejected(self, client, app, upload_env):
        resp = client.post(
            "/api/files",
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        )
        assert resp.status_code >= 400
        assert resp.json()["error"]["code"] == "F0_IO_001"

    def test_max_upload_bytes_is_sane(self, client):
        assert MAX_UPLOAD_BYTES == 100 * 1024 * 1024


# ---------------------------------------------------------------------------
# Non-clobbering landing
# ---------------------------------------------------------------------------

class TestUploadNoClobber:
    def test_same_name_twice_keeps_both(self, client, app, upload_env):
        data_root, _ = upload_env
        r1 = client.post(
            "/api/files",
            files={"file": ("dup.txt", io.BytesIO(b"first"), "text/plain")},
        )
        r2 = client.post(
            "/api/files",
            files={"file": ("dup.txt", io.BytesIO(b"second"), "text/plain")},
        )
        assert r1.status_code == 200 and r2.status_code == 200
        local_dir = data_root / "raw" / "local"
        names = sorted(p.name for p in local_dir.iterdir())
        assert "dup.txt" in names
        assert "dup_1.txt" in names
        # Original payload preserved (not overwritten).
        assert (local_dir / "dup.txt").read_bytes() == b"first"
        assert (local_dir / "dup_1.txt").read_bytes() == b"second"
