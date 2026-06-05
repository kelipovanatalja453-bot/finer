"""WeChat Channels (视频号) F0 adapter — download + import pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx

from finer.schemas.content import ContentRecord
from finer.schemas.import_receipt import ImportReceipt

logger = logging.getLogger(__name__)


# --- WeChat Channels F0 intake ---

WECHAT_CHANNELS_SOURCE_KIND = "wechat_channels_video"

# Name of the WeChat Channels downloader binary as it appears on PATH.
WX_CHANNELS_DOWNLOAD_BINARY_NAME = "wx_video_download"
# Environment variable that pins an explicit downloader binary path.
WX_CHANNELS_DOWNLOAD_BIN_ENV = "WX_CHANNELS_DOWNLOAD_BIN"


class WeChatChannelsDownloaderUnavailable(RuntimeError):
    """Raised when the WeChat Channels downloader binary cannot be located/used.

    This is an *external dependency* failure (the local downloader service/CLI
    is not installed or not reachable), NOT an invalid-input failure. The API
    layer maps it to a retryable ``F0_EXT_001`` rather than ``F0_IN_001``.
    """


def _vendored_wx_channels_download_bin(root: Path) -> Path:
    """Last-resort vendored binary path bundled in the repo."""
    return root / "scripts" / "wx_channels_download" / WX_CHANNELS_DOWNLOAD_BINARY_NAME


def resolve_wx_channels_download_bin(root: Path) -> Path | None:
    """Resolve the WeChat Channels downloader binary via external-install order.

    Resolution order (first hit wins):

    1. ``shutil.which("wx_video_download")`` — a system/PATH install.
    2. ``$WX_CHANNELS_DOWNLOAD_BIN`` — explicit env override.
    3. ``WeChatServiceConfig.channels_downloader_bin`` — configs/wechat.yaml.
    4. Vendored copy under ``scripts/wx_channels_download/`` — last resort.

    Returns the resolved path, or ``None`` if nothing is found (the caller then
    raises :class:`WeChatChannelsDownloaderUnavailable`). This function does not
    verify the file is executable beyond ``which``'s own check; existence of an
    explicit/vendored path is validated at download time.
    """
    on_path = shutil.which(WX_CHANNELS_DOWNLOAD_BINARY_NAME)
    if on_path:
        return Path(on_path)

    env_value = os.environ.get(WX_CHANNELS_DOWNLOAD_BIN_ENV)
    if env_value:
        return Path(env_value).expanduser()

    try:
        from finer.config import load_wechat_service_config

        configured = load_wechat_service_config(root).channels_downloader_bin
    except Exception:  # pragma: no cover - config load is best-effort
        configured = None
    if configured:
        return Path(configured).expanduser()

    vendored = _vendored_wx_channels_download_bin(root)
    if vendored.exists():
        return vendored

    return None


@dataclass(frozen=True)
class WeChatChannelsArtifacts:
    """Raw F0 artifacts persisted for one WeChat Channels video."""

    raw_video_path: Path
    raw_profile_path: Path
    video_sha256: str
    profile_sha256: str


@dataclass(frozen=True)
class WeChatChannelsImportResult:
    """Result of importing one WeChat Channels video into canonical F0 storage."""

    import_run_id: str
    status: str
    content_record: ContentRecord
    record_path: Path
    receipt_path: Path
    artifacts: WeChatChannelsArtifacts
    f0_dir: Path


class WeChatChannelsDownloadClient:
    """Thin client for scripts/wx_channels_download local service and CLI."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:2022",
        downloader_bin: Path | None = None,
        timeout_seconds: int = 300,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.downloader_bin = downloader_bin
        self.timeout_seconds = timeout_seconds

    def get_feed_profile(self, url: str) -> dict[str, Any]:
        """Fetch raw profile JSON for a WeChat Channels shared/feed URL."""
        endpoint = (
            "/api/channels/shared_feed/profile"
            if "weixin.qq.com/sph/" in url or "finder-preview" in url
            else "/api/channels/feed/profile"
        )
        request_url = f"{self.base_url}{endpoint}?url={quote_plus(url)}"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(request_url)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as e:
            raise TimeoutError("WeChat Channels downloader API timed out") from e
        except httpx.HTTPError as e:
            raise ConnectionError(f"WeChat Channels downloader API unavailable: {e}") from e

        if payload.get("code") != 0:
            raise ValueError(payload.get("msg") or "WeChat Channels downloader returned an error")
        return payload

    def download_media(
        self,
        *,
        media_url: str,
        decode_key: str | int | None,
        filename: str,
    ) -> Path:
        """Download one video through the bundled wx_channels_download CLI."""
        if not self.downloader_bin:
            raise WeChatChannelsDownloaderUnavailable(
                "wx_video_download binary not found: install it on PATH, set "
                f"{WX_CHANNELS_DOWNLOAD_BIN_ENV}, configure channels_downloader_bin, "
                "or provide the vendored copy under scripts/wx_channels_download/"
            )
        if not self.downloader_bin.exists():
            raise WeChatChannelsDownloaderUnavailable(
                f"wx_video_download binary not found at {self.downloader_bin}: install it "
                f"on PATH or set {WX_CHANNELS_DOWNLOAD_BIN_ENV} to a valid path"
            )

        safe_filename = Path(filename).name
        download_path = Path.home() / "Downloads" / safe_filename
        cmd = [
            str(self.downloader_bin),
            "download",
            "--url",
            media_url,
            "--filename",
            safe_filename,
        ]
        key_text = str(decode_key or "").strip()
        if key_text and key_text != "0":
            cmd.extend(["--key", key_text])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise WeChatChannelsDownloaderUnavailable(
                f"wx_video_download failed (exit {result.returncode}): {stderr}"
            )
        if not download_path.exists():
            raise WeChatChannelsDownloaderUnavailable(
                f"wx_video_download did not produce {download_path}"
            )
        return download_path


