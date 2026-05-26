"""Tests for WeChat Channels F0 import."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from finer.ingestion.wechat_adapter import (
    WECHAT_CHANNELS_SOURCE_KIND,
    WeChatChannelsDownloadClient,
    WeChatChannelsF0Importer,
)
from finer.schemas.content import ContentRecord


def _profile_payload() -> dict:
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "errCode": 0,
            "errMsg": "ok",
            "data": {
                "object": {
                    "id": "14819096805414996657",
                    "contact": {
                        "username": "v2_test_finder@finder",
                        "nickname": "Test Creator",
                    },
                    "objectDesc": {
                        "description": "Market view short video",
                        "media": [
                            {
                                "url": "https://finder.video.qq.com/test.mp4",
                                "mediaType": 4,
                                "videoPlayLen": 41,
                                "width": 1080,
                                "height": 1440,
                                "fileSize": 12,
                                "decodeKey": "123456",
                                "coverUrl": "https://example.com/cover.jpg",
                                "spec": [{"fileFormat": "xWT111"}],
                            }
                        ],
                    },
                    "objectNonceId": "nonce_001",
                    "source_url": "",
                    "createtime": 1700000000,
                },
                "commentCount": 7,
            },
        },
    }


def test_wechat_channels_importer_writes_f0_artifacts(tmp_path: Path) -> None:
    video = tmp_path / "downloaded.mp4"
    video.write_bytes(b"video-bytes")
    importer = WeChatChannelsF0Importer(
        root=tmp_path,
        client=WeChatChannelsDownloadClient(),
    )

    result = importer.import_video(
        url="https://weixin.qq.com/sph/test",
        video_file_path=video,
        profile_payload=_profile_payload(),
    )

    assert result.status == "imported"
    assert result.artifacts.raw_video_path.exists()
    assert result.artifacts.raw_profile_path.exists()
    assert result.record_path.exists()
    assert result.receipt_path.exists()
    assert "data/raw/wechat/channels" in str(result.artifacts.raw_video_path)
    assert "data/F0_intake/wechat/channels" in str(result.record_path)

    record = ContentRecord.model_validate_json(result.record_path.read_text(encoding="utf-8"))
    assert record.file_type == "video"
    assert record.source_platform == "wechat"
    assert record.source_type == "unclassified"
    assert record.external_source_id == "14819096805414996657"
    assert record.metadata["source_kind"] == WECHAT_CHANNELS_SOURCE_KIND
    assert record.metadata["raw_video_sha256"] == result.artifacts.video_sha256
    assert record.metadata["raw_profile_path"] == str(result.artifacts.raw_profile_path)

    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["stage"] == "F0"
    assert receipt["source_channel"] == "wechat"
    assert receipt["source_kind"] == WECHAT_CHANNELS_SOURCE_KIND
    assert receipt["content_id"] == record.content_id


def test_wechat_channels_importer_is_idempotent(tmp_path: Path) -> None:
    video = tmp_path / "downloaded.mp4"
    video.write_bytes(b"video-bytes")
    importer = WeChatChannelsF0Importer(
        root=tmp_path,
        client=WeChatChannelsDownloadClient(),
    )

    first = importer.import_video(
        url="https://weixin.qq.com/sph/test",
        video_file_path=video,
        profile_payload=_profile_payload(),
    )
    second = importer.import_video(
        url="https://weixin.qq.com/sph/test",
        video_file_path=video,
        profile_payload=_profile_payload(),
    )

    assert second.status == "already_imported"
    assert second.content_record.content_id == first.content_record.content_id
    assert second.record_path == first.record_path


def test_wechat_channels_import_route(tmp_path: Path) -> None:
    from finer.api.routes import wechat
    from finer.api.server import app

    video = tmp_path / "downloaded.mp4"
    video.write_bytes(b"video-bytes")

    with patch.object(wechat, "REPO_ROOT", tmp_path), patch(
        "finer.ingestion.wechat_adapter.WeChatChannelsDownloadClient.get_feed_profile",
        return_value=_profile_payload(),
    ):
        client = TestClient(app)
        resp = client.post(
            "/api/wechat/channels/import",
            json={
                "url": "https://weixin.qq.com/sph/test",
                "video_file_path": str(video),
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "imported"
    assert data["content_record"]["file_type"] == "video"
    assert data["content_record"]["metadata"]["source_kind"] == WECHAT_CHANNELS_SOURCE_KIND
    assert Path(data["record_path"]).exists()
    assert Path(data["receipt_path"]).exists()


def test_wechat_channels_import_route_requires_video_or_download() -> None:
    from finer.api.server import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/wechat/channels/import",
        json={"url": "https://weixin.qq.com/sph/test"},
    )

    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "F0_IN_001"
    assert data["error"]["details"]["stage"] == "F0"
    assert data["error"]["details"]["source_channel"] == "wechat"
