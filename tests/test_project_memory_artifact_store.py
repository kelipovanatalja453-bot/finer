"""Tests for ArtifactStore — artifact CRUD, canonicality, and lineage edges."""

from __future__ import annotations

import sqlite3

import pytest

from finer.services.project_memory.artifact_store import (
    ArtifactStore,
    VALID_RELATIONS,
    VALID_STAGES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(
        """
        CREATE TABLE artifacts (
            artifact_id TEXT PRIMARY KEY,
            content_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            role TEXT NOT NULL,
            object_id TEXT NOT NULL,
            manifest_id TEXT,
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
        """
    )
    return c


@pytest.fixture()
def store(conn: sqlite3.Connection) -> ArtifactStore:
    return ArtifactStore(conn)


# Helper to insert a minimal artifact row for edge tests.
def _insert_artifact(conn: sqlite3.Connection, artifact_id: str, content_id: str = "cnt_1") -> None:
    conn.execute(
        """
        INSERT INTO artifacts
            (artifact_id, content_id, stage, artifact_type, role, object_id,
             artifact_version, is_canonical, created_at)
        VALUES (?, ?, 'F0', 'raw', 'input', 'obj_1', 1, 0, '2026-01-01T00:00:00Z')
        """,
        (artifact_id, content_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# create_artifact
# ---------------------------------------------------------------------------


class TestCreateArtifact:
    def test_returns_artifact_id(self, store: ArtifactStore) -> None:
        aid = store.create_artifact(
            content_id="cnt_1",
            stage="F0",
            artifact_type="raw",
            role="input",
            object_id="sha256:abc123",
        )
        assert aid.startswith("art_")

    def test_stores_all_fields(self, store: ArtifactStore) -> None:
        aid = store.create_artifact(
            content_id="cnt_1",
            stage="F1",
            artifact_type="envelope",
            role="canonical",
            object_id="sha256:def",
            manifest_id="m_1",
            schema_name="ContentEnvelope",
            schema_version="1.0.0",
            run_id="run_1",
            metadata={"key": "value"},
        )
        row = store.get_artifact(aid)
        assert row is not None
        assert row["content_id"] == "cnt_1"
        assert row["stage"] == "F1"
        assert row["artifact_type"] == "envelope"
        assert row["role"] == "canonical"
        assert row["object_id"] == "sha256:def"
        assert row["manifest_id"] == "m_1"
        assert row["schema_name"] == "ContentEnvelope"
        assert row["schema_version"] == "1.0.0"
        assert row["run_id"] == "run_1"
        assert row["metadata_json"] == '{"key": "value"}'

    def test_version_auto_increments(self, store: ArtifactStore) -> None:
        aid1 = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        aid2 = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o2"
        )
        assert store.get_artifact(aid1)["artifact_version"] == 1
        assert store.get_artifact(aid2)["artifact_version"] == 2

    def test_version_independent_per_type(self, store: ArtifactStore) -> None:
        aid_raw = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        aid_envelope = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="envelope", role="output", object_id="o2"
        )
        assert store.get_artifact(aid_raw)["artifact_version"] == 1
        assert store.get_artifact(aid_envelope)["artifact_version"] == 1

    def test_new_artifact_is_not_canonical(self, store: ArtifactStore) -> None:
        aid = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        assert store.get_artifact(aid)["is_canonical"] == 0

    def test_invalid_stage_raises(self, store: ArtifactStore) -> None:
        with pytest.raises(ValueError, match="Invalid stage"):
            store.create_artifact(
                content_id="cnt_1", stage="L0", artifact_type="raw", role="input", object_id="o1"
            )

    def test_all_valid_stages_accepted(self, store: ArtifactStore) -> None:
        for stage in VALID_STAGES:
            aid = store.create_artifact(
                content_id="cnt_1", stage=stage, artifact_type="t", role="r", object_id="o"
            )
            assert store.get_artifact(aid)["stage"] == stage


# ---------------------------------------------------------------------------
# get_artifact
# ---------------------------------------------------------------------------


class TestGetArtifact:
    def test_returns_none_for_missing(self, store: ArtifactStore) -> None:
        assert store.get_artifact("art_nonexistent") is None


# ---------------------------------------------------------------------------
# get_canonical_artifact
# ---------------------------------------------------------------------------


class TestGetCanonicalArtifact:
    def test_returns_none_when_no_canonical(self, store: ArtifactStore) -> None:
        store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        assert store.get_canonical_artifact("cnt_1", "F0") is None

    def test_returns_canonical(self, store: ArtifactStore) -> None:
        aid = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        store.mark_canonical(aid)
        row = store.get_canonical_artifact("cnt_1", "F0")
        assert row is not None
        assert row["artifact_id"] == aid

    def test_filters_by_artifact_type(self, store: ArtifactStore) -> None:
        aid1 = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        aid2 = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="envelope", role="output", object_id="o2"
        )
        store.mark_canonical(aid1)
        store.mark_canonical(aid2)

        row = store.get_canonical_artifact("cnt_1", "F0", artifact_type="raw")
        assert row["artifact_id"] == aid1

        row = store.get_canonical_artifact("cnt_1", "F0", artifact_type="envelope")
        assert row["artifact_id"] == aid2


