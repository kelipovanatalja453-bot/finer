"""KOL Profile 管理相关 Schema。

跨平台 KOL 身份管理，用于追踪同一 KOL 在不同平台的账号。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlatformIdentity(BaseModel):
    """平台身份信息。"""

    platform: str = Field(
        ...,
        description="平台标识：wechat, bilibili, feishu, twitter, weibo 等",
    )
    account_id: str = Field(
        ...,
        description="平台账号唯一标识",
    )
    account_name: Optional[str] = Field(
        default=None,
        description="账号显示名称",
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="头像 URL",
    )
    verified: bool = Field(
        default=False,
        description="是否已认证",
    )
    follower_count: Optional[int] = Field(
        default=None,
        description="粉丝数",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="平台特有元数据",
    )


class KOLProfile(BaseModel):
    """KOL 全局档案。"""

    kol_id: str = Field(
        ...,
        description="全局唯一 KOL ID，格式：kol_{uuid}",
    )
    display_name: str = Field(
        ...,
        description="显示名称",
    )
    platform_identities: list[PlatformIdentity] = Field(
        default_factory=list,
        description="各平台身份列表",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="标签：如 crypto, macro, tech",
    )
    rating: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="综合评分（0-5）",
    )
    bio: Optional[str] = Field(
        default=None,
        description="简介",
    )
    created_at: datetime = Field(
        ...,
        description="创建时间",
    )
    updated_at: datetime = Field(
        ...,
        description="最后更新时间",
    )

    def get_platform_identity(self, platform: str) -> Optional[PlatformIdentity]:
        """获取指定平台的身份信息。"""
        for identity in self.platform_identities:
            if identity.platform == platform:
                return identity
        return None

    def has_platform(self, platform: str) -> bool:
        """检查是否已关联某平台。"""
        return self.get_platform_identity(platform) is not None


class KOLProfileCreate(BaseModel):
    """创建 KOL Profile 请求。"""

    display_name: str = Field(..., description="显示名称")
    platform: str = Field(..., description="初始平台")
    account_id: str = Field(..., description="平台账号 ID")
    account_name: Optional[str] = Field(default=None, description="账号名称")
    avatar_url: Optional[str] = Field(default=None, description="头像 URL")
    tags: list[str] = Field(default_factory=list, description="初始标签")
    bio: Optional[str] = Field(default=None, description="简介")


class PlatformLink(BaseModel):
    """平台关联请求。"""

    platform: str = Field(..., description="平台标识")
    account_id: str = Field(..., description="平台账号 ID")
    account_name: Optional[str] = Field(default=None, description="账号名称")
    avatar_url: Optional[str] = Field(default=None, description="头像 URL")
    verified: bool = Field(default=False, description="是否认证")
    follower_count: Optional[int] = Field(default=None, description="粉丝数")
