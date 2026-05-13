"""Tests for NameLineageService."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from finer.services.project_memory.name_lineage import NameLineageService

_SCHEMA = """
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

CREATE INDEX idx_name_bindings_subject
  ON name_bindings(subject_type, subject_id, namespace, name_kind);

CREATE INDEX idx_name_bindings_primary
  ON name_bindings(subject_type, subject_id, stage, is_primary);
"""


class TestNameLineageService(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.svc = NameLineageService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    # ── bind_name ────────────────────────────────────────────────────

    def test_bind_name_returns_id(self) -> None:
        bid = self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        self.assertTrue(bid.startswith("nb_"))

    def test_bind_name_persists(self) -> None:
        bid = self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        row = self.conn.execute(
            "SELECT * FROM name_bindings WHERE name_binding_id = ?", (bid,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["display_value"], "file.pdf")
        self.assertEqual(row["subject_type"], "content")
        self.assertIsNone(row["valid_to"])

    def test_bind_name_with_optional_fields(self) -> None:
        bid = self.svc.bind_name(
            subject_type="artifact",
            subject_id="a_001",
            namespace="artifact",
            name_kind="materialized_filename",
            display_value="My File",
            normalized_value="my file",
            path_safe_value="my_file",
            stage="f1",
            is_primary=True,
        )
        row = self.conn.execute(
            "SELECT * FROM name_bindings WHERE name_binding_id = ?", (bid,)
        ).fetchone()
        self.assertEqual(row["normalized_value"], "my file")
        self.assertEqual(row["path_safe_value"], "my_file")
        self.assertEqual(row["stage"], "f1")
        self.assertEqual(row["is_primary"], 1)

    # ── set_primary ──────────────────────────────────────────────────

    def test_set_primary_creates_primary(self) -> None:
        bid = self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="Title A",
        )
        row = self.conn.execute(
            "SELECT * FROM name_bindings WHERE name_binding_id = ?", (bid,)
        ).fetchone()
        self.assertEqual(row["is_primary"], 1)
        self.assertIsNone(row["valid_to"])

    def test_set_primary_closes_old_primary(self) -> None:
        self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="Title A",
        )
        bid2 = self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="Title B",
        )
        rows = self.conn.execute(
            "SELECT * FROM name_bindings WHERE subject_id = 'c_001' ORDER BY valid_from"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertIsNotNone(rows[0]["valid_to"])
        self.assertEqual(rows[1]["display_value"], "Title B")
        self.assertIsNone(rows[1]["valid_to"])

    def test_set_primary_stage_scoped(self) -> None:
        self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="F1 Title",
            stage="f1",
        )
        self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="F2 Title",
            stage="f2",
        )
        rows = self.conn.execute(
            "SELECT * FROM name_bindings WHERE subject_id = 'c_001'"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        # Both should still be current (different stages)
        self.assertIsNone(rows[0]["valid_to"])
        self.assertIsNone(rows[1]["valid_to"])

    # ── close_binding ────────────────────────────────────────────────

    def test_close_binding(self) -> None:
        bid = self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        self.svc.close_binding(bid)
        row = self.conn.execute(
            "SELECT valid_to FROM name_bindings WHERE name_binding_id = ?", (bid,)
        ).fetchone()
        self.assertIsNotNone(row["valid_to"])

    # ── rename ───────────────────────────────────────────────────────

    def test_rename_closes_old_and_creates_new(self) -> None:
        self.svc.rename(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            new_display_value="New Title",
        )
        rows = self.conn.execute(
            "SELECT * FROM name_bindings WHERE subject_id = 'c_001'"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["display_value"], "New Title")

    def test_rename_with_existing_primary(self) -> None:
        self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="Old Title",
        )
        self.svc.rename(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            new_display_value="New Title",
        )
        rows = self.conn.execute(
            "SELECT * FROM name_bindings WHERE subject_id = 'c_001' ORDER BY valid_from"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertIsNotNone(rows[0]["valid_to"])
        self.assertEqual(rows[1]["display_value"], "New Title")
        self.assertIsNone(rows[1]["valid_to"])

    # ── get_names ────────────────────────────────────────────────────

    def test_get_names_returns_current_only(self) -> None:
        bid = self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        self.svc.close_binding(bid)
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="new.pdf",
        )
        names = self.svc.get_names("content", "c_001")
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0]["display_value"], "new.pdf")

    def test_get_names_filters_by_namespace(self) -> None:
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="Title",
        )
        names = self.svc.get_names("content", "c_001", namespace="source")
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0]["namespace"], "source")

    # ── get_primary_name ─────────────────────────────────────────────

    def test_get_primary_name_returns_display_value(self) -> None:
        self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="Main Title",
        )
        self.assertEqual(
            self.svc.get_primary_name("content", "c_001"), "Main Title"
        )

    def test_get_primary_name_returns_none_when_no_primary(self) -> None:
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
            is_primary=False,
        )
        self.assertIsNone(self.svc.get_primary_name("content", "c_001"))

    def test_get_primary_name_scoped(self) -> None:
        self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="F1 Title",
            stage="f1",
        )
        self.assertEqual(
            self.svc.get_primary_name("content", "c_001", stage="f1"),
            "F1 Title",
        )
        self.assertIsNone(
            self.svc.get_primary_name("content", "c_001", stage="f2")
        )

    # ── get_name_history ─────────────────────────────────────────────

    def test_get_name_history_includes_closed(self) -> None:
        self.svc.rename(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            new_display_value="V1",
        )
        self.svc.rename(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            new_display_value="V2",
        )
        history = self.svc.get_name_history(
            "content", "c_001", "f1", "envelope_title"
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["display_value"], "V1")
        self.assertIsNotNone(history[0]["valid_to"])
        self.assertEqual(history[1]["display_value"], "V2")
        self.assertIsNone(history[1]["valid_to"])

    # ── get_names_for_content ────────────────────────────────────────

    def test_get_names_for_content_groups_by_namespace_kind(self) -> None:
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            display_value="Title",
        )
        result = self.svc.get_names_for_content("c_001")
        self.assertIn("source.original_filename", result)
        self.assertIn("f1.envelope_title", result)
        self.assertEqual(len(result["source.original_filename"]), 1)

    def test_get_names_for_content_excludes_closed(self) -> None:
        bid = self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="old.pdf",
        )
        self.svc.close_binding(bid)
        result = self.svc.get_names_for_content("c_001")
        self.assertEqual(len(result), 0)

    # ── search_by_name ───────────────────────────────────────────────

    def test_search_by_name_exact_match(self) -> None:
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="report.pdf",
        )
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_002",
            namespace="source",
            name_kind="original_filename",
            display_value="report.pdf",
        )
        results = self.svc.search_by_name("report.pdf")
        self.assertEqual(len(results), 2)

    def test_search_by_name_filters_subject_type(self) -> None:
        self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        self.svc.bind_name(
            subject_type="artifact",
            subject_id="a_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        results = self.svc.search_by_name("file.pdf", subject_type="content")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["subject_type"], "content")

    def test_search_by_name_excludes_closed(self) -> None:
        bid = self.svc.bind_name(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        self.svc.close_binding(bid)
        results = self.svc.search_by_name("file.pdf")
        self.assertEqual(len(results), 0)

    # ── Rules validation ─────────────────────────────────────────────

    def test_historical_bindings_not_overwritten(self) -> None:
        """Verify that renames preserve history."""
        self.svc.rename(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            new_display_value="V1",
        )
        self.svc.rename(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            new_display_value="V2",
        )
        self.svc.rename(
            subject_type="content",
            subject_id="c_001",
            namespace="f1",
            name_kind="envelope_title",
            new_display_value="V3",
        )
        # All 3 bindings should exist
        rows = self.conn.execute(
            "SELECT * FROM name_bindings WHERE subject_id = 'c_001'"
        ).fetchall()
        self.assertEqual(len(rows), 3)
        # First two should be closed
        self.assertIsNotNone(rows[0]["valid_to"])
        self.assertIsNotNone(rows[1]["valid_to"])
        # Last one should be current
        self.assertIsNone(rows[2]["valid_to"])
        # IDs should all be different
        ids = {r["name_binding_id"] for r in rows}
        self.assertEqual(len(ids), 3)

    def test_every_content_has_primary_display_name(self) -> None:
        """Rule: every content_id must have at least one primary display name."""
        self.svc.set_primary(
            subject_type="content",
            subject_id="c_001",
            namespace="source",
            name_kind="original_filename",
            display_value="file.pdf",
        )
        primary = self.svc.get_primary_name("content", "c_001")
        self.assertIsNotNone(primary)
        self.assertEqual(primary, "file.pdf")


class TestCommitPersistence(unittest.TestCase):
    """Verify that write methods actually commit data (not just in-transaction visibility)."""

    def _create_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        return conn

    def test_bind_name_persists_across_connections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite3"
            conn1 = self._create_db(db_path)
            svc = NameLineageService(conn1)
            svc.bind_name("content", "c_001", "source", "original_filename", "file.pdf")
            conn1.close()

            # Open a new connection — data must be visible
            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row
            row = conn2.execute(
                "SELECT * FROM name_bindings WHERE subject_id = 'c_001'"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["display_value"], "file.pdf")
            conn2.close()

    def test_close_binding_persists_across_connections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite3"
            conn1 = self._create_db(db_path)
            svc = NameLineageService(conn1)
            bid = svc.bind_name("content", "c_001", "source", "original_filename", "old.pdf")
            svc.close_binding(bid)
            conn1.close()

            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row
            row = conn2.execute(
                "SELECT * FROM name_bindings WHERE name_binding_id = ?", (bid,)
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertIsNotNone(row["valid_to"])
            conn2.close()

    def test_set_primary_persists_across_connections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.sqlite3"
            conn1 = self._create_db(db_path)
            svc = NameLineageService(conn1)
            svc.set_primary("content", "c_001", "source", "original_filename", "new.pdf")
            conn1.close()

            conn2 = sqlite3.connect(str(db_path))
            conn2.row_factory = sqlite3.Row
            row = conn2.execute(
                "SELECT display_value FROM name_bindings "
                "WHERE subject_id = 'c_001' AND is_primary = 1 AND valid_to IS NULL"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["display_value"], "new.pdf")
            conn2.close()


if __name__ == "__main__":
    unittest.main()
