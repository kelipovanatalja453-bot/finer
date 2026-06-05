"""Tests for Bilibili integration."""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from finer.ingestion.bilibili_adapter import (
    BilibiliVideoInfo,
    BilibiliClient,
    TranscriptSegment,
    TranscriptResult,
)


class TestBilibiliVideoInfo:
    """Test BilibiliVideoInfo dataclass."""

    def test_has_aid_field(self):
        """Verify BilibiliVideoInfo has aid field."""
        info = BilibiliVideoInfo(
            bvid="BV1xx411c7mD",
            title="Test Video",
            uploader="Test UP",
            uploader_id=12345,
            publish_time=datetime(2024, 1, 1),
            duration=120,
            description="Test description",
            cover_url="https://example.com/pic.jpg",
            aid=12345,
        )
        assert info.aid == 12345
        assert info.bvid == "BV1xx411c7mD"

    def test_default_aid(self):
        """Verify aid defaults to 0."""
        info = BilibiliVideoInfo(
            bvid="BV1xx411c7mD",
            title="Test",
            uploader="",
            uploader_id=0,
            publish_time=datetime(2024, 1, 1),
            duration=0,
            description="",
            cover_url="",
        )
        assert info.aid == 0

    def test_default_page_count(self):
        """Verify page_count defaults to 1."""
        info = BilibiliVideoInfo(
            bvid="BV1xx411c7mD",
            title="Test",
            uploader="",
            uploader_id=0,
            publish_time=datetime(2024, 1, 1),
            duration=0,
            description="",
            cover_url="",
        )
        assert info.page_count == 1

    def test_default_tags(self):
        """Verify tags defaults to empty list."""
        info = BilibiliVideoInfo(
            bvid="BV1xx411c7mD",
            title="Test",
            uploader="",
            uploader_id=0,
            publish_time=datetime(2024, 1, 1),
            duration=0,
            description="",
            cover_url="",
        )
        assert info.tags == []

    def test_all_fields(self):
        """Verify all fields can be set."""
        info = BilibiliVideoInfo(
            bvid="BV1xx411c7mD",
            title="My Video",
            uploader="UP主",
            uploader_id=99999,
            publish_time=datetime(2024, 6, 15, 10, 30),
            duration=3600,
            description="A long video",
            cover_url="https://example.com/cover.jpg",
            aid=54321,
            page_count=3,
            tags=["finance", "stock"],
        )
        assert info.bvid == "BV1xx411c7mD"
        assert info.title == "My Video"
        assert info.uploader == "UP主"
        assert info.uploader_id == 99999
        assert info.publish_time == datetime(2024, 6, 15, 10, 30)
        assert info.duration == 3600
        assert info.description == "A long video"
        assert info.cover_url == "https://example.com/cover.jpg"
        assert info.aid == 54321
        assert info.page_count == 3
        assert info.tags == ["finance", "stock"]