# ---------------------------------------------------------------------------
# list_artifacts_for_content
# ---------------------------------------------------------------------------


class TestListArtifacts:
    def test_lists_all(self, store: ArtifactStore) -> None:
        store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        store.create_artifact(
            content_id="cnt_1", stage="F1", artifact_type="envelope", role="output", object_id="o2"
        )
        rows = store.list_artifacts_for_content("cnt_1")
        assert len(rows) == 2

    def test_filters_by_stage(self, store: ArtifactStore) -> None:
        store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        store.create_artifact(
            content_id="cnt_1", stage="F1", artifact_type="envelope", role="output", object_id="o2"
        )
        rows = store.list_artifacts_for_content("cnt_1", stage="F0")
        assert len(rows) == 1
        assert rows[0]["stage"] == "F0"

    def test_empty_for_unknown_content(self, store: ArtifactStore) -> None:
        assert store.list_artifacts_for_content("cnt_unknown") == []


# ---------------------------------------------------------------------------
# mark_canonical / mark_non_canonical
# ---------------------------------------------------------------------------


class TestCanonicality:
    def test_mark_canonical(self, store: ArtifactStore) -> None:
        aid = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        store.mark_canonical(aid)
        assert store.get_artifact(aid)["is_canonical"] == 1

    def test_mark_canonical_clears_siblings(self, store: ArtifactStore) -> None:
        aid1 = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        aid2 = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o2"
        )
        store.mark_canonical(aid1)
        store.mark_canonical(aid2)

        assert store.get_artifact(aid1)["is_canonical"] == 0
        assert store.get_artifact(aid2)["is_canonical"] == 1

    def test_mark_canonical_only_clears_same_type(self, store: ArtifactStore) -> None:
        aid_raw = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        aid_env = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="envelope", role="output", object_id="o2"
        )
        store.mark_canonical(aid_raw)
        store.mark_canonical(aid_env)

        # Both should still be canonical because they have different artifact_type.
        assert store.get_artifact(aid_raw)["is_canonical"] == 1
        assert store.get_artifact(aid_env)["is_canonical"] == 1

    def test_mark_non_canonical(self, store: ArtifactStore) -> None:
        aid = store.create_artifact(
            content_id="cnt_1", stage="F0", artifact_type="raw", role="input", object_id="o1"
        )
        store.mark_canonical(aid)
        store.mark_non_canonical(aid)
        assert store.get_artifact(aid)["is_canonical"] == 0

    def test_mark_canonical_nonexistent_raises(self, store: ArtifactStore) -> None:
        with pytest.raises(ValueError, match="Artifact not found"):
            store.mark_canonical("art_ghost")


