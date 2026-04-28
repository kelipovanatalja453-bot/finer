"""Tests for security utilities."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from finer.api.middleware.security import (
    SecurityConfig,
    TokenManager,
    SecureTokenStorage,
    generate_api_key,
    hash_password,
    verify_password,
)


def test_generate_api_key():
    """Test API key generation."""
    key1 = generate_api_key()
    key2 = generate_api_key()

    # Keys should be different
    assert key1 != key2

    # Keys should be URL-safe strings
    assert isinstance(key1, str)
    assert len(key1) > 30  # Default length is 32 bytes


def test_password_hashing():
    """Test password hashing and verification."""
    password = "test-password-123"

    # Hash password
    hashed = hash_password(password)

    # Hash should be different from password
    assert hashed != password

    # Hash should contain salt
    assert "$" in hashed

    # Verify correct password
    assert verify_password(password, hashed) is True

    # Verify wrong password
    assert verify_password("wrong-password", hashed) is False


def test_password_hashing_with_salt():
    """Test password hashing with custom salt."""
    password = "test-password"
    salt = "custom-salt-123"

    hashed1 = hash_password(password, salt)
    hashed2 = hash_password(password, salt)

    # Same salt should produce same hash
    assert hashed1 == hashed2


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_token_manager_store_and_get(temp_cache_dir):
    """Test token storage and retrieval."""
    manager = TokenManager(
        temp_cache_dir,
        config=SecurityConfig(enable_encryption=False)
    )

    # Store token
    token_data = {"user": "test", "value": "secret123"}
    manager.store_token("token1", token_data, expire_days=1)

    # Retrieve token
    retrieved = manager.get_token("token1")
    assert retrieved is not None
    assert retrieved["user"] == "test"
    assert retrieved["value"] == "secret123"


def test_token_manager_expiration(temp_cache_dir):
    """Test token expiration."""
    manager = TokenManager(
        temp_cache_dir,
        config=SecurityConfig(enable_encryption=False)
    )

    # Store token that expired in the past (negative days)
    token_data = {"user": "test"}
    manager.store_token("token1", token_data, expire_days=-1)

    # Token should be expired
    retrieved = manager.get_token("token1")
    assert retrieved is None


def test_token_manager_refresh(temp_cache_dir):
    """Test token refresh."""
    manager = TokenManager(
        temp_cache_dir,
        config=SecurityConfig(enable_encryption=False)
    )

    # Store token
    token_data = {"user": "test"}
    manager.store_token("token1", token_data, expire_days=1)

    # Refresh token
    success = manager.refresh_token("token1", expire_days=7)
    assert success is True

    # Token should still be valid
    retrieved = manager.get_token("token1")
    assert retrieved is not None


def test_token_manager_revoke(temp_cache_dir):
    """Test token revocation."""
    manager = TokenManager(
        temp_cache_dir,
        config=SecurityConfig(enable_encryption=False)
    )

    # Store and revoke token
    token_data = {"user": "test"}
    manager.store_token("token1", token_data, expire_days=1)

    success = manager.revoke_token("token1")
    assert success is True

    # Token should be invalid
    retrieved = manager.get_token("token1")
    assert retrieved is None


def test_token_manager_encryption(temp_cache_dir):
    """Test encrypted token storage."""
    # Generate a key for testing
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()

    manager = TokenManager(
        temp_cache_dir,
        config=SecurityConfig(
            encryption_key=key,
            enable_encryption=True
        )
    )

    # Store token
    token_data = {"user": "test", "secret": "sensitive-data"}
    manager.store_token("token1", token_data, expire_days=1)

    # Retrieve token
    retrieved = manager.get_token("token1")
    assert retrieved is not None
    assert retrieved["secret"] == "sensitive-data"

    # Verify file is encrypted
    tokens_file = temp_cache_dir / "tokens.enc"
    content = tokens_file.read_bytes()
    # Encrypted content should not contain plaintext
    assert b"sensitive-data" not in content


def test_secure_token_storage_wechat(temp_cache_dir):
    """Test WeChat token storage."""
    storage = SecureTokenStorage(
        temp_cache_dir,
        config=SecurityConfig(enable_encryption=False)
    )

    # Store WeChat token
    storage.store_wechat_token(
        account_id="test_account",
        token="test_token_123",
        cookie="test_cookie_abc",
        account_name="测试公众号",
        expire_days=7
    )

    # Retrieve token
    token_data = storage.get_wechat_token("test_account")
    assert token_data is not None
    assert token_data["token"] == "test_token_123"
    assert token_data["cookie"] == "test_cookie_abc"
    assert token_data["account_name"] == "测试公众号"

    # Check validity
    assert storage.is_token_valid("test_account") is True


def test_secure_token_storage_refresh(temp_cache_dir):
    """Test WeChat token refresh."""
    storage = SecureTokenStorage(
        temp_cache_dir,
        config=SecurityConfig(enable_encryption=False)
    )

    # Store token
    storage.store_wechat_token(
        account_id="test_account",
        token="test_token",
        cookie="test_cookie",
        expire_days=1
    )

    # Refresh token
    success = storage.refresh_wechat_token("test_account", expire_days=7)
    assert success is True

    # Token should still be valid
    assert storage.is_token_valid("test_account") is True


def test_security_config_key_derivation():
    """Test encryption key derivation."""
    password = "test-password-123"

    config1 = SecurityConfig(enable_encryption=False)
    key1 = config1._derive_key(password)

    config2 = SecurityConfig(enable_encryption=False)
    key2 = config2._derive_key(password)

    # Same password should derive same key (due to fixed salt)
    assert key1 == key2

    # Keys should be valid Fernet keys
    from cryptography.fernet import Fernet
    Fernet(key1)  # Should not raise
