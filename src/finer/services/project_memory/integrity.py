"""Integrity checker for Project Memory — validates referential and structural invariants."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class IntegrityIssue:
    """A single integrity violation found by a check."""

    check_name: str
    severity: Severity
    message: str
    affected_ids: list[str] = field(default_factory=list)


@dataclass
class IntegrityReport:
    """Aggregated result of all integrity checks."""

    issues: list[IntegrityIssue] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)


class IntegrityChecker:
    """Read-only integrity validator for a Project Memory SQLite database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all_checks(self) -> IntegrityReport:
        """Run every integrity check and return an aggregated report."""
        report = IntegrityReport()
        checks = [
            self.check_content_identity_consistency,
            self.check_source_link_consistency,
            self.check_artifact_payload_consistency,
            self.check_primary_name_consistency,
            self.check_asset_index_consistency,
            self.check_topic_member_consistency,
            self.check_stage_consistency,
            self.check_name_binding_consistency,
            self.check_no_legacy_stages,
            self.check_asset_index_count_match,
            self.check_fts_rebuildable,
        ]
        for check in checks:
            report.issues.extend(check())
        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_content_identity_consistency(self) -> list[IntegrityIssue]:
        """No content row without identity."""
        rows = self._conn.execute(
            "SELECT content_id FROM contents "
            "WHERE content_id NOT IN (SELECT content_id FROM content_identities)"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            return [IntegrityIssue(
                check_name="content_identity_consistency",
                severity=Severity.ERROR,
                message=f"{len(ids)} content row(s) without identity",
                affected_ids=ids,
            )]
        return []

    def check_source_link_consistency(self) -> list[IntegrityIssue]:
        """No content identity without any source link."""
        rows = self._conn.execute(
            "SELECT content_id FROM content_identities "
            "WHERE content_id NOT IN (SELECT content_id FROM source_content_links)"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            return [IntegrityIssue(
                check_name="source_link_consistency",
                severity=Severity.WARNING,
                message=f"{len(ids)} content identity(ies) without any source link",
                affected_ids=ids,
            )]
        return []

    def check_artifact_payload_consistency(self) -> list[IntegrityIssue]:
        """No canonical artifact without object payload."""
        rows = self._conn.execute(
            "SELECT artifact_id FROM artifacts "
            "WHERE is_canonical = 1 "
            "AND object_id NOT IN (SELECT object_id FROM storage_objects)"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            return [IntegrityIssue(
                check_name="artifact_payload_consistency",
                severity=Severity.ERROR,
                message=f"{len(ids)} canonical artifact(s) without object payload",
                affected_ids=ids,
            )]
        return []

    def check_primary_name_consistency(self) -> list[IntegrityIssue]:
        """No content without primary display name."""
        rows = self._conn.execute(
            "SELECT c.content_id "
            "FROM contents c "
            "LEFT JOIN name_bindings n "
            "  ON n.subject_type = 'content' "
            " AND n.subject_id = c.content_id "
            " AND n.is_primary = 1 "
            " AND n.valid_to IS NULL "
            "WHERE n.name_binding_id IS NULL"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            return [IntegrityIssue(
                check_name="primary_name_consistency",
                severity=Severity.WARNING,
                message=f"{len(ids)} content item(s) without primary display name",
                affected_ids=ids,
            )]
        return []

    def check_asset_index_consistency(self) -> list[IntegrityIssue]:
        """No visible frontend asset without a content row."""
        rows = self._conn.execute(
            "SELECT asset_id FROM asset_index "
            "WHERE content_id NOT IN (SELECT content_id FROM contents)"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            return [IntegrityIssue(
                check_name="asset_index_consistency",
                severity=Severity.ERROR,
                message=f"{len(ids)} asset(s) referencing missing content",
                affected_ids=ids,
            )]
        return []

    def check_topic_member_consistency(self) -> list[IntegrityIssue]:
        """No F1 topic member pointing at a missing block."""
        rows = self._conn.execute(
            "SELECT topic_block_id, block_id FROM topic_block_members "
            "WHERE block_id NOT IN (SELECT block_id FROM content_blocks)"
        ).fetchall()
        if rows:
            ids = [f"{r[0]}->{r[1]}" for r in rows]
            return [IntegrityIssue(
                check_name="topic_member_consistency",
                severity=Severity.ERROR,
                message=f"{len(ids)} topic member(s) pointing at missing blocks",
                affected_ids=ids,
            )]
        return []

    def check_stage_consistency(self) -> list[IntegrityIssue]:
        """Every F1 canonical artifact has source_record_id reachable through contents."""
        issues: list[IntegrityIssue] = []
        rows = self._conn.execute(
            "SELECT a.artifact_id, a.content_id "
            "FROM artifacts a "
            "JOIN contents c ON c.content_id = a.content_id "
            "WHERE a.stage = 'F1' AND a.is_canonical = 1 "
            "AND c.primary_source_record_id IS NULL"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            issues.append(IntegrityIssue(
                check_name="stage_consistency",
                severity=Severity.WARNING,
                message=f"{len(ids)} F1 canonical artifact(s) without reachable source_record_id",
                affected_ids=ids,
            ))
        return issues

    def check_name_binding_consistency(self) -> list[IntegrityIssue]:
        """Every F1 materialized artifact has name_bindings."""
        rows = self._conn.execute(
            "SELECT a.artifact_id "
            "FROM artifacts a "
            "WHERE a.stage = 'F1' AND a.is_canonical = 1 "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM name_bindings nb "
            "  WHERE nb.subject_type = 'artifact' "
            "  AND nb.subject_id = a.artifact_id "
            "  AND nb.valid_to IS NULL"
            ")"
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            return [IntegrityIssue(
                check_name="name_binding_consistency",
                severity=Severity.WARNING,
                message=f"{len(ids)} F1 materialized artifact(s) without name_bindings",
                affected_ids=ids,
            )]
        return []

    def check_no_legacy_stages(self) -> list[IntegrityIssue]:
        """No new row uses L0-L8 or V0-V6 as canonical stage."""
        legacy_stages = [
            "L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8",
            "V0", "V1", "V2", "V3", "V4", "V5", "V6",
        ]
        placeholders = ",".join(["?"] * len(legacy_stages))

        issues: list[IntegrityIssue] = []

        # Check artifacts
        rows = self._conn.execute(
            f"SELECT artifact_id, stage FROM artifacts WHERE stage IN ({placeholders})",
            legacy_stages,
        ).fetchall()
        if rows:
            ids = [f"{r[0]}({r[1]})" for r in rows]
            issues.append(IntegrityIssue(
                check_name="no_legacy_stages",
                severity=Severity.ERROR,
                message=f"{len(ids)} artifact(s) using legacy stage names",
                affected_ids=ids,
            ))

        # Check stage_status
        rows = self._conn.execute(
            f"SELECT content_id, stage FROM stage_status WHERE stage IN ({placeholders})",
            legacy_stages,
        ).fetchall()
        if rows:
            ids = [f"{r[0]}({r[1]})" for r in rows]
            issues.append(IntegrityIssue(
                check_name="no_legacy_stages",
                severity=Severity.ERROR,
                message=f"{len(ids)} stage_status row(s) using legacy stage names",
                affected_ids=ids,
            ))

        # Check asset_index
        rows = self._conn.execute(
            f"SELECT asset_id FROM asset_index WHERE stage IN ({placeholders})",
            legacy_stages,
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            issues.append(IntegrityIssue(
                check_name="no_legacy_stages",
                severity=Severity.ERROR,
                message=f"{len(ids)} asset_index row(s) using legacy stage names",
                affected_ids=ids,
            ))

        return issues

    def check_asset_index_count_match(self) -> list[IntegrityIssue]:
        """asset_index counts match stage_status for ready/partial rows."""
        ss_rows = self._conn.execute(
            "SELECT stage, COUNT(*) FROM stage_status "
            "WHERE status IN ('ready', 'partial') GROUP BY stage"
        ).fetchall()
        ai_rows = self._conn.execute(
            "SELECT stage, COUNT(*) FROM asset_index "
            "WHERE status IN ('ready', 'partial') GROUP BY stage"
        ).fetchall()

        ss_map: dict[str, int] = {r[0]: r[1] for r in ss_rows}
        ai_map: dict[str, int] = {r[0]: r[1] for r in ai_rows}

        all_stages = sorted(set(ss_map) | set(ai_map))
        mismatches: list[str] = []
        for stage in all_stages:
            ss_count = ss_map.get(stage, 0)
            ai_count = ai_map.get(stage, 0)
            if ss_count != ai_count:
                mismatches.append(f"{stage}: stage_status={ss_count} asset_index={ai_count}")

        if mismatches:
            return [IntegrityIssue(
                check_name="asset_index_count_match",
                severity=Severity.WARNING,
                message=f"Count mismatch: {'; '.join(mismatches)}",
                affected_ids=mismatches,
            )]
        return []

    def check_fts_rebuildable(self) -> list[IntegrityIssue]:
        """asset_index_fts can be rebuilt from asset_index."""
        try:
            # Check if FTS table exists
            row = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_index_fts'"
            ).fetchone()
            if row is None:
                return [IntegrityIssue(
                    check_name="fts_rebuildable",
                    severity=Severity.INFO,
                    message="asset_index_fts does not exist — can be rebuilt",
                )]

            # Count FTS rows vs asset_index rows
            fts_count = self._conn.execute(
                "SELECT COUNT(*) FROM asset_index_fts"
            ).fetchone()[0]
            ai_count = self._conn.execute(
                "SELECT COUNT(*) FROM asset_index"
            ).fetchone()[0]

            if fts_count != ai_count:
                return [IntegrityIssue(
                    check_name="fts_rebuildable",
                    severity=Severity.WARNING,
                    message=f"FTS row count ({fts_count}) != asset_index count ({ai_count})",
                    affected_ids=[f"fts={fts_count}", f"asset_index={ai_count}"],
                )]
        except sqlite3.OperationalError:
            return [IntegrityIssue(
                check_name="fts_rebuildable",
                severity=Severity.INFO,
                message="asset_index_fts is not accessible — rebuild recommended",
            )]
        return []
