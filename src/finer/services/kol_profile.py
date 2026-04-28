"""KOL Profile 管理服务。

提供跨平台 KOL 身份映射和管理功能。
"""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from finer.schemas.kol_profile import (
    KOLProfile,
    KOLProfileCreate,
    PlatformIdentity,
    PlatformLink,
)
from finer.paths import DATA_ROOT


class KOLProfileManager:
    """KOL 档案管理器。

    负责：
    - 创建和查询 KOL 档案
    - 跨平台身份关联
    - 档案持久化存储

    存储路径：data/kol_profiles/
    文件格式：{kol_id}.json
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """初始化管理器。

        Args:
            storage_dir: 存储目录，默认 data/kol_profiles/
        """
        self.storage_dir = storage_dir or DATA_ROOT / "kol_profiles"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, KOLProfile] = {}
        self._platform_index: dict[str, str] = {}  # "{platform}:{account_id}" -> kol_id
        self._loaded = False
        self._lock = threading.Lock()  # 线程安全锁

    def _ensure_loaded(self) -> None:
        """懒加载所有档案到缓存（线程安全）。"""
        with self._lock:
            if self._loaded:
                return

            for profile_file in self.storage_dir.glob("kol_*.json"):
                try:
                    profile = self._load_profile(profile_file)
                    self._cache[profile.kol_id] = profile
                    for identity in profile.platform_identities:
                        key = self._make_platform_key(identity.platform, identity.account_id)
                        self._platform_index[key] = profile.kol_id
                except Exception:
                    # 忽略损坏的文件
                    continue

            self._loaded = True

    def _make_platform_key(self, platform: str, account_id: str) -> str:
        """生成平台索引键。"""
        return f"{platform.lower()}:{account_id}"

    def _generate_kol_id(self) -> str:
        """生成唯一 KOL ID。"""
        return f"kol_{uuid.uuid4().hex[:12]}"

    def _get_profile_path(self, kol_id: str) -> Path:
        """获取档案文件路径。"""
        return self.storage_dir / f"{kol_id}.json"

    def _load_profile(self, path: Path) -> KOLProfile:
        """从文件加载档案。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return KOLProfile.model_validate(data)

    def _save_profile(self, profile: KOLProfile) -> None:
        """保存档案到文件。"""
        path = self._get_profile_path(profile.kol_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(profile.model_dump_json(indent=2))

    def get_or_create(
        self,
        platform: str,
        account_id: str,
        account_name: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> KOLProfile:
        """获取或创建 KOL 档案。

        如果该平台账号已关联到某个 KOL，返回已有档案。
        否则创建新档案。

        Args:
            platform: 平台标识
            account_id: 平台账号 ID
            account_name: 账号名称（可选）
            display_name: 显示名称（创建新档案时使用，默认用 account_name）

        Returns:
            KOL 档案
        """
        self._ensure_loaded()

        # 先查找是否已存在
        existing = self.find_by_platform(platform, account_id)
        if existing:
            return existing

        # 创建新档案
        kol_id = self._generate_kol_id()
        now = datetime.now()
        name = display_name or account_name or f"{platform}_{account_id}"

        profile = KOLProfile(
            kol_id=kol_id,
            display_name=name,
            platform_identities=[
                PlatformIdentity(
                    platform=platform,
                    account_id=account_id,
                    account_name=account_name,
                )
            ],
            created_at=now,
            updated_at=now,
        )

        # 保存并更新索引
        self._save_profile(profile)
        self._cache[kol_id] = profile
        key = self._make_platform_key(platform, account_id)
        self._platform_index[key] = kol_id

        return profile

    def find_by_platform(self, platform: str, account_id: str) -> Optional[KOLProfile]:
        """根据平台账号查找 KOL 档案。

        Args:
            platform: 平台标识
            account_id: 平台账号 ID

        Returns:
            KOL 档案，不存在则返回 None
        """
        self._ensure_loaded()

        key = self._make_platform_key(platform, account_id)
        kol_id = self._platform_index.get(key)
        if kol_id:
            return self._cache.get(kol_id)
        return None

    def get_by_kol_id(self, kol_id: str) -> Optional[KOLProfile]:
        """根据 KOL ID 获取档案。

        Args:
            kol_id: KOL 全局 ID

        Returns:
            KOL 档案，不存在则返回 None
        """
        self._ensure_loaded()
        return self._cache.get(kol_id)

    def link_platform(
        self,
        kol_id: str,
        platform: str,
        account_id: str,
        account_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        verified: bool = False,
        follower_count: Optional[int] = None,
    ) -> KOLProfile:
        """为 KOL 关联新平台账号。

        Args:
            kol_id: KOL 全局 ID
            platform: 平台标识
            account_id: 平台账号 ID
            account_name: 账号名称
            avatar_url: 头像 URL
            verified: 是否认证
            follower_count: 粉丝数

        Returns:
            更新后的档案

        Raises:
            ValueError: KOL 不存在或平台账号已被其他 KOL 占用
        """
        self._ensure_loaded()

        profile = self._cache.get(kol_id)
        if not profile:
            raise ValueError(f"KOL not found: {kol_id}")

        # 检查平台账号是否已被占用
        key = self._make_platform_key(platform, account_id)
        existing_kol_id = self._platform_index.get(key)
        if existing_kol_id and existing_kol_id != kol_id:
            raise ValueError(
                f"Platform account {platform}:{account_id} already linked to {existing_kol_id}"
            )

        # 检查是否已关联该平台
        if profile.has_platform(platform):
            # 更新现有身份信息
            for i, identity in enumerate(profile.platform_identities):
                if identity.platform == platform:
                    profile.platform_identities[i] = PlatformIdentity(
                        platform=platform,
                        account_id=account_id,
                        account_name=account_name or identity.account_name,
                        avatar_url=avatar_url or identity.avatar_url,
                        verified=verified or identity.verified,
                        follower_count=follower_count or identity.follower_count,
                    )
                    break
        else:
            # 添加新平台身份
            profile.platform_identities.append(
                PlatformIdentity(
                    platform=platform,
                    account_id=account_id,
                    account_name=account_name,
                    avatar_url=avatar_url,
                    verified=verified,
                    follower_count=follower_count,
                )
            )

        profile.updated_at = datetime.now()
        self._save_profile(profile)
        self._platform_index[key] = kol_id

        return profile

    def unlink_platform(self, kol_id: str, platform: str) -> KOLProfile:
        """解除平台关联。

        Args:
            kol_id: KOL 全局 ID
            platform: 要解除的平台

        Returns:
            更新后的档案

        Raises:
            ValueError: KOL 不存在或未关联该平台
        """
        self._ensure_loaded()

        profile = self._cache.get(kol_id)
        if not profile:
            raise ValueError(f"KOL not found: {kol_id}")

        if not profile.has_platform(platform):
            raise ValueError(f"KOL {kol_id} has no platform {platform}")

        identity = profile.get_platform_identity(platform)
        if identity:
            key = self._make_platform_key(platform, identity.account_id)
            self._platform_index.pop(key, None)

        profile.platform_identities = [
            i for i in profile.platform_identities if i.platform != platform
        ]
        profile.updated_at = datetime.now()
        self._save_profile(profile)

        return profile

    def update_profile(
        self,
        kol_id: str,
        display_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        rating: Optional[float] = None,
        bio: Optional[str] = None,
    ) -> KOLProfile:
        """更新 KOL 档案基本信息。

        Args:
            kol_id: KOL 全局 ID
            display_name: 显示名称
            tags: 标签列表
            rating: 评分
            bio: 简介

        Returns:
            更新后的档案

        Raises:
            ValueError: KOL 不存在
        """
        self._ensure_loaded()

        profile = self._cache.get(kol_id)
        if not profile:
            raise ValueError(f"KOL not found: {kol_id}")

        if display_name is not None:
            profile.display_name = display_name
        if tags is not None:
            profile.tags = tags
        if rating is not None:
            profile.rating = rating
        if bio is not None:
            profile.bio = bio

        profile.updated_at = datetime.now()
        self._save_profile(profile)

        return profile

    def list_all(self) -> list[KOLProfile]:
        """列出所有 KOL 档案。

        Returns:
            所有档案列表
        """
        self._ensure_loaded()
        return list(self._cache.values())

    def find_by_tag(self, tag: str) -> list[KOLProfile]:
        """根据标签查找 KOL。

        Args:
            tag: 标签

        Returns:
            匹配的档案列表
        """
        self._ensure_loaded()
        return [p for p in self._cache.values() if tag in p.tags]

    def delete(self, kol_id: str) -> bool:
        """删除 KOL 档案。

        Args:
            kol_id: KOL 全局 ID

        Returns:
            是否删除成功
        """
        self._ensure_loaded()

        profile = self._cache.get(kol_id)
        if not profile:
            return False

        # 清理索引
        for identity in profile.platform_identities:
            key = self._make_platform_key(identity.platform, identity.account_id)
            self._platform_index.pop(key, None)

        # 删除文件和缓存
        path = self._get_profile_path(kol_id)
        if path.exists():
            path.unlink()
        self._cache.pop(kol_id, None)

        return True


# 全局单例 (thread-safe)
from functools import lru_cache

@lru_cache(maxsize=1)
def get_kol_profile_manager() -> KOLProfileManager:
    """获取全局 KOL 档案管理器 (线程安全单例)。"""
    return KOLProfileManager()
