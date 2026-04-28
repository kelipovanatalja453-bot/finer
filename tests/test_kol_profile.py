"""KOL Profile 管理模块测试。"""

import tempfile
from pathlib import Path

import pytest

from finer.schemas.kol_profile import KOLProfile, PlatformIdentity
from finer.services.kol_profile import KOLProfileManager


@pytest.fixture
def temp_storage():
    """创建临时存储目录。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manager(temp_storage):
    """创建使用临时存储的管理器。"""
    return KOLProfileManager(storage_dir=temp_storage)


class TestKOLProfileSchema:
    """测试 KOL Profile Schema。"""

    def test_create_platform_identity(self):
        """测试创建平台身份。"""
        identity = PlatformIdentity(
            platform="wechat",
            account_id="test123",
            account_name="测试账号",
            verified=True,
        )
        assert identity.platform == "wechat"
        assert identity.account_id == "test123"
        assert identity.account_name == "测试账号"
        assert identity.verified is True
        assert identity.follower_count is None

    def test_create_kol_profile(self):
        """测试创建 KOL 档案。"""
        from datetime import datetime

        profile = KOLProfile(
            kol_id="kol_abc123",
            display_name="测试 KOL",
            platform_identities=[
                PlatformIdentity(platform="wechat", account_id="wx123"),
            ],
            tags=["crypto", "macro"],
            rating=4.5,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert profile.kol_id == "kol_abc123"
        assert profile.display_name == "测试 KOL"
        assert len(profile.platform_identities) == 1
        assert "crypto" in profile.tags
        assert profile.rating == 4.5

    def test_get_platform_identity(self):
        """测试获取平台身份。"""
        from datetime import datetime

        profile = KOLProfile(
            kol_id="kol_test",
            display_name="Test",
            platform_identities=[
                PlatformIdentity(platform="wechat", account_id="wx1"),
                PlatformIdentity(platform="bilibili", account_id="bili1"),
            ],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        wechat = profile.get_platform_identity("wechat")
        assert wechat is not None
        assert wechat.account_id == "wx1"

        twitter = profile.get_platform_identity("twitter")
        assert twitter is None

    def test_has_platform(self):
        """测试检查平台关联。"""
        from datetime import datetime

        profile = KOLProfile(
            kol_id="kol_test",
            display_name="Test",
            platform_identities=[
                PlatformIdentity(platform="wechat", account_id="wx1"),
            ],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert profile.has_platform("wechat") is True
        assert profile.has_platform("twitter") is False


class TestKOLProfileManager:
    """测试 KOL 档案管理器。"""

    def test_get_or_create_new(self, manager):
        """测试创建新档案。"""
        profile = manager.get_or_create(
            platform="wechat",
            account_id="wx123",
            account_name="测试号",
        )

        assert profile.kol_id.startswith("kol_")
        assert profile.display_name == "测试号"
        assert profile.has_platform("wechat")
        assert profile.get_platform_identity("wechat").account_id == "wx123"

    def test_get_or_create_existing(self, manager):
        """测试获取已有档案。"""
        # 第一次创建
        profile1 = manager.get_or_create(
            platform="bilibili",
            account_id="bili456",
        )

        # 第二次应该返回同一个
        profile2 = manager.get_or_create(
            platform="bilibili",
            account_id="bili456",
        )

        assert profile1.kol_id == profile2.kol_id

    def test_find_by_platform(self, manager):
        """测试根据平台账号查找。"""
        manager.get_or_create(
            platform="feishu",
            account_id="feishu789",
            account_name="飞书号",
        )

        found = manager.find_by_platform("feishu", "feishu789")
        assert found is not None
        assert found.display_name == "飞书号"

        not_found = manager.find_by_platform("feishu", "notexist")
        assert not_found is None

    def test_link_platform(self, manager):
        """测试关联新平台。"""
        profile = manager.get_or_create(
            platform="wechat",
            account_id="wx1",
            display_name="测试 KOL",
        )

        # 关联 B站账号
        updated = manager.link_platform(
            kol_id=profile.kol_id,
            platform="bilibili",
            account_id="bili1",
            account_name="B站账号",
            verified=True,
        )

        assert updated.has_platform("bilibili")
        assert updated.get_platform_identity("bilibili").account_name == "B站账号"
        assert updated.get_platform_identity("bilibili").verified is True

    def test_link_platform_already_occupied(self, manager):
        """测试关联已被占用的平台账号。"""
        profile1 = manager.get_or_create(
            platform="wechat",
            account_id="wx1",
        )
        profile2 = manager.get_or_create(
            platform="bilibili",
            account_id="bili1",
        )

        with pytest.raises(ValueError, match="already linked"):
            manager.link_platform(
                kol_id=profile1.kol_id,
                platform="bilibili",
                account_id="bili1",
            )

    def test_unlink_platform(self, manager):
        """测试解除平台关联。"""
        profile = manager.get_or_create(
            platform="wechat",
            account_id="wx1",
        )
        manager.link_platform(
            kol_id=profile.kol_id,
            platform="bilibili",
            account_id="bili1",
        )

        updated = manager.unlink_platform(profile.kol_id, "bilibili")
        assert not updated.has_platform("bilibili")
        assert updated.has_platform("wechat")

    def test_update_profile(self, manager):
        """测试更新档案信息。"""
        profile = manager.get_or_create(
            platform="wechat",
            account_id="wx1",
        )

        updated = manager.update_profile(
            kol_id=profile.kol_id,
            display_name="新名称",
            tags=["crypto", "defi"],
            rating=4.8,
            bio="这是简介",
        )

        assert updated.display_name == "新名称"
        assert updated.tags == ["crypto", "defi"]
        assert updated.rating == 4.8
        assert updated.bio == "这是简介"

    def test_list_all(self, manager):
        """测试列出所有档案。"""
        manager.get_or_create("wechat", "wx1")
        manager.get_or_create("bilibili", "bili1")

        all_profiles = manager.list_all()
        assert len(all_profiles) == 2

    def test_find_by_tag(self, manager):
        """测试根据标签查找。"""
        profile = manager.get_or_create("wechat", "wx1")
        manager.update_profile(profile.kol_id, tags=["crypto", "macro"])

        profile2 = manager.get_or_create("bilibili", "bili1")
        manager.update_profile(profile2.kol_id, tags=["tech"])

        crypto_kols = manager.find_by_tag("crypto")
        assert len(crypto_kols) == 1
        assert crypto_kols[0].kol_id == profile.kol_id

    def test_delete(self, manager):
        """测试删除档案。"""
        profile = manager.get_or_create("wechat", "wx1")

        result = manager.delete(profile.kol_id)
        assert result is True

        found = manager.find_by_platform("wechat", "wx1")
        assert found is None

        # 删除不存在的档案
        result = manager.delete("kol_notexist")
        assert result is False

    def test_persistence(self, temp_storage):
        """测试持久化。"""
        # 第一个管理器创建档案
        manager1 = KOLProfileManager(storage_dir=temp_storage)
        profile = manager1.get_or_create("wechat", "wx1", account_name="持久化测试")
        kol_id = profile.kol_id

        # 新管理器应该能加载
        manager2 = KOLProfileManager(storage_dir=temp_storage)
        loaded = manager2.get_by_kol_id(kol_id)
        assert loaded is not None
        assert loaded.display_name == "持久化测试"