class WeChatChannelsF0Importer:
    """Import WeChat Channels video artifacts without crossing the F0 boundary."""

    def __init__(
        self,
        *,
        root: Path,
        client: WeChatChannelsDownloadClient | None = None,
    ) -> None:
        self.root = root
        self.client = client or WeChatChannelsDownloadClient(
            downloader_bin=resolve_wx_channels_download_bin(root)
        )

    def import_video(
        self,
        *,
        url: str,
        video_file_path: Path | None = None,
        download: bool = False,
        profile_payload: dict[str, Any] | None = None,
    ) -> WeChatChannelsImportResult:
        """Persist raw video/profile artifacts, ContentRecord, and import receipt."""
        import_run_id = _new_wechat_channels_import_run_id()
        raw_profile = profile_payload or self.client.get_feed_profile(url)
        feed_object, inner_payload = _extract_wechat_channels_feed_object(raw_profile)
        media = _select_wechat_channels_video_media(feed_object)

        creator = feed_object.get("contact") or {}
        creator_id = str(creator.get("username") or "unknown")
        creator_name = creator.get("nickname") or None
        feed_id = str(feed_object.get("id") or _short_sha256(url, 16))
        content_id = _derive_wechat_channels_content_id(creator_id, feed_id)
        dedupe_fingerprint = _derive_wechat_channels_dedupe(creator_id, feed_id)
        creator_segment = _safe_path_segment(creator_id)

        raw_dir = self.root / "data" / "raw" / "wechat" / "channels" / creator_segment
        f0_dir = self.root / "data" / "F0_intake" / "wechat" / "channels" / creator_segment
        raw_dir.mkdir(parents=True, exist_ok=True)
        f0_dir.mkdir(parents=True, exist_ok=True)

        raw_profile_path = raw_dir / f"{feed_id}.profile.json"
        raw_video_path = raw_dir / f"{feed_id}{_video_suffix(video_file_path)}"
        record_path = f0_dir / f"{content_id}.json"
        receipt_path = f0_dir / f"{content_id}.receipt.json"

        if record_path.exists():
            record = ContentRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
            artifacts = WeChatChannelsArtifacts(
                raw_video_path=Path(record.raw_path),
                raw_profile_path=raw_profile_path,
                video_sha256=record.metadata.get("raw_video_sha256", ""),
                profile_sha256=_sha256_file(raw_profile_path) if raw_profile_path.exists() else "",
            )
            receipt = _build_wechat_channels_receipt(
                import_run_id=import_run_id,
                status="already_imported",
                record=record,
                record_path=record_path,
                artifacts=artifacts,
                f0_dir=f0_dir,
            )
            receipt_path.write_text(
                receipt.model_dump_json(indent=2),
                encoding="utf-8",
            )
            return WeChatChannelsImportResult(
                import_run_id=import_run_id,
                status="already_imported",
                content_record=record,
                record_path=record_path,
                receipt_path=receipt_path,
                artifacts=artifacts,
                f0_dir=f0_dir,
            )

        _write_json_if_absent(raw_profile_path, raw_profile)
        source_video_path = self._resolve_source_video_path(
            video_file_path=video_file_path,
            download=download,
            media=media,
            filename=f"{feed_id}.mp4",
        )
        if not raw_video_path.exists():
            shutil.copy2(source_video_path, raw_video_path)

        video_sha256 = _sha256_file(raw_video_path)
        profile_sha256 = _sha256_file(raw_profile_path)
        artifacts = WeChatChannelsArtifacts(
            raw_video_path=raw_video_path,
            raw_profile_path=raw_profile_path,
            video_sha256=video_sha256,
            profile_sha256=profile_sha256,
        )
        record = _build_wechat_channels_content_record(
            content_id=content_id,
            url=url,
            feed_object=feed_object,
            inner_payload=inner_payload,
            media=media,
            creator_id=creator_id,
            creator_name=creator_name,
            dedupe_fingerprint=dedupe_fingerprint,
            import_run_id=import_run_id,
            artifacts=artifacts,
            acquisition_method="provided_file" if video_file_path else "wx_channels_download_cli",
            downloader_bin=self.client.downloader_bin,
        )
        record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        receipt = _build_wechat_channels_receipt(
            import_run_id=import_run_id,
            status="imported",
            record=record,
            record_path=record_path,
            artifacts=artifacts,
            f0_dir=f0_dir,
        )
        receipt_path.write_text(
            receipt.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return WeChatChannelsImportResult(
            import_run_id=import_run_id,
            status="imported",
            content_record=record,
            record_path=record_path,
            receipt_path=receipt_path,
            artifacts=artifacts,
            f0_dir=f0_dir,
        )

    def _resolve_source_video_path(
        self,
        *,
        video_file_path: Path | None,
        download: bool,
        media: dict[str, Any],
        filename: str,
    ) -> Path:
        if video_file_path is not None:
            if not video_file_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_file_path}")
            return video_file_path
        if not download:
            raise ValueError("Provide video_file_path or set download=true")
        media_url = str(media.get("url") or "")
        if not media_url:
            raise ValueError("WeChat Channels profile has no downloadable media URL")
        return self.client.download_media(
            media_url=media_url,
            decode_key=media.get("decodeKey"),
            filename=filename,
        )


