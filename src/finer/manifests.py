from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib
import json
import shutil


@dataclass
class ContentManifest:
    content_id: str
    creator_name: str
    source_platform: str
    content_type: str
    published_at: str
    title: str | None
    source_url: str | None
    source_path: str
    language: str | None
    market_scope: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_content_id(creator_id: str, content_type: str, filename: str) -> str:
    digest = hashlib.sha1(f"{creator_id}:{content_type}:{filename}".encode("utf-8")).hexdigest()
    return f"{creator_id}_{content_type}_{digest[:12]}"


def infer_published_at_from_filename(file_path: Path) -> str:
    stem = file_path.stem
    for token in stem.replace("_", "-").split("-"):
        pass
    prefix = stem[:10]
    try:
        dt = datetime.strptime(prefix, "%Y-%m-%d")
        return dt.replace(hour=9, minute=0, second=0).isoformat()
    except ValueError:
        return datetime.now().replace(microsecond=0).isoformat()


def write_manifest(root: Path, manifest: ContentManifest) -> Path:
    manifest_dir = root / "data" / "processed" / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    target = manifest_dir / f"{manifest.content_id}.json"
    target.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def register_file(
    *,
    root: Path,
    creator_id: str,
    creator_name: str,
    content_type: str,
    source_platform: str,
    source_file: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    content_id = build_content_id(creator_id, content_type, source_file.name)
    published_at = infer_published_at_from_filename(source_file)
    extension = source_file.suffix.lower()

    raw_target_dir = root / "data" / "raw" / creator_id / content_type
    raw_target_dir.mkdir(parents=True, exist_ok=True)
    target_file = raw_target_dir / source_file.name

    manifest = ContentManifest(
        content_id=content_id,
        creator_name=creator_name,
        source_platform=source_platform,
        content_type=content_type,
        published_at=published_at,
        title=source_file.stem,
        source_url=None,
        source_path=str(target_file),
        language="zh",
        market_scope=["US", "HK", "A"],
        metadata={
            "original_filename": source_file.name,
            "extension": extension,
            "registered_via": "register-dir",
        },
    )

    if not dry_run:
        if source_file.resolve() != target_file.resolve():
            shutil.copy2(source_file, target_file)
        manifest_path = write_manifest(root, manifest)
    else:
        manifest_path = root / "data" / "processed" / "manifests" / f"{content_id}.json"

    return {
        "content_id": content_id,
        "raw_target": str(target_file),
        "manifest_path": str(manifest_path),
        "dry_run": dry_run,
    }
