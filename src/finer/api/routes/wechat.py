"""WeChat API Routes — REST endpoints for WeChat integration.

Provides endpoints for:
- QR code login
- Account management
- Article listing and syncing
- Integration with F0 Intake pipeline
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pathlib import Path
from typing import List, Optional
import logging

from finer.schemas.wechat import (
    LoginSessionResponse,
    LoginStatusResponse,
    AccountResponse,
    ArticleResponse,
    ArticleListResponse,
    ArticleListRequest,
    SyncRequest,
    SyncResultResponse,
    WeChatStatusResponse,
    WeChatUnifiedConfig,
    WeChatSourceType,
    LoginStatus,
    ArticleSyncStatus,
)
from finer.ingestion.wechat_adapter import get_wechat_adapter, WeChatAdapter, get_unified_wechat_adapter, UnifiedWeChatAdapter
from finer.paths import REPO_ROOT
from finer.config import load_wechat_service_config

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_adapter() -> WeChatAdapter:
    """Get WeChat adapter instance."""
    return get_wechat_adapter(REPO_ROOT)


def _get_unified_adapter() -> UnifiedWeChatAdapter:
    """Get unified WeChat adapter instance."""
    config = load_wechat_service_config(REPO_ROOT)
    return get_unified_wechat_adapter(
        REPO_ROOT,
        WeChatUnifiedConfig(
            source_type=WeChatSourceType(config.source_type),
            exporter_url=config.exporter_url,
            prefer_exporter=config.prefer_exporter,
            cache_credentials=config.cache_credentials,
        )
    )


# --- Login Endpoints ---

@router.post("/login", response_model=LoginSessionResponse)
async def create_login_session(
    use_exporter: bool = Query(default=True, description="Use wechat-article-exporter service if available"),
):
    """Create a new login session with QR code.

    Returns a session ID and QR code URL. User should scan the QR code
    with WeChat app to complete login.

    Poll `/login/status` to check when login is confirmed.

    Args:
        use_exporter: Try to use wechat-article-exporter service first
    """
    import base64
    import secrets

    # Try exporter service first if enabled
    if use_exporter:
        try:
            from finer.ingestion.wechat_exporter_client import WeChatExporterClient
            config = load_wechat_service_config(REPO_ROOT)
            client = WeChatExporterClient(base_url=config.exporter_url)

            # Get QR code as PNG bytes
            qr_bytes = await client.get_qrcode()
            qr_base64 = base64.b64encode(qr_bytes).decode("utf-8")
            qr_url = f"data:image/png;base64,{qr_base64}"

            session_id = secrets.token_urlsafe(16)

            session = LoginSessionResponse(
                session_id=session_id,
                qr_url=qr_url,
                qr_base64=qr_base64,
                expires_in=300,
                status=LoginStatus.PENDING,
            )
            logger.info(f"Created login session via exporter: {session_id}")
            return session
        except Exception as e:
            logger.warning(f"Exporter login failed, falling back to direct: {e}")

    # Fallback to direct adapter
    adapter = _get_adapter()

    try:
        session = await adapter.create_login_session()

        # If we got a URL but no base64, try to fetch the image
        if session.qr_url and not session.qr_base64:
            if session.qr_url.startswith("data:"):
                # Already a data URL
                pass
            else:
                # Try to fetch the QR code image
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                        resp = await client.get(
                            session.qr_url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                                "Accept": "image/*",
                            }
                        )
                        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                            session.qr_base64 = base64.b64encode(resp.content).decode("utf-8")
                            session.qr_url = f"data:image/png;base64,{session.qr_base64}"
                except Exception as e:
                    logger.warning(f"Failed to fetch QR image: {e}")

        return LoginSessionResponse(
            session_id=session.session_id,
            qr_url=session.qr_url,
            qr_base64=session.qr_base64,
            expires_in=300,
            status=LoginStatus(session.status.value),
        )
    except Exception as e:
        logger.error(f"Failed to create login session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create login session: {e}")


@router.post("/login/exporter")
async def create_login_via_exporter():
    """Create login session via wechat-article-exporter service.

    This endpoint uses the external wechat-article-exporter Nuxt.js service
    which has better QR code generation support.

    Requires wechat-article-exporter to be running at WECHAT_EXPORTER_URL.
    """
    try:
        from finer.ingestion.wechat_exporter_client import WeChatExporterClient
        from finer.config import load_wechat_service_config

        config = load_wechat_service_config(REPO_ROOT)
        client = WeChatExporterClient(base_url=config.exporter_url)

        # Get QR code from exporter
        qr_bytes = await client.get_qrcode()
        import base64
        qr_base64 = base64.b64encode(qr_bytes).decode("utf-8")
        qr_url = f"data:image/png;base64,{qr_base64}"

        import secrets
        session_id = secrets.token_urlsafe(16)

        return LoginSessionResponse(
            session_id=session_id,
            qr_url=qr_url,
            qr_base64=qr_base64,
            expires_in=300,
            status=LoginStatus.PENDING,
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="wechat_exporter_client not available")
    except Exception as e:
        logger.error(f"Failed to create login via exporter: {e}")
        raise HTTPException(status_code=500, detail=f"Exporter login failed: {e}")


@router.get("/login/status/{session_id}", response_model=LoginStatusResponse)
async def check_login_status(session_id: str):
    """Check login status for a session.

    Poll this endpoint to detect when QR code is scanned and confirmed.
    """
    adapter = _get_adapter()

    try:
        session = await adapter.check_login_status(session_id)

        return LoginStatusResponse(
            session_id=session.session_id,
            status=LoginStatus(session.status.value),
            account_id=session.account_id if session.status == LoginStatus.CONFIRMED else None,
            account_name=session.account_name if session.status == LoginStatus.CONFIRMED else None,
            error_msg=session.error_msg if session.status in (LoginStatus.FAILED, LoginStatus.EXPIRED) else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to check login status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check status: {e}")


# --- Account Endpoints ---

@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts():
    """List all logged-in WeChat accounts."""
    adapter = _get_adapter()

    accounts = adapter.get_accounts()

    return [
        AccountResponse(
            account_id=acc.account_id,
            account_name=acc.account_name,
            last_sync=acc.last_sync,
            article_count=acc.article_count,
            is_valid=acc.is_valid,
        )
        for acc in accounts
    ]


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: str):
    """Get a specific WeChat account."""
    adapter = _get_adapter()

    account = adapter.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    return AccountResponse(
        account_id=account.account_id,
        account_name=account.account_name,
        last_sync=account.last_sync,
        article_count=account.article_count,
        is_valid=account.is_valid,
    )


@router.delete("/accounts/{account_id}")
async def remove_account(account_id: str):
    """Remove a logged-in account."""
    adapter = _get_adapter()

    success = adapter.remove_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    return {"status": "ok", "message": f"Account {account_id} removed"}


# --- Article Endpoints ---

@router.get("/articles/{account_id}", response_model=ArticleListResponse)
async def list_articles(
    account_id: str,
    page: int = 0,
    page_size: int = 10,
    query: Optional[str] = None,
):
    """List articles from a WeChat account.

    Requires the account to be logged in.
    """
    adapter = _get_adapter()

    try:
        articles = await adapter.list_articles(account_id, page, page_size, query)

        return ArticleListResponse(
            account_id=account_id,
            articles=[
                ArticleResponse(
                    article_id=art.article_id,
                    title=art.title,
                    author=art.author,
                    digest=art.digest,
                    publish_time=art.publish_time,
                    read_count=art.read_count,
                    like_count=art.like_count,
                    content_url=art.content_url,
                    status=ArticleSyncStatus(art.status.value),
                )
                for art in articles
            ],
            total=len(articles),
            page=page,
            page_size=page_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list articles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list articles: {e}")


@router.post("/sync/{account_id}", response_model=SyncResultResponse)
async def sync_articles(
    account_id: str,
    max_articles: Optional[int] = None,
    include_images: bool = False,
    trigger_l0: bool = True,
    background_tasks: BackgroundTasks = None,
):
    """Sync articles from a WeChat account to local storage.

    Articles are saved to `data/raw/wechat/{account_id}/` as Markdown files.

    Args:
        account_id: Account to sync
        max_articles: Maximum articles to sync (None for all)
        include_images: Download images locally
        trigger_l0: Trigger F0 ingestion pipeline after sync
    """
    adapter = _get_adapter()

    # Check account exists
    account = adapter.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    try:
        # Sync articles
        synced_paths = await adapter.sync_all_articles(
            account_id,
            max_articles=max_articles,
            include_images=include_images,
        )

        # Trigger L0 pipeline if requested
        l0_triggered = False
        if trigger_l0 and synced_paths:
            # L0 pipeline integration would go here
            # Currently placeholder - files are saved to data/raw/wechat/{account_id}/
            # They can be imported via the integrations hub
            l0_triggered = False
            logger.info(f"Synced {len(synced_paths)} articles to {adapter.output_dir}")

        return SyncResultResponse(
            account_id=account_id,
            synced_count=len(synced_paths),
            articles=[str(p) for p in synced_paths],
            errors=[],
            l0_triggered=l0_triggered,
        )

    except Exception as e:
        logger.error(f"Failed to sync articles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync articles: {e}")


@router.post("/sync-single", response_model=SyncResultResponse)
async def sync_single_article(
    account_id: str,
    article_id: str,
    include_images: bool = False,
):
    """Sync a single article from a WeChat account."""
    adapter = _get_adapter()

    try:
        # Get article list first
        articles = await adapter.list_articles(account_id, page=0, page_size=50)

        # Find the specific article
        article = next((a for a in articles if a.article_id == article_id), None)
        if not article:
            raise HTTPException(status_code=404, detail=f"Article {article_id} not found")

        # Sync the article
        path = await adapter.sync_article(account_id, article, include_images)

        return SyncResultResponse(
            account_id=account_id,
            synced_count=1,
            articles=[str(path)],
            errors=[],
            l0_triggered=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync article: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync article: {e}")


# --- Status Endpoint ---

@router.get("/status", response_model=WeChatStatusResponse)
async def get_wechat_status():
    """Get WeChat integration status."""
    adapter = _get_adapter()

    accounts = adapter.get_accounts()
    total_articles = sum(acc.article_count for acc in accounts)
    last_sync = max(
        (acc.last_sync for acc in accounts if acc.last_sync),
        default=None
    )

    return WeChatStatusResponse(
        enabled=True,
        accounts_count=len(accounts),
        total_articles_synced=total_articles,
        last_sync=last_sync,
        cache_dir=str(adapter.cache_dir),
        output_dir=str(adapter.output_dir),
    )


# --- Utility Endpoints ---

@router.post("/refresh/{account_id}")
async def refresh_account_token(account_id: str):
    """Refresh authentication token for an account.

    If the account's token has expired, this will initiate a new login session.
    """
    adapter = _get_adapter()

    account = adapter.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Check if token is still valid by trying to list articles
    try:
        articles = await adapter.list_articles(account_id, page=0, page_size=1)
        return {"status": "ok", "message": "Token is valid", "account_id": account_id}
    except Exception:
        # Token is invalid - need to re-login
        return {
            "status": "relogin_required",
            "message": "Token expired, please re-login",
            "account_id": account_id,
        }
