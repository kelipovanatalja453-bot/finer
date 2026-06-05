"""WeChat adapter — backward-compatible re-export shim.

Split into wechat_mp_adapter.py (公众号) and wechat_channels_adapter.py (视频号).
This file re-exports all public names for backward compatibility.
"""

from finer.ingestion.wechat_mp_adapter import *  # noqa: F401,F403
from finer.ingestion.wechat_channels_adapter import *  # noqa: F401,F403

# Explicit re-exports for type checkers and IDE auto-complete
from finer.ingestion.wechat_mp_adapter import (
    ArticleStatus,
    UnifiedWeChatAdapter,
    WeChatAccount,
    WeChatAdapter,
    WeChatArticle,
    WeChatArticleClient,
    WeChatAuthClient,
    WeChatLoginStatus,
    WeChatSession,
    get_unified_wechat_adapter,
    get_wechat_adapter,
    init_wechat_adapter,
)
from finer.ingestion.wechat_channels_adapter import (
    WECHAT_CHANNELS_SOURCE_KIND,
    WX_CHANNELS_DOWNLOAD_BIN_ENV,
    WX_CHANNELS_DOWNLOAD_BINARY_NAME,
    WeChatChannelsArtifacts,
    WeChatChannelsDownloadClient,
    WeChatChannelsDownloaderUnavailable,
    WeChatChannelsF0Importer,
    WeChatChannelsImportResult,
    resolve_wx_channels_download_bin,
)