# ---------------------------------------------------------------------------
# Artifact edges
# ---------------------------------------------------------------------------


class TestEdges:
    def _setup_two_artifacts(self, conn: sqlite3.Connection) -> tuple[str, str]:
        a1, a2 = "art_aaa", "art_bbb"
        _insert_artifact(conn, a1)
        _insert_artifact(conn, a2)
        return a1, a2

    def test_add_edge_and_query(self, store: ArtifactStore, conn: sqlite3.Connection) -> None:
        p, c = self._setup_two_artifacts(conn)
        store.add_edge(p, c, "derived_from")
        out = store.get_edges_from(p)
        assert len(out) == 1
        assert out[0]["child_artifact_id"] == c
        assert out[0]["relation"] == "derived_from"

        incoming = store.get_edges_to(c)
        assert len(incoming) == 1
        assert incoming[0]["parent_artifact_id"] == p

    def test_add_edge_deduplicates(self, store: ArtifactStore, conn: sqlite3.Connection) -> None:
        p, c = self._setup_two_artifacts(conn)
        store.add_edge(p, c, "standardizes")
        store.add_edge(p, c, "standardizes")  # duplicate
        assert len(store.get_edges_from(p)) == 1

    def test_invalid_relation_raises(self, store: ArtifactStore, conn: sqlite3.Connection) -> None:
        p, c = self._setup_two_artifacts(conn)
        with pytest.raises(ValueError, match="Invalid relation"):
            store.add_edge(p, c, "not_a_relation")

    def test_all_valid_relations_accepted(
        self, store: ArtifactStore, conn: sqlite3.Connection
    ) -> None:
        _insert_artifact(conn, "art_p")
        _insert_artifact(conn, "art_c")
        for rel in VALID_RELATIONS:
            store.add_edge("art_p", "art_c", rel)
        assert len(store.get_edges_from("art_p")) == len(VALID_RELATIONS)

    def test_get_edges_from_empty(self, store: ArtifactStore) -> None:
        assert store.get_edges_from("art_none") == []

    def test_get_edges_to_empty(self, store: ArtifactStore) -> None:
        assert store.get_edges_to("art_none") == []


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


class TestLineage:
    def test_direct_parent(self, store: ArtifactStore, conn: sqlite3.Connection) -> None:
        _insert_artifact(conn, "art_a")
        _insert_artifact(conn, "art_b")
        store.add_edge("art_a", "art_b", "derived_from")
        assert store.get_lineage("art_b") == ["art_a"]

    def test_transitive_chain(self, store: ArtifactStore, conn: sqlite3.Connection) -> None:
        # a -> b -> c
        for aid in ("art_a", "art_b", "art_c"):
            _insert_artifact(conn, aid)
        store.add_edge("art_a", "art_b", "derived_from")
        store.add_edge("art_b", "art_c", "derived_from")

        lineage = store.get_lineage("art_c")
        assert "art_b" in lineage
        assert "art_a" in lineage

    def test_diamond_lineage(self, store: ArtifactStore, conn: sqlite3.Connection) -> None:
        # a -> c, b -> c
        for aid in ("art_a", "art_b", "art_c"):
            _insert_artifact(conn, aid)
        store.add_edge("art_a", "art_c", "derived_from")
        store.add_edge("art_b", "art_c", "derived_from")

        lineage = store.get_lineage("art_c")
        assert set(lineage) == {"art_a", "art_b"}

    def test_no_parents_returns_empty(self, store: ArtifactStore, conn: sqlite3.Connection) -> None:
        _insert_artifact(conn, "art_root")
        assert store.get_lineage("art_root") == []

    def test_unknown_artifact_returns_empty(self, store: ArtifactStore) -> None:
        assert store.get_lineage("art_ghost") == []
