"""Security middleware for Finer API.

Provides authentication and authorization for API endpoints.
"""

from __future__ import annotations

import os
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Callable, List, Optional, Set
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from finer.errors import ErrorCode, error_response

logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    """Authentication configuration.

    All settings are loaded from environment variables for security.
    Default is disabled (development-friendly).
    """
    enabled: bool = field(default_factory=lambda: os.environ.get("AUTH_ENABLED", "false").lower() == "true")
    api_key: str = field(default_factory=lambda: os.environ.get("API_KEY", ""))
    jwt_secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET", ""))
    jwt_algorithm: str = field(default_factory=lambda: os.environ.get("JWT_ALGORITHM", "HS256"))
    token_expire_hours: int = field(default_factory=lambda: int(os.environ.get("TOKEN_EXPIRE_HOURS", "24")))

    # Whitelist paths that don't require authentication
    whitelist: List[str] = field(default_factory=lambda: [
        "/api/health",
        "/api/docs",
        "/openapi.json",
        "/docs",
        "/redoc",
    ])

    # Sensitive operations require additional verification
    sensitive_paths: Set[str] = field(default_factory=lambda: {
        "/api/files/delete",
        "/api/wechat/accounts",  # DELETE operations
        "/api/backtest",  # If exists
    })

    def validate(self) -> bool:
        """Validate configuration.

        Returns True if config is valid, raises ValueError otherwise.
        """
        if self.enabled:
            if not self.api_key and not self.jwt_secret:
                raise ValueError(
                    "AUTH_ENABLED=true but neither API_KEY nor JWT_SECRET is set. "
                    "Please set at least one authentication method."
                )
        return True


@lru_cache()
def get_auth_config() -> AuthConfig:
    """Get cached auth configuration."""
    config = AuthConfig()
    config.validate()
    return config


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API Key authentication middleware.

    Supports two authentication methods:
    1. API Key via X-API-Key header
    2. JWT token via Authorization header (if JWT_SECRET is set)

    For development, authentication is disabled by default.
    Enable via AUTH_ENABLED=true environment variable.
    """

    def __init__(self, app: FastAPI, config: Optional[AuthConfig] = None):
        super().__init__(app)
        self.config = config or get_auth_config()
        logger.info(f"Auth middleware initialized: enabled={self.config.enabled}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through authentication."""

        # Skip authentication if disabled
        if not self.config.enabled:
            return await call_next(request)

        # Check whitelist
        if self._is_whitelisted(request.url.path):
            return await call_next(request)

        # Authenticate request
        auth_result = self._authenticate(request)
        if not auth_result.success:
            return error_response(
                ErrorCode.SYS_AUTH_001,
                auth_result.error_message,
                details=self._request_details(request),
            )

        # Check sensitive operations
        if self._is_sensitive(request):
            # Require re-authentication for sensitive operations
            sensitive_auth = request.headers.get("X-Sensitive-Auth")
            if not sensitive_auth or not self._verify_sensitive_auth(sensitive_auth):
                return error_response(
                    ErrorCode.SYS_PERM_001,
                    "Sensitive operation requires additional authentication",
                    details=self._request_details(request),
                )

        # Store auth info in request state
        request.state.auth_user = auth_result.user_id
        request.state.auth_method = auth_result.method

        return await call_next(request)

    def _is_whitelisted(self, path: str) -> bool:
        """Check if path is in whitelist."""
        for whitelist_path in self.config.whitelist:
            if path.startswith(whitelist_path):
                return True
        return False

    def _is_sensitive(self, request: Request) -> bool:
        """Check if this is a sensitive operation."""
        # DELETE methods are always sensitive
        if request.method == "DELETE":
            return True

        # Check sensitive paths
        path = request.url.path
        for sensitive_path in self.config.sensitive_paths:
            if path.startswith(sensitive_path):
                return True

        return False

    def _authenticate(self, request: Request) -> AuthResult:
        """Authenticate request using available methods."""

        # Try API Key first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            if self._verify_api_key(api_key):
                return AuthResult(
                    success=True,
                    method="api_key",
                    user_id="api_user"
                )
            return AuthResult(
                success=False,
                error_message="Invalid API key"
            )

        # Try JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            jwt_result = self._verify_jwt(token)
            if jwt_result.success:
                return jwt_result
            return AuthResult(
                success=False,
                error_message=jwt_result.error_message
            )

        # No authentication provided
        return AuthResult(
            success=False,
            error_message="Missing authentication. Provide X-API-Key header or Authorization Bearer token."
        )

    def _verify_api_key(self, api_key: str) -> bool:
        """Verify API key using constant-time comparison."""
        if not self.config.api_key:
            return False
        return secrets.compare_digest(api_key, self.config.api_key)

    def _verify_jwt(self, token: str) -> AuthResult:
        """Verify JWT token.

        Requires pyjwt package: pip install pyjwt
        """
        if not self.config.jwt_secret:
            return AuthResult(
                success=False,
                error_message="JWT authentication not configured"
            )

        try:
            import jwt
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm]
            )
            user_id = payload.get("sub") or payload.get("user_id")
            return AuthResult(
                success=True,
                method="jwt",
                user_id=user_id
            )
        except ImportError:
            logger.warning("pyjwt not installed, JWT verification unavailable")
            return AuthResult(
                success=False,
                error_message="JWT authentication unavailable (pyjwt not installed)"
            )
        except jwt.ExpiredSignatureError:
            return AuthResult(
                success=False,
                error_message="JWT token expired"
            )
        except jwt.InvalidTokenError as e:
            return AuthResult(
                success=False,
                error_message=f"Invalid JWT token: {str(e)}"
            )

    def _verify_sensitive_auth(self, auth_code: str) -> bool:
        """Verify additional authentication for sensitive operations.

        For sensitive operations, require either:
        - The same API key (re-sent as X-Sensitive-Auth)
        - A time-based one-time code
        """
        # Re-verify API key
        if self.config.api_key and secrets.compare_digest(auth_code, self.config.api_key):
            return True

        # Could implement TOTP here for additional security
        # For now, just require API key re-verification
        return False

    def _request_details(self, request: Request) -> dict[str, str]:
        return {
            "request_id": request.headers.get("X-Request-ID") or str(uuid4()),
        }


@dataclass
class AuthResult:
    """Authentication result."""
    success: bool
    method: Optional[str] = None
    user_id: Optional[str] = None
    error_message: Optional[str] = None


def create_jwt_token(
    user_id: str,
    secret: str,
    algorithm: str = "HS256",
    expire_hours: int = 24,
    **extra_claims
) -> str:
    """Create a JWT token for testing or internal use.

    Args:
        user_id: User identifier
        secret: JWT secret
        algorithm: JWT algorithm
        expire_hours: Token expiration in hours
        **extra_claims: Additional claims to include

    Returns:
        JWT token string
    """
    try:
        import jwt
    except ImportError:
        raise ImportError("pyjwt required for JWT token creation: pip install pyjwt")

    payload = {
        "sub": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expire_hours),
        **extra_claims
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def setup_auth_middleware(app: FastAPI, config: Optional[AuthConfig] = None) -> None:
    """Setup authentication middleware on FastAPI app.

    Args:
        app: FastAPI application
        config: Optional auth config (defaults to environment-based config)
    """
    config = config or get_auth_config()
    app.add_middleware(APIKeyAuthMiddleware, config=config)
    logger.info(f"Authentication middleware configured: enabled={config.enabled}")
