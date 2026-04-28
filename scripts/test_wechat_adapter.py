#!/usr/bin/env python3
"""Test WeChat adapter imports and basic functionality."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    try:
        from finer.ingestion.wechat_adapter import WeChatAdapter, WeChatAuthClient, WeChatArticleClient
        print("✓ wechat_adapter imported successfully")
    except Exception as e:
        print(f"✗ Failed to import wechat_adapter: {e}")
        return False

    try:
        from finer.schemas.wechat import LoginSessionResponse, AccountResponse, ArticleResponse
        print("✓ wechat schemas imported successfully")
    except Exception as e:
        print(f"✗ Failed to import wechat schemas: {e}")
        return False

    try:
        from finer.api.routes.wechat import router
        print("✓ wechat API router imported successfully")
    except Exception as e:
        print(f"✗ Failed to import wechat router: {e}")
        return False

    return True


def test_adapter_creation():
    """Test that adapter can be created."""
    print("\nTesting adapter creation...")

    try:
        from finer.ingestion.wechat_adapter import WeChatAdapter
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = WeChatAdapter(root=Path(tmpdir))
            print(f"✓ Adapter created with cache_dir: {adapter.cache_dir}")
            print(f"✓ Output dir: {adapter.output_dir}")
            return True
    except Exception as e:
        print(f"✗ Failed to create adapter: {e}")
        return False


def test_schema_validation():
    """Test schema validation."""
    print("\nTesting schema validation...")

    try:
        from finer.schemas.wechat import (
            LoginSessionResponse,
            LoginStatus,
            AccountResponse,
            ArticleResponse,
        )
        from datetime import datetime

        # Test login session response
        session = LoginSessionResponse(
            session_id="test-123",
            qr_url="https://example.com/qr/test",
            status=LoginStatus.PENDING,
        )
        print(f"✓ LoginSessionResponse: {session.session_id}")

        # Test account response
        account = AccountResponse(
            account_id="gh_12345",
            account_name="测试公众号",
            article_count=10,
            is_valid=True,
        )
        print(f"✓ AccountResponse: {account.account_name}")

        # Test article response
        article = ArticleResponse(
            article_id="article-001",
            title="测试文章",
            author="作者",
            read_count=100,
        )
        print(f"✓ ArticleResponse: {article.title}")

        return True
    except Exception as e:
        print(f"✗ Schema validation failed: {e}")
        return False


def test_api_routes():
    """Test API route definitions."""
    print("\nTesting API routes...")

    try:
        from finer.api.routes.wechat import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/wechat")

        routes = [r.path for r in app.routes]
        wechat_routes = [r for r in routes if "/wechat" in r]

        print(f"✓ Found {len(wechat_routes)} WeChat routes:")
        for r in wechat_routes:
            print(f"  - {r}")

        return True
    except Exception as e:
        print(f"✗ API routes test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("WeChat Adapter Module Test")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Adapter Creation", test_adapter_creation()))
    results.append(("Schema Validation", test_schema_validation()))
    results.append(("API Routes", test_api_routes()))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("-" * 40)

    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")

    print("=" * 60)

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n✓ All tests passed! WeChat adapter module is ready.")
        print("\nUsage:")
        print("  1. Start the backend: python -m finer.api.server")
        print("  2. API endpoints available at: http://127.0.0.1:8000/api/wechat")
        print("  3. Test login: POST /api/wechat/login")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
