#!/usr/bin/env python3
"""Security verification and setup script.

This script helps you:
1. Verify security configuration
2. Generate API keys
3. Generate encryption keys
4. Test authentication

Usage:
    python scripts/verify_security.py
    python scripts/verify_security.py --generate-api-key
    python scripts/verify_security.py --generate-encryption-key
    python scripts/verify_security.py --test-auth
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def generate_api_key():
    """Generate a secure API key."""
    from finer.api.middleware.security import generate_api_key

    key = generate_api_key()
    print("\n=== Generated API Key ===")
    print(f"API_KEY={key}")
    print("\nAdd to your .env file:")
    print(f'  export API_KEY="{key}"')
    print("\nOr set directly:")
    print(f"  AUTH_ENABLED=true API_KEY={key} uvicorn finer.api.server:app")


def generate_encryption_key():
    """Generate a Fernet encryption key."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    print("\n=== Generated Encryption Key ===")
    print(f"FINER_ENCRYPTION_KEY={key}")
    print("\nAdd to your .env file:")
    print(f'  export FINER_ENCRYPTION_KEY="{key}"')
    print("\nIMPORTANT: Store this key securely! Tokens cannot be recovered without it.")


def verify_config():
    """Verify security configuration."""
    print("\n=== Security Configuration Check ===\n")

    # Check environment variables
    env_vars = {
        "AUTH_ENABLED": os.environ.get("AUTH_ENABLED", "false"),
        "API_KEY": "***SET***" if os.environ.get("API_KEY") else "NOT SET",
        "JWT_SECRET": "***SET***" if os.environ.get("JWT_SECRET") else "NOT SET",
        "FINER_ENCRYPTION_KEY": "***SET***" if os.environ.get("FINER_ENCRYPTION_KEY") else "NOT SET",
        "ALLOWED_ORIGINS": os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000"),
    }

    print("Environment Variables:")
    for key, value in env_vars.items():
        status = "✓" if value not in ["NOT SET", "false"] else "○"
        print(f"  {status} {key}: {value}")

    # Load auth config
    try:
        from finer.api.middleware.auth import get_auth_config
        config = get_auth_config()

        print("\nAuthentication Status:")
        print(f"  Enabled: {config.enabled}")
        print(f"  API Key Auth: {'Available' if config.api_key else 'Not configured'}")
        print(f"  JWT Auth: {'Available' if config.jwt_secret else 'Not configured'}")
        print(f"  Whitelisted paths: {len(config.whitelist)}")

        # Warnings
        print("\nSecurity Recommendations:")
        if not config.enabled:
            print("  ⚠️  Authentication is DISABLED. Enable for production.")
        if not os.environ.get("ALLOWED_ORIGINS"):
            print("  ⚠️  ALLOWED_ORIGINS not set. Using default localhost only.")
        if config.enabled and not config.api_key and not config.jwt_secret:
            print("  ❌ Authentication enabled but no auth method configured!")

        if config.enabled and (config.api_key or config.jwt_secret):
            print("  ✓ Authentication properly configured")

    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        return False

    return True


def test_auth():
    """Test authentication endpoints."""
    import requests

    base_url = "http://localhost:8000"

    print("\n=== Testing Authentication ===\n")

    # Test health endpoint (should always work)
    try:
        response = requests.get(f"{base_url}/api/health")
        if response.status_code == 200:
            print("✓ Health endpoint accessible")
        else:
            print(f"✗ Health endpoint failed: {response.status_code}")
    except requests.ConnectionError:
        print("✗ Cannot connect to API. Is the server running?")
        print("  Start with: uvicorn finer.api.server:app")
        return False

    # Test protected endpoint
    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("○ Skipping protected endpoint test (no API_KEY set)")
        return True

    # Test without auth
    response = requests.get(f"{base_url}/api/files")
    if response.status_code == 401:
        print("✓ Protected endpoint requires authentication")
    else:
        print(f"○ Protected endpoint returned {response.status_code} (auth may be disabled)")

    # Test with auth
    response = requests.get(
        f"{base_url}/api/files",
        headers={"X-API-Key": api_key}
    )
    if response.status_code == 200:
        print("✓ API key authentication works")
    elif response.status_code == 401:
        print("✗ API key authentication failed")
    else:
        print(f"○ API request returned {response.status_code}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Security verification and setup for Finer OS"
    )
    parser.add_argument(
        "--generate-api-key",
        action="store_true",
        help="Generate a new API key"
    )
    parser.add_argument(
        "--generate-encryption-key",
        action="store_true",
        help="Generate a new encryption key"
    )
    parser.add_argument(
        "--test-auth",
        action="store_true",
        help="Test authentication against running API"
    )

    args = parser.parse_args()

    # Change to project root
    os.chdir(project_root)

    if args.generate_api_key:
        generate_api_key()
    elif args.generate_encryption_key:
        generate_encryption_key()
    elif args.test_auth:
        test_auth()
    else:
        # Default: verify configuration
        success = verify_config()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
