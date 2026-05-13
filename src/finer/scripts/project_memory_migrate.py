"""CLI migration runner for Project Memory Storage v1.

Commands:
    status  — show applied vs pending migrations with checksums
    upgrade — apply all pending migrations in order
    verify  — check all applied migrations match their stored checksums
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import click

from finer.paths import PROJECT_MEMORY_DB

MIGRATIONS_DIR = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "project_memory"
    / "migrations"
)

_VERSION_RE = re.compile(r"^-- Version:\s*(\d+)\s*$", re.MULTILINE)
_NAME_RE = re.compile(r"^-- Name:\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class MigrationFile:
    version: int
    name: str
    path: Path
    checksum: str


def _compute_checksum(path: Path) -> str:
    """SHA-256 of file content after stripping the checksum line itself."""
    raw = path.read_text(encoding="utf-8")
    # Strip any existing checksum line for idempotent hashing
    stripped = re.sub(r"^-- Checksum:.*\n?", "", raw, flags=re.MULTILINE)
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def discover_migrations() -> list[MigrationFile]:
    """Find and parse all migration SQL files in order."""
    results: list[MigrationFile] = []
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8")

        version_match = _VERSION_RE.search(text)
        name_match = _NAME_RE.search(text)

        if not version_match:
            raise click.ClickException(
                f"Migration {sql_file.name} missing '-- Version: <N>' header"
            )

        version = int(version_match.group(1))
        name = name_match.group(1).strip() if name_match else sql_file.stem
        checksum = _compute_checksum(sql_file)

        results.append(
            MigrationFile(
                version=version,
                name=name,
                path=sql_file,
                checksum=checksum,
            )
        )

    results.sort(key=lambda m: m.version)
    return results


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open SQLite in WAL mode, creating parent dirs if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _applied_versions(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    """Return {version: (name, checksum)} for already-applied migrations."""
    if not _table_exists(conn, "schema_migrations"):
        return {}
    rows = conn.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    return {row[0]: (row[1], row[2]) for row in rows}


def _apply_migration(conn: sqlite3.Connection, migration: MigrationFile) -> int:
    """Apply a single migration and record it. Returns execution_ms."""
    sql = migration.path.read_text(encoding="utf-8")
    start = time.monotonic()
    conn.executescript(sql)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    conn.execute(
        """
        INSERT INTO schema_migrations (version, name, checksum, applied_at, applied_by, execution_ms)
        VALUES (?, ?, ?, datetime('now'), 'migrate_cli', ?)
        """,
        (migration.version, migration.name, migration.checksum, elapsed_ms),
    )
    conn.commit()
    return elapsed_ms


# ── CLI ──────────────────────────────────────────────────────────────────────


@click.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(PROJECT_MEMORY_DB),
    help="Path to finer.project.sqlite3",
)
@click.pass_context
def cli(ctx: click.Context, db_path: str) -> None:
    """Project Memory migration runner."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show applied vs pending migrations."""
    db_path: Path = ctx.obj["db_path"]
    if not db_path.exists():
        click.echo(f"Database not found: {db_path}")
        click.echo("All migrations are pending (run 'upgrade' first).")
        _show_pending(discover_migrations(), applied={})
        return

    conn = _open_db(db_path)
    try:
        applied = _applied_versions(conn)
    finally:
        conn.close()

    all_migrations = discover_migrations()
    applied_count = 0
    pending_count = 0

    click.echo(f"Database: {db_path}")
    click.echo(f"Migration files: {len(all_migrations)}")
    click.echo()

    for m in all_migrations:
        if m.version in applied:
            stored_name, stored_checksum = applied[m.version]
            match = "OK" if stored_checksum == m.checksum else "CHECKSUM MISMATCH"
            click.echo(f"  [applied]  {m.version:03d} {m.name:<40s} {match}")
            applied_count += 1
        else:
            click.echo(f"  [pending]  {m.version:03d} {m.name}")
            pending_count += 1

    click.echo()
    click.echo(f"Applied: {applied_count}, Pending: {pending_count}")


def _show_pending(
    all_migrations: list[MigrationFile],
    applied: dict[int, tuple[str, str]],
) -> None:
    for m in all_migrations:
        if m.version not in applied:
            click.echo(f"  [pending]  {m.version:03d} {m.name}")


@cli.command()
@click.pass_context
def upgrade(ctx: click.Context) -> None:
    """Apply all pending migrations in order."""
    db_path: Path = ctx.obj["db_path"]
    conn = _open_db(db_path)
    try:
        applied = _applied_versions(conn)
        all_migrations = discover_migrations()

        pending = [m for m in all_migrations if m.version not in applied]

        if not pending:
            click.echo("All migrations already applied.")
            return

        # Verify no checksum mismatches in already-applied migrations
        for m in all_migrations:
            if m.version in applied:
                _, stored_checksum = applied[m.version]
                if stored_checksum != m.checksum:
                    raise click.ClickException(
                        f"Checksum mismatch for migration {m.version:03d} ({m.name}). "
                        f"Expected {stored_checksum[:16]}..., got {m.checksum[:16]}... . "
                        f"Applied migrations are immutable."
                    )

        # Verify pending migrations are sequential with no gaps
        expected_version = max(applied.keys(), default=0) + 1
        for m in pending:
            if m.version != expected_version:
                raise click.ClickException(
                    f"Migration version gap: expected {expected_version}, "
                    f"got {m.version}. Cannot apply out of order."
                )
            expected_version += 1

        total_ms = 0
        for m in pending:
            click.echo(f"Applying {m.version:03d} {m.name}...", nl=False)
            elapsed = _apply_migration(conn, m)
            total_ms += elapsed
            click.echo(f" done ({elapsed}ms)")

        click.echo()
        click.echo(f"Applied {len(pending)} migration(s) in {total_ms}ms.")
    finally:
        conn.close()


@cli.command()
@click.pass_context
def verify(ctx: click.Context) -> None:
    """Verify all applied migrations match their stored checksums."""
    db_path: Path = ctx.obj["db_path"]
    if not db_path.exists():
        click.echo(f"Database not found: {db_path}")
        raise SystemExit(1)

    conn = _open_db(db_path)
    try:
        applied = _applied_versions(conn)
    finally:
        conn.close()

    if not applied:
        click.echo("No migrations applied yet.")
        return

    all_migrations = discover_migrations()
    by_version = {m.version: m for m in all_migrations}

    errors: list[str] = []
    for version, (stored_name, stored_checksum) in sorted(applied.items()):
        if version not in by_version:
            errors.append(
                f"  Migration {version:03d} ({stored_name}): "
                f"applied but file missing from migrations directory"
            )
            continue

        m = by_version[version]
        if m.checksum != stored_checksum:
            errors.append(
                f"  Migration {version:03d} ({m.name}): checksum mismatch. "
                f"DB={stored_checksum[:16]}..., file={m.checksum[:16]}..."
            )

    if errors:
        click.echo("Checksum verification FAILED:")
        for err in errors:
            click.echo(err)
        raise SystemExit(1)

    click.echo(f"All {len(applied)} applied migration(s) verified OK.")


if __name__ == "__main__":
    cli()
