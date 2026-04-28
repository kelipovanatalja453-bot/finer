#!/usr/bin/env python3
"""Test GLM-5.1 API connection for both text and vision."""

import os
import sys
import base64
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx


def test_glm_text():
    """Test GLM-5.1 text API."""
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        print("❌ GLM_API_KEY not set")
        return False

    print(f"✓ GLM_API_KEY found: {api_key[:10]}...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "curl/8.0",
    }

    data = {
        "model": "GLM-5.1",
        "messages": [{"role": "user", "content": "你好，请用一句话回复确认你可以正常工作。"}],
        "max_tokens": 100,
    }

    try:
        with httpx.Client(timeout=30.0, http2=False) as client:
            response = client.post(
                "https://api.svips.org/v1/chat/completions",
                headers=headers,
                json=data,
            )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✓ GLM-5.1 Text API 成功!")
            print(f"  回复: {content}")
            return True
        else:
            print(f"❌ GLM-5.1 Text API 错误: {response.status_code}")
            print(f"  响应: {response.text[:300]}")
            return False
    except Exception as e:
        print(f"❌ GLM-5.1 Text API 异常: {e}")
        return False


def test_glm_vision():
    """Test GLM-5.1 vision API with a simple test image."""
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        print("❌ GLM_API_KEY not set")
        return False

    # Create a 100x100 red square PNG (minimum size for most vision models)
    # This is a valid PNG with red pixels
    import struct
    import zlib

    def create_simple_png(width, height, color):
        """Create a simple solid color PNG."""
        def png_chunk(chunk_type, data):
            chunk_len = struct.pack('>I', len(data))
            chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
            return chunk_len + chunk_type + data + chunk_crc

        # PNG signature
        signature = b'\x89PNG\r\n\x1a\n'

        # IHDR chunk
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        ihdr = png_chunk(b'IHDR', ihdr_data)

        # IDAT chunk (raw image data)
        raw_data = b''
        for y in range(height):
            raw_data += b'\x00'  # filter byte
            for x in range(width):
                raw_data += bytes(color)

        compressed = zlib.compress(raw_data, 9)
        idat = png_chunk(b'IDAT', compressed)

        # IEND chunk
        iend = png_chunk(b'IEND', b'')

        return signature + ihdr + idat + iend

    # Create a 100x100 red PNG
    png_data = create_simple_png(100, 100, (255, 0, 0))
    base64_image = base64.b64encode(png_data).decode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "curl/8.0",
    }

    data = {
        "model": "GLM-5.1",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请简单描述这张图片。"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        "max_tokens": 100,
    }

    try:
        with httpx.Client(timeout=30.0, http2=False) as client:
            response = client.post(
                "https://api.svips.org/v1/chat/completions",
                headers=headers,
                json=data,
            )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✓ GLM-5.1 Vision API 成功!")
            print(f"  回复: {content}")
            return True
        else:
            print(f"❌ GLM-5.1 Vision API 错误: {response.status_code}")
            print(f"  响应: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ GLM-5.1 Vision API 异常: {e}")
        return False