def _new_wechat_channels_import_run_id() -> str:
    return f"wxch_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _derive_wechat_channels_content_id(creator_id: str, feed_id: str) -> str:
    return hashlib.sha256(f"wechat_channels:{creator_id}:{feed_id}".encode("utf-8")).hexdigest()[:32]


def _derive_wechat_channels_dedupe(creator_id: str, feed_id: str) -> str:
    return hashlib.sha256(f"wechat_channels:{creator_id}:{feed_id}".encode("utf-8")).hexdigest()[:16]


def _short_sha256(value: str, length: int) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _safe_path_segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._@-]+", "_", value).strip("._")
    return safe[:96] or "unknown"


def _video_suffix(video_file_path: Path | None) -> str:
    if video_file_path and video_file_path.suffix:
        return video_file_path.suffix.lower()
    return ".mp4"


def _write_json_if_absent(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_wechat_channels_feed_object(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    outer_data = payload.get("data")
    if not isinstance(outer_data, dict):
        raise ValueError("WeChat Channels profile response missing data")
    if outer_data.get("errCode") not in (None, 0):
        raise ValueError(outer_data.get("errMsg") or "WeChat Channels profile returned an error")

    inner_payload = outer_data.get("data") if isinstance(outer_data.get("data"), dict) else outer_data
    feed_object = inner_payload.get("object") if isinstance(inner_payload, dict) else None
    if not isinstance(feed_object, dict):
        raise ValueError("WeChat Channels profile response missing object")
    return feed_object, inner_payload


def _select_wechat_channels_video_media(feed_object: dict[str, Any]) -> dict[str, Any]:
    object_desc = feed_object.get("objectDesc") or {}
    media_items = object_desc.get("media") or []
    for item in media_items:
        if isinstance(item, dict) and (item.get("mediaType") in (None, 4) or item.get("url")):
            return item
    raise ValueError("WeChat Channels profile response missing video media")


def _published_at_from_feed(feed_object: dict[str, Any]) -> datetime | None:
    raw = feed_object.get("createtime")
    if raw in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _build_wechat_channels_content_record(
    *,
    content_id: str,
    url: str,
    feed_object: dict[str, Any],
    inner_payload: dict[str, Any],
    media: dict[str, Any],
    creator_id: str,
    creator_name: str | None,
    dedupe_fingerprint: str,
    import_run_id: str,
    artifacts: WeChatChannelsArtifacts,
    acquisition_method: str,
    downloader_bin: Path | None,
) -> ContentRecord:
    object_desc = feed_object.get("objectDesc") or {}
    description = object_desc.get("description") or ""
    title = description.strip().splitlines()[0][:120] if description.strip() else f"WeChat Channels {feed_object.get('id')}"

    metadata = {
        "source_kind": WECHAT_CHANNELS_SOURCE_KIND,
        "source_product": "channels",
        "feed_id": str(feed_object.get("id") or ""),
        "object_nonce_id": feed_object.get("objectNonceId"),
        "creator_username": creator_id,
        "creator_nickname": creator_name,
        "description": description,
        "comment_count": inner_payload.get("commentCount"),
        "media_url": media.get("url"),
        "cover_url": media.get("coverUrl"),
        "decode_key_present": bool(media.get("decodeKey")),
        "duration_seconds": media.get("videoPlayLen"),
        "width": media.get("width"),
        "height": media.get("height"),
        "file_size": media.get("fileSize"),
        "media_type": media.get("mediaType"),
        "media_specs": media.get("spec") or [],
        "raw_profile_path": str(artifacts.raw_profile_path),
        "raw_profile_sha256": artifacts.profile_sha256,
        "raw_video_sha256": artifacts.video_sha256,
        "import_run_id": import_run_id,
        "acquisition_status": "success",
        "acquisition_method": acquisition_method,
        "downloader": "scripts/wx_channels_download",
        "downloader_bin": str(downloader_bin) if downloader_bin else None,
    }

    return ContentRecord(
        content_id=content_id,
        source_type=WECHAT_CHANNELS_SOURCE_KIND,
        source_platform="wechat",
        creator_id=creator_id,
        creator_name=creator_name,
        published_at=_published_at_from_feed(feed_object),
        title=title,
        raw_path=str(artifacts.raw_video_path),
        file_type="video",
        metadata=metadata,
        source_url=url,
        external_source_id=str(feed_object.get("id") or ""),
        dedupe_fingerprint=dedupe_fingerprint,
    )


def _build_wechat_channels_receipt(
    *,
    import_run_id: str,
    status: str,
    record: ContentRecord,
    record_path: Path,
    artifacts: WeChatChannelsArtifacts,
    f0_dir: Path,
) -> ImportReceipt:
    """Build a canonical ImportReceipt for a WeChat Channels video import."""
    # Map legacy status values to ImportStatus literals.
    _status_map = {"imported": "completed", "already_imported": "skipped"}
    mapped_status = _status_map.get(status, status)

    return ImportReceipt(
        run_id=import_run_id,
        source_channel="wechat_channels",
        source_kind=WECHAT_CHANNELS_SOURCE_KIND,
        status=mapped_status,
        content_id=record.content_id,
        external_source_id=record.external_source_id,
        dedupe_fingerprint=record.dedupe_fingerprint,
        collected_at=record.collected_at,
        raw_sha256={
            "video": artifacts.video_sha256,
            "profile": artifacts.profile_sha256,
        },
        raw_paths={
            "video": str(artifacts.raw_video_path),
            "profile": str(artifacts.raw_profile_path),
        },
        record_path=str(record_path),
        records_created=1 if status == "imported" else 0,
    )
