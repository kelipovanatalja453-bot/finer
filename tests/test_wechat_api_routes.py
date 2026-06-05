"""Tests for WeChat API routes."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    from finer.api.server import app
    return TestClient(app)


class TestLoginEndpoints:
    @patch("finer.api.routes.wechat._get_exporter_client")
    def test_create_login_session_success(self, mock_get_client, client):
        mock_client = AsyncMock()
        mock_client.get_qrcode.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        mock_get_client.return_value = mock_client

        resp = client.post("/api/wechat/login")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "qr_ready"
        assert data["qr_data_uri"].startswith("data:image/png;base64,")

    @patch("finer.api.routes.wechat._get_exporter_client")
    def test_create_login_session_exporter_unavailable(self, mock_get_client, client):
        mock_client = AsyncMock()
        mock_client.get_qrcode.side_effect = ConnectionError("Connection refused")
        mock_get_client.return_value = mock_client

        resp = client.post("/api/wechat/login")
        assert resp.status_code == 502

    @patch("finer.api.routes.wechat._get_exporter_client")
    def test_login_status_not_found(self, mock_get_client, client):
        resp = client.get("/api/wechat/login/nonexistent/status")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "WX_AUTH_001"

    @patch("finer.api.routes.wechat._get_exporter_client")
    def test_qr_endpoint_not_found(self, mock_get_client, client):
        resp = client.get("/api/wechat/login/nonexistent/qr")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "WX_AUTH_001"


class TestAccountEndpoints:
    @patch("finer.api.routes.wechat.get_unified_wechat_adapter")
    def test_list_accounts_empty(self, mock_adapter_fn, client):
        mock_adapter = AsyncMock()
        mock_adapter.list_accounts.return_value = []
        mock_adapter_fn.return_value = mock_adapter

        resp = client.get("/api/wechat/accounts")
        assert resp.status_code == 200
        assert resp.json() == []


class TestSyncPagination:
    @patch("finer.api.routes.wechat._register_f0_index")
    @patch("finer.api.routes.wechat._get_exporter_client")
    def test_sync_paginates_articles(self, mock_get_client, mock_register, client, tmp_path):
        """Sync should loop get_articles until has_more is False.

        ``_register_f0_index`` is patched to a no-op and ``REPO_ROOT`` to a tmp
        dir so the test never writes to the live Project Memory DB or repo data.
        """
        from finer.ingestion.wechat_exporter_client import ArticleListResult, WeChatArticleInfo

        mock_client = AsyncMock()
        # First page: 10 articles, has_more=True
        page1_articles = [
            WeChatArticleInfo(aid=f"art_{i}", title=f"Article {i}", link=f"https://example.com/{i}", create_time=1700000000)
            for i in range(10)
        ]
        # Second page: 3 articles, has_more=False
        page2_articles = [
            WeChatArticleInfo(aid=f"art_{i}", title=f"Article {i}", link=f"https://example.com/{i}", create_time=1700000000)
            for i in range(10, 13)
        ]

        mock_client.get_articles = AsyncMock(
            side_effect=[
                ArticleListResult(articles=page1_articles, total=13, has_more=True),
                ArticleListResult(articles=page2_articles, total=13, has_more=False),
            ]
        )
        mock_client.export_article = AsyncMock(return_value="# Article content")
        mock_client.auth_key = "test_key"
        mock_get_client.return_value = mock_client

        with patch("finer.api.routes.wechat.load_wechat_service_config"), \
                patch("finer.api.routes.wechat.REPO_ROOT", tmp_path):
            resp = client.post("/api/wechat/sync/test_account")

        assert resp.status_code == 200
        data = resp.json()
        # get_articles called twice (page 1 + page 2)
        assert mock_client.get_articles.call_count == 2
        # First call: begin=0, size=10
        assert mock_client.get_articles.call_args_list[0].kwargs.get("begin") == 0 or \
               mock_client.get_articles.call_args_list[0].args[1] == 0
        # Second call: begin=10, size=10
        assert mock_client.get_articles.call_args_list[1].kwargs.get("begin") == 10 or \
               mock_client.get_articles.call_args_list[1].args[1] == 10


class TestSyncReceipt:
    """Official-account sync must emit a GATE ImportReceipt and register PM."""

    @patch("finer.api.routes.wechat._register_f0_index")
    @patch("finer.api.routes.wechat._get_exporter_client")
    def test_sync_writes_receipt_and_registers_pm(
        self, mock_get_client, mock_register, client, tmp_path
    ):
        import json as _json
        from pathlib import Path
        from finer.ingestion.wechat_exporter_client import ArticleListResult, WeChatArticleInfo

        article = WeChatArticleInfo(
            aid="art_1",
            title="A",
            link="https://mp.weixin.qq.com/s/abc",
            create_time=1700000000,
        )
        mock_client = AsyncMock()
        mock_client.get_articles = AsyncMock(
            return_value=ArticleListResult(articles=[article], total=1, has_more=False)
        )
        mock_client.export_article = AsyncMock(return_value="# Body")
        mock_client.search_account = AsyncMock(return_value=[])
        mock_client.auth_key = "test_key"
        mock_get_client.return_value = mock_client

        with patch("finer.api.routes.wechat.load_wechat_service_config"), \
                patch("finer.api.routes.wechat.REPO_ROOT", tmp_path):
            resp = client.post("/api/wechat/sync/test_account")

        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] == 1
        content_id = data["content_record_ids"][0]

        # Receipt is written next to the ContentRecord, named {content_id}.receipt.json
        receipt_path = (
            tmp_path / "data" / "F0_intake" / "wechat" / "test_account" / f"{content_id}.receipt.json"
        )
        assert receipt_path.exists()
        receipt = _json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["source_channel"] == "wechat"
        assert receipt["source_kind"] == "wechat_article"
        assert receipt["status"] == "completed"
        assert receipt["records_created"] == 1
        # raw_artifact_kind == exporter_markdown is encoded as the artifact role
        assert "exporter_markdown" in receipt["raw_paths"]
        assert "exporter_markdown" in receipt["raw_sha256"]

        # Project Memory registration was attempted exactly once for the article.
        assert mock_register.call_count == 1

    @patch("finer.api.routes.wechat._register_f0_index")
    @patch("finer.api.routes.wechat._get_exporter_client")
    def test_receipt_projects_to_import_run_row(
        self, mock_get_client, mock_register, client, tmp_path
    ):
        """The persisted receipt must project cleanly onto an import_runs row."""
        import json as _json
        from finer.schemas.import_receipt import ImportReceipt
        from finer.ingestion.wechat_exporter_client import ArticleListResult, WeChatArticleInfo

        article = WeChatArticleInfo(
            aid="art_2", title="B", link="https://mp.weixin.qq.com/s/xyz", create_time=1700000000
        )
        mock_client = AsyncMock()
        mock_client.get_articles = AsyncMock(
            return_value=ArticleListResult(articles=[article], total=1, has_more=False)
        )
        mock_client.export_article = AsyncMock(return_value="# Body")
        mock_client.search_account = AsyncMock(return_value=[])
        mock_client.auth_key = "test_key"
        mock_get_client.return_value = mock_client

        with patch("finer.api.routes.wechat.load_wechat_service_config"), \
                patch("finer.api.routes.wechat.REPO_ROOT", tmp_path):
            resp = client.post("/api/wechat/sync/test_account")

        content_id = resp.json()["content_record_ids"][0]
        receipt_path = (
            tmp_path / "data" / "F0_intake" / "wechat" / "test_account" / f"{content_id}.receipt.json"
        )
        receipt = ImportReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
        row = receipt.to_import_run()
        assert row["source_channel"] == "wechat"
        assert row["status"] == "completed"
        assert row["records_created"] == 1
        assert row["error_code"] is None


class TestExporterHealth:
    @patch("finer.api.routes.wechat.load_wechat_service_config")
    def test_health_exporter_available(self, mock_config, client):
        mock_config.return_value = MagicMock(exporter_url="http://localhost:3001")

        with patch("httpx.AsyncClient") as MockClient:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            resp = client.get("/api/wechat/exporter/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True

    @patch("finer.api.routes.wechat.load_wechat_service_config")
    def test_health_exporter_unavailable(self, mock_config, client):
        mock_config.return_value = MagicMock(exporter_url="http://localhost:9999")
        resp = client.get("/api/wechat/exporter/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
