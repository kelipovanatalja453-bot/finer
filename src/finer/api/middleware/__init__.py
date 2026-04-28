"""API Middleware package.

Provides security, authentication, and other middleware for FastAPI.
"""

from finer.api.middleware.auth import (
    AuthConfig,
    AuthResult,
    APIKeyAuthMiddleware,
    create_jwt_token,
    get_auth_config,
    setup_auth_middleware,
)
from finer.api.middleware.security import (
    SecurityConfig,
    TokenManager,
    SecureTokenStorage,
    generate_api_key,
    hash_password,
    verify_password,
)

__all__ = [
    # Auth
    "AuthConfig",
    "AuthResult",
    "APIKeyAuthMiddleware",
    "create_jwt_token",
    "get_auth_config",
    "setup_auth_middleware",
    # Security
    "SecurityConfig",
    "TokenManager",
    "SecureTokenStorage",
    "generate_api_key",
    "hash_password",
    "verify_password",
]
