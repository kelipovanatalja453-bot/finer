from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING
import hashlib
import json
import shutil

if TYPE_CHECKING:
    from finer.schemas.content import ContentRecord


@dataclass
class ContentManifest:
    """F0 canonical manifest — dataclass mirror of ContentRecord for storage/serialization."""

    # --- identity ---
    content_id: str
    # --- source classification ---
    source_type: str                          # feishu_chat | bilibili_video | wechat_article | manual_upload | nlm_note
    source_platform: str
    # --- creator ---
    creator_id: str | None
    creator_name: str | None
    # --- timestamps (ISO strings) ---
    published_at: str | None                  # ISO format, may be None
    collected_at: str                         # ISO format
    # --- content metadata ---
    title: str | None
    raw_path: str
    file_type: str                            # chat_log | image | pdf | doc | audio | video | text
    metadata: dict[str, Any]
    # --- optional linkage ---
    source_url: str | None
    external_source_id: str | None
    dedupe_fingerprint: str | None
    # --- backward-compatible optional fields ---
    overall_summary: str | None = None
    language: str | None = None
    market_scope: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_record(cls, record: ContentRecord) -> ContentManifest:
        """Create a ContentManifest from a pydantic ContentRecord."""
        return cls(
            content_id=record.content_id,
            source_type=record.source_type,
            source_platform=record.source_platform,
            creator_id=record.creator_id,
            creator_name=record.creator_name,
            published_at=record.published_at.isoformat() if record.published_at else None,
            collected_at=record.collected_at.isoformat(),
            title=record.title,
            raw_path=record.raw_path,
            file_type=record.file_type,
            metadata=dict(record.metadata),
            source_url=record.source_url,
            external_source_id=record.external_source_id,
            dedupe_fingerprint=record.dedupe_fingerprint,
            overall_summary=record.overall_summary,
            language=record.language,
            market_scope=list(record.market_scope) if record.market_scope else None,
        )


def build_content_id(creator_id: str, content_type: str, filename: str) -> str:
    digest = hashlib.sha1(f"{creator_id}:{content_type}:{filename}".encode("utf-8")).hexdigest()
    return f"{creator_id}_{content_type}_{digest[:12]}"


def infer_published_at_from_filename(file_path: Path) -> str:
    stem = file_path.stem
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


_EXTENSION_TO_FILE_TYPE: dict[str, str] = {
    ".txt": "text", ".md": "text", ".csv": "text",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
    ".pdf": "pdf",
    ".doc": "doc", ".docx": "doc",
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".aac": "audio",
    ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video", ".webm": "video",
    ".json": "chat_log", ".html": "chat_log",
}


def _infer_file_type(extension: str) -> str:
    """Map a file extension to the canonical file_type enum value."""
    return _EXTENSION_TO_FILE_TYPE.get(extension.lower(), "text")


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
        source_type=content_type,
        source_platform=source_platform,
        creator_id=creator_id,
        creator_name=creator_name,
        published_at=published_at,
        collected_at=datetime.utcnow().replace(microsecond=0).isoformat(),
        title=source_file.stem,
        raw_path=str(target_file),
        file_type=_infer_file_type(extension),
        metadata={
            "original_filename": source_file.name,
            "extension": extension,
            "registered_via": "register-dir",
        },
        source_url=None,
        external_source_id=None,
        dedupe_fingerprint=None,
        language="zh",
        market_scope=["US", "HK", "A"],
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