class TestBilibiliClient:
    """Test BilibiliClient initialization and methods."""

    def test_init_default(self):
        """Test default initialization."""
        client = BilibiliClient()
        assert client is not None
        assert "User-Agent" in client.headers
        assert "Referer" in client.headers
        assert client.timeout == 30.0

    def test_parse_bvid_direct(self):
        """Test parsing a direct BV ID."""
        client = BilibiliClient()
        assert client.parse_bvid("BV1xx411c7mD") == "BV1xx411c7mD"

    def test_parse_bvid_from_url(self):
        """Test extracting BV ID from a bilibili.com URL."""
        client = BilibiliClient()
        url = "https://www.bilibili.com/video/BV1xx411c7mD"
        assert client.parse_bvid(url) == "BV1xx411c7mD"

    def test_parse_bvid_from_short_url(self):
        """Test extracting BV ID from a b23.tv URL."""
        client = BilibiliClient()
        url = "https://b23.tv/BV1xx411c7mD"
        assert client.parse_bvid(url) == "BV1xx411c7mD"

    def test_parse_bvid_invalid(self):
        """Test parsing an invalid string raises ValueError."""
        client = BilibiliClient()
        with pytest.raises(ValueError, match="Cannot parse BV ID"):
            client.parse_bvid("not-a-valid-id")

    @patch("finer.ingestion.bilibili_adapter.httpx.Client")
    def test_search_videos_returns_parsed_results(self, mock_httpx_cls):
        """Test that search_videos calls the real API and parses results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "result": [
                    {
                        "bvid": "BV1abc123def",
                        "title": "Finance <em class=\"keyword\">Analysis</em> 2024",
                        "author": "TestUP",
                        "play": 50000,
                        "duration": "12:34",
                        "description": "A finance video",
                        "pic": "//i0.hdslb.com/bfs/archive/abc.jpg",
                    },
                    {
                        "bvid": "BV2xyz456ghi",
                        "title": "Stock Market",
                        "author": "AnotherUP",
                        "play": 10000,
                        "duration": "05:00",
                        "description": "Stock tips",
                        "pic": "//i0.hdslb.com/bfs/archive/xyz.jpg",
                    },
                ],
                "numResults": 2,
            },
        }

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        client = BilibiliClient()
        result = client.search_videos("finance")

        assert result["total"] == 2
        assert result["page"] == 1
        assert len(result["videos"]) == 2

        v0 = result["videos"][0]
        assert v0["bvid"] == "BV1abc123def"
        assert v0["title"] == "Finance Analysis 2024"  # HTML tags stripped
        assert v0["author"] == "TestUP"
        assert v0["play"] == 50000
        assert v0["duration"] == "12:34"
        assert v0["pic"] == "//i0.hdslb.com/bfs/archive/abc.jpg"

    @patch("finer.ingestion.bilibili_adapter.httpx.Client")
    def test_search_videos_api_failure_returns_empty(self, mock_httpx_cls):
        """Test that search_videos returns empty results when API returns error code."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "code": -412,
            "message": "请求被拦截",
        }

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        client = BilibiliClient()
        result = client.search_videos("finance")

        assert result["videos"] == []
        assert result["total"] == 0

    @patch("finer.ingestion.bilibili_adapter.httpx.Client")
    def test_search_videos_exception_returns_empty(self, mock_httpx_cls):
        """Test that search_videos returns empty results on network exception."""
        mock_client_instance = Mock()
        mock_client_instance.get.side_effect = Exception("connection timeout")
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        client = BilibiliClient()
        result = client.search_videos("finance", page=2, page_size=10)

        assert result["videos"] == []
        assert result["page"] == 2
        assert result["page_size"] == 10

    @patch("finer.ingestion.bilibili_adapter.httpx.Client")
    def test_search_videos_with_pagination(self, mock_httpx_cls):
        """Test search_videos passes pagination params to the API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {"result": [], "numResults": 0},
        }

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        client = BilibiliClient()
        result = client.search_videos("finance", page=2, page_size=10)

        assert result["page"] == 2
        assert result["page_size"] == 10

        # Verify params were passed correctly to httpx
        call_kwargs = mock_client_instance.get.call_args
        assert call_kwargs[1]["params"]["page"] == 2
        assert call_kwargs[1]["params"]["page_size"] == 10


class TestTranscriptSegment:
    """Test TranscriptSegment dataclass."""

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        seg = TranscriptSegment(start_time=3661.5, end_time=3721.0, text="hello")
        assert seg.format_timestamp(3661.5) == "[01:01:01]"

    def test_format_timestamp_zero(self):
        """Test zero timestamp."""
        seg = TranscriptSegment(start_time=0, end_time=0, text="hello")
        assert seg.format_timestamp(0) == "[00:00:00]"

    def test_to_markdown(self):
        """Test markdown output."""
        seg = TranscriptSegment(start_time=65.0, end_time=125.0, text="market analysis")
        assert seg.to_markdown() == "[00:01:05] market analysis"


class TestTranscriptResult:
    """Test TranscriptResult dataclass."""

    def test_to_markdown(self):
        """Test markdown generation from result."""
        info = BilibiliVideoInfo(
            bvid="BV1xx411c7mD",
            title="Finance Talk",
            uploader="UP主",
            uploader_id=123,
            publish_time=datetime(2024, 1, 1),
            duration=120,
            description="",
            cover_url="",
        )
        segments = [
            TranscriptSegment(start_time=0, end_time=5, text="Hello"),
            TranscriptSegment(start_time=5, end_time=10, text="World"),
        ]
        result = TranscriptResult(
            video_info=info,
            segments=segments,
            full_text="Hello World",
            model="paraformer-realtime-v2",
            duration_seconds=120,
        )
        md = result.to_markdown()
        assert "Finance Talk" in md
        assert "UP主" in md
        assert "[00:00:00] Hello" in md
        assert "[00:00:05] World" in md
        assert "paraformer-realtime-v2" in md


class TestVideoInfoResponse:
    """Test VideoInfoResponse includes aid."""

    def test_video_info_response_has_aid(self):
        """Verify VideoInfoResponse schema includes aid field."""
        from finer.api.routes.bilibili import VideoInfoResponse

        resp = VideoInfoResponse(
            bvid="BV1xx411c7mD",
            aid=12345,
            title="Test",
            uploader="UP",
            uploader_id=100,
            publish_time="2024-01-01T00:00:00",
            duration=120,
            description="",
            cover_url="",
            page_count=1,
            tags=[],
        )
        assert resp.aid == 12345

    def test_video_info_to_response_includes_aid(self):
        """Verify video_info_to_response maps aid from BilibiliVideoInfo."""
        from finer.api.routes.bilibili import video_info_to_response

        info = BilibiliVideoInfo(
            bvid="BV1xx411c7mD",
            aid=99999,
            title="Test Video",
            uploader="UP主",
            uploader_id=123,
            publish_time=datetime(2024, 1, 1),
            duration=120,
            description="desc",
            cover_url="https://example.com/pic.jpg",
        )
        resp = video_info_to_response(info)
        assert resp.aid == 99999


class TestSyncResponse:
    """Test SyncResponse uses canonical naming."""

    def test_sync_response_has_f0_path(self):
        """Verify SyncResponse uses f0_path, not l0_path."""
        from finer.api.routes.bilibili import SyncResponse

        resp = SyncResponse(
            bvid="BV1xx411c7mD",
            content_id="bilibili_BV1xx411c7mD",
            f0_path="/data/F0_intake/bilibili/123",
            transcript_path="/data/F0_intake/bilibili/123/BV1xx411c7mD.md",
            metadata_path="/data/processed/manifests/xxx.json",
            status="synced",
        )
        assert resp.f0_path == "/data/F0_intake/bilibili/123"
        assert resp.status == "synced"

    def test_sync_response_model_fields(self):
        """Verify SyncResponse field names match canonical F-stage naming."""
        from finer.api.routes.bilibili import SyncResponse
        import inspect

        # Ensure the model has f0_path in its fields
        field_names = set(SyncResponse.model_fields.keys())
        assert "f0_path" in field_names
        # Ensure legacy l0_path is NOT a field
        assert "l0_path" not in field_names


class TestBilibiliSearchEndpoint:
    """Test /api/bilibili/search endpoint behavior."""

    def test_search_empty_keyword_returns_empty(self):
        """Empty keyword returns empty results without calling API."""
        from fastapi.testclient import TestClient
        from finer.api.server import app

        client = TestClient(app)
        resp = client.get("/api/bilibili/search?keyword=")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["data"]["videos"] == []
        assert data["data"]["total"] == 0

    def test_search_error_returns_bili_ext_001(self):
        """Search failure returns BILI_EXT_001 error code."""
        from fastapi.testclient import TestClient
        from finer.api.server import app

        client = TestClient(app)
        with patch.object(
            __import__("finer.ingestion.bilibili_adapter", fromlist=["BilibiliClient"]).BilibiliClient,
            "search_videos",
            side_effect=RuntimeError("upstream timeout"),
        ):
            resp = client.get("/api/bilibili/search?keyword=finance")
        # error_response returns a JSONResponse with the error payload
        data = resp.json()
        assert data["ok"] is False
        assert data["error"]["code"] == "BILI_EXT_001"