def test_qwen_vision():
    """Test Qwen-VL-Plus as fallback."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("⚠ DASHSCOPE_API_KEY not set (Qwen fallback unavailable)")
        return None

    print(f"✓ DASHSCOPE_API_KEY found: {api_key[:10]}...")

    # Create a 100x100 red square PNG (minimum size for most vision models)
    import struct
    import zlib

    def create_simple_png(width, height, color):
        """Create a simple solid color PNG."""
        def png_chunk(chunk_type, data):
            chunk_len = struct.pack('>I', len(data))
            chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
            return chunk_len + chunk_type + data + chunk_crc

        # PNG signature
        signature = b'\x89PNG\r\n\x1a\n'

        # IHDR chunk
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        ihdr = png_chunk(b'IHDR', ihdr_data)

        # IDAT chunk (raw image data)
        raw_data = b''
        for y in range(height):
            raw_data += b'\x00'  # filter byte
            for x in range(width):
                raw_data += bytes(color)

        compressed = zlib.compress(raw_data, 9)
        idat = png_chunk(b'IDAT', compressed)

        # IEND chunk
        iend = png_chunk(b'IEND', b'')

        return signature + ihdr + idat + iend

    # Create a 100x100 red PNG
    png_data = create_simple_png(100, 100, (255, 0, 0))
    base64_image = base64.b64encode(png_data).decode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "curl/8.0",
    }

    data = {
        "model": "qwen-vl-plus",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请简单描述这张图片。"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        "max_tokens": 100,
    }

    try:
        with httpx.Client(timeout=30.0, http2=False) as client:
            response = client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers=headers,
                json=data,
            )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✓ Qwen-VL-Plus Vision API 成功!")
            print(f"  回复: {content}")
            return True
        else:
            print(f"❌ Qwen-VL-Plus Vision API 错误: {response.status_code}")
            print(f"  响应: {response.text[:300]}")
            return False
    except Exception as e:
        print(f"❌ Qwen-VL-Plus Vision API 异常: {e}")
        return False


def test_qwen_text():
    """Test Qwen-Plus text API."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("⚠ DASHSCOPE_API_KEY not set")
        return None

    print(f"✓ DASHSCOPE_API_KEY found: {api_key[:10]}...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "curl/8.0",
    }

    data = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": "你好，请用一句话回复确认你可以正常工作。"}],
        "max_tokens": 100,
    }

    try:
        with httpx.Client(timeout=30.0, http2=False) as client:
            response = client.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers=headers,
                json=data,
            )

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✓ Qwen-Plus Text API 成功!")
            print(f"  回复: {content}")
            return True
        else:
            print(f"❌ Qwen-Plus Text API 错误: {response.status_code}")
            print(f"  响应: {response.text[:300]}")
            return False
    except Exception as e:
        print(f"❌ Qwen-Plus Text API 异常: {e}")
        return False


def main():
    print("=" * 60)
    print("GLM-5.1 & Qwen API 连接测试")
    print("=" * 60)

    print("\n[1] 测试 GLM-5.1 文本 API")
    print("-" * 40)
    text_ok = test_glm_text()

    print("\n[2] 测试 GLM-5.1 视觉 API")
    print("-" * 40)
    vision_ok = test_glm_vision()

    print("\n[3] 测试 Qwen-Plus 文本 API")
    print("-" * 40)
    qwen_text_ok = test_qwen_text()

    print("\n[4] 测试 Qwen-VL-Plus 视觉 API")
    print("-" * 40)
    qwen_ok = test_qwen_vision()

    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print(f"  GLM-5.1 文本: {'✓ 成功' if text_ok else '❌ 失败'}")
    print(f"  GLM-5.1 视觉: {'✓ 成功' if vision_ok else '❌ 失败'}")
    print(f"  Qwen-Plus 文本: {'✓ 成功' if qwen_text_ok else '⚠ 不可用' if qwen_text_ok is None else '❌ 失败'}")
    print(f"  Qwen-VL-Plus 视觉: {'✓ 成功' if qwen_ok else '⚠ 不可用' if qwen_ok is None else '❌ 失败'}")
    print("=" * 60)

    # Check if at least one model works for each task
    text_available = text_ok or qwen_text_ok
    vision_available = vision_ok or qwen_ok

    if text_available and vision_available:
        print("\n✓ 模型配置完成，API 连接正常!")
        print("  推荐配置:")
        if qwen_text_ok:
            print("  - 文本模型: Qwen-Plus (主)")
        if text_ok:
            print("  - 文本模型: GLM-5.1 (备)")
        if qwen_ok:
            print("  - 视觉模型: Qwen-VL-Plus (主)")
        if vision_ok:
            print("  - 视觉模型: GLM-5.1 (备)")
        return 0
    else:
        print("\n❌ API 连接存在问题，请检查 API Key 配置")
        return 1


if __name__ == "__main__":
    sys.exit(main())
