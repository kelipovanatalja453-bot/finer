"""Security utilities for Finer OS.

Provides utilities for token management, encryption, and security helpers.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Security configuration for token management."""
    encryption_key: Optional[bytes] = None
    token_expire_days: int = 30
    enable_encryption: bool = True

    def __post_init__(self):
        """Initialize encryption key if not provided."""
        if self.enable_encryption and not self.encryption_key:
            # Derive key from environment variable
            key_secret = os.environ.get("FINER_ENCRYPTION_KEY", "")
            if key_secret:
                self.encryption_key = self._derive_key(key_secret)
            else:
                # Generate a random key for this session
                # In production, should always use FINER_ENCRYPTION_KEY
                self.encryption_key = Fernet.generate_key()
                logger.warning(
                    "FINER_ENCRYPTION_KEY not set. Using session-specific key. "
                    "Tokens will not persist across restarts."
                )

    @staticmethod
    def _derive_key(password: str, salt: Optional[bytes] = None) -> bytes:
        """Derive Fernet key from password.

        Args:
            password: Password string
            salt: Optional salt (uses fixed salt if not provided)

        Returns:
            Fernet-compatible key
        """
        if salt is None:
            # Use project-specific salt
            salt = b"FinerOS-TokenEncryption-v1"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key


class TokenManager:
    """Secure token storage and management.

    Provides:
    - Encrypted token storage
    - Automatic expiration checking
    - Token refresh tracking
    """

    def __init__(
        self,
        cache_dir: Path,
        config: Optional[SecurityConfig] = None
    ):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or SecurityConfig()

        # Initialize Fernet cipher
        if self.config.encryption_key:
            self.cipher = Fernet(self.config.encryption_key)
        else:
            self.cipher = None
            logger.warning("Token encryption disabled. Tokens stored in plaintext!")

        # Token cache file
        self.tokens_file = self.cache_dir / "tokens.enc"

    def store_token(
        self,
        token_id: str,
        token_data: Dict[str, Any],
        expire_days: Optional[int] = None
    ) -> None:
        """Store a token securely.

        Args:
            token_id: Unique token identifier
            token_data: Token data to store
            expire_days: Days until expiration (default from config)
        """
        expire_days = expire_days or self.config.token_expire_days

        # Add metadata
        token_entry = {
            "id": token_id,
            "data": token_data,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=expire_days)).isoformat(),
            "is_valid": True,
        }

        # Load existing tokens
        tokens = self._load_tokens()

        # Add new token
        tokens[token_id] = token_entry

        # Save tokens
        self._save_tokens(tokens)

        logger.info(f"Stored token: {token_id} (expires in {expire_days} days)")

    def get_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get a token by ID.

        Returns None if token doesn't exist, is expired, or invalid.

        Args:
            token_id: Token identifier

        Returns:
            Token data or None
        """
        tokens = self._load_tokens()
        entry = tokens.get(token_id)

        if not entry:
            return None

        # Check expiration
        if self._is_expired(entry):
            logger.warning(f"Token expired: {token_id}")
            # Mark as invalid
            entry["is_valid"] = False
            self._save_tokens(tokens)
            return None

        # Check validity flag
        if not entry.get("is_valid", True):
            return None

        return entry.get("data")

    def refresh_token(self, token_id: str, expire_days: Optional[int] = None) -> bool:
        """Refresh a token's expiration.

        Args:
            token_id: Token identifier
            expire_days: New expiration days

        Returns:
            True if refreshed, False if token not found
        """
        tokens = self._load_tokens()
        entry = tokens.get(token_id)

        if not entry:
            return False

        # Update expiration
        expire_days = expire_days or self.config.token_expire_days
        entry["expires_at"] = (datetime.now() + timedelta(days=expire_days)).isoformat()
        entry["is_valid"] = True
        entry["refreshed_at"] = datetime.now().isoformat()

        self._save_tokens(tokens)

        logger.info(f"Refreshed token: {token_id}")
        return True

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token.

        Args:
            token_id: Token identifier

        Returns:
            True if revoked, False if not found
        """
        tokens = self._load_tokens()
        entry = tokens.get(token_id)

        if not entry:
            return False

        entry["is_valid"] = False
        entry["revoked_at"] = datetime.now().isoformat()

        self._save_tokens(tokens)

        logger.info(f"Revoked token: {token_id}")
        return True

    def list_valid_tokens(self) -> Dict[str, Dict[str, Any]]:
        """List all valid (non-expired) tokens.

        Returns:
            Dict of token_id -> token_data
        """
        tokens = self._load_tokens()
        valid_tokens = {}

        for token_id, entry in tokens.items():
            if entry.get("is_valid", True) and not self._is_expired(entry):
                valid_tokens[token_id] = entry.get("data")

        return valid_tokens

    def cleanup_expired(self) -> int:
        """Remove expired tokens.

        Returns:
            Number of tokens removed
        """
        tokens = self._load_tokens()
        expired_ids = [
            token_id for token_id, entry in tokens.items()
            if self._is_expired(entry)
        ]

        for token_id in expired_ids:
            del tokens[token_id]

        if expired_ids:
            self._save_tokens(tokens)
            logger.info(f"Cleaned up {len(expired_ids)} expired tokens")

        return len(expired_ids)

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if token entry is expired."""
        expires_at_str = entry.get("expires_at")
        if not expires_at_str:
            return False

        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.now() > expires_at
        except ValueError:
            return True

    def _load_tokens(self) -> Dict[str, Dict[str, Any]]:
        """Load tokens from encrypted storage."""
        if not self.tokens_file.exists():
            return {}

        try:
            encrypted_data = self.tokens_file.read_bytes()

            # Decrypt if encryption enabled
            if self.cipher:
                decrypted_data = self.cipher.decrypt(encrypted_data)
            else:
                decrypted_data = encrypted_data

            return json.loads(decrypted_data.decode("utf-8"))

        except InvalidToken:
            logger.error("Failed to decrypt tokens. Key may have changed.")
            return {}
        except Exception as e:
            logger.error(f"Failed to load tokens: {e}")
            return {}

    def _save_tokens(self, tokens: Dict[str, Dict[str, Any]]) -> None:
        """Save tokens to encrypted storage."""
        try:
            data = json.dumps(tokens, indent=2, ensure_ascii=False).encode("utf-8")

            # Encrypt if encryption enabled
            if self.cipher:
                encrypted_data = self.cipher.encrypt(data)
            else:
                encrypted_data = data

            self.tokens_file.write_bytes(encrypted_data)

        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            raise


class SecureTokenStorage:
    """High-level secure token storage for WeChat and other integrations.

    Provides a simple interface for storing and retrieving authentication
    tokens with automatic encryption and expiration.
    """

    def __init__(self, cache_dir: Path, config: Optional[SecurityConfig] = None):
        self.token_manager = TokenManager(cache_dir, config)

    def store_wechat_token(
        self,
        account_id: str,
        token: str,
        cookie: str,
        account_name: str = "",
        expire_days: int = 7
    ) -> None:
        """Store WeChat authentication token.

        Args:
            account_id: WeChat account ID
            token: Authentication token
            cookie: Session cookie
            account_name: Account display name
            expire_days: Token expiration (WeChat tokens expire quickly)
        """
        token_data = {
            "type": "wechat",
            "account_id": account_id,
            "account_name": account_name,
            "token": token,
            "cookie": cookie,
        }
        self.token_manager.store_token(f"wechat_{account_id}", token_data, expire_days)

    def get_wechat_token(self, account_id: str) -> Optional[Dict[str, str]]:
        """Get WeChat authentication token.

        Args:
            account_id: WeChat account ID

        Returns:
            Dict with token, cookie, account_name or None if expired/invalid
        """
        data = self.token_manager.get_token(f"wechat_{account_id}")
        if data:
            return {
                "token": data.get("token", ""),
                "cookie": data.get("cookie", ""),
                "account_name": data.get("account_name", ""),
            }
        return None

    def refresh_wechat_token(self, account_id: str, expire_days: int = 7) -> bool:
        """Refresh WeChat token expiration.

        Args:
            account_id: WeChat account ID
            expire_days: New expiration days

        Returns:
            True if refreshed, False if not found
        """
        return self.token_manager.refresh_token(f"wechat_{account_id}", expire_days)

    def is_token_valid(self, account_id: str) -> bool:
        """Check if WeChat token is valid and not expired.

        Args:
            account_id: WeChat account ID

        Returns:
            True if valid, False otherwise
        """
        return self.token_manager.get_token(f"wechat_{account_id}") is not None


def generate_api_key(length: int = 32) -> str:
    """Generate a secure random API key.

    Args:
        length: Key length in bytes

    Returns:
        URL-safe API key string
    """
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash a password with salt.

    Args:
        password: Password to hash
        salt: Optional salt (generated if not provided)

    Returns:
        Hash string in format: salt$hash
    """
    if salt is None:
        salt = secrets.token_hex(16)

    # Use SHA-256 for hashing
    hash_value = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${hash_value}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash.

    Args:
        password: Password to verify
        stored_hash: Stored hash in format: salt$hash

    Returns:
        True if password matches
    """
    try:
        salt, hash_value = stored_hash.split("$")
        computed_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(computed_hash, hash_value)
    except ValueError:
        return False
