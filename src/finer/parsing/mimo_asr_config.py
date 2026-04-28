"""MiMo ASR Configuration Helper.

This module provides utilities for configuring the MiMo-V2.5-TTS ASR service.
"""

from pathlib import Path
from typing import Optional
import os


class MiMoASRSetup:
    """Helper for MiMo ASR configuration."""

    DEFAULT_URL = "http://localhost:8001/api/asr"

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Args:
            api_url: MiMo ASR API endpoint URL
            api_key: Optional API key for authentication
        """
        self.api_url = api_url or os.getenv("MIMO_ASR_URL", self.DEFAULT_URL)
        self.api_key = api_key or os.getenv("MIMO_ASR_API_KEY")

    def get_config(self) -> dict:
        """Get MiMo ASR configuration."""
        return {
            "api_url": self.api_url,
            "api_key": self.api_key,
            "timeout": float(os.getenv("MIMO_ASR_TIMEOUT", "300")),
            "chunk_size_mb": float(os.getenv("MIMO_ASR_CHUNK_SIZE_MB", "25")),
            "language": os.getenv("MIMO_ASR_LANGUAGE", "zh"),
        }

    def to_env(self) -> dict:
        """Export configuration as environment variables."""
        env = {
            "MIMO_ASR_URL": self.api_url,
            "MIMO_ASR_TIMEOUT": "300",
            "MIMO_ASR_CHUNK_SIZE_MB": "25",
            "MIMO_ASR_LANGUAGE": "zh",
        }
        if self.api_key:
            env["MIMO_ASR_API_KEY"] = self.api_key
        return env


def configure_mimo_asr(
    api_url: str = "http://localhost:8001/api/asr",
    api_key: Optional[str] = None,
) -> MiMoASRSetup:
    """Configure MiMo ASR service.

    Args:
        api_url: MiMo ASR API endpoint
        api_key: Optional API key

    Returns:
        MiMoASRSetup instance

    Example:
        # Local deployment
        setup = configure_mimo_asr("http://localhost:8001/api/asr")

        # Remote deployment with API key
        setup = configure_mimo_asr(
            "https://api.example.com/asr",
            api_key="your-api-key"
        )
    """
    return MiMoASRSetup(api_url=api_url, api_key=api_key)


# Common configurations
LOCAL_MIMO = MiMoASRSetup("http://localhost:8001/api/asr")
"""Local MiMo ASR on port 8001."""


def check_mimo_asr_health(api_url: Optional[str] = None) -> dict:
    """Check MiMo ASR service health.

    Args:
        api_url: Optional URL override

    Returns:
        Health status dict
    """
    import httpx

    url = api_url or os.getenv("MIMO_ASR_URL", MiMoASRSetup.DEFAULT_URL)
    base_url = url.rsplit("/", 1)[0]

    try:
        response = httpx.get(f"{base_url}/health", timeout=5.0)
        return {
            "healthy": response.status_code == 200,
            "url": url,
            "status_code": response.status_code,
        }
    except Exception as e:
        return {
            "healthy": False,
            "url": url,
            "error": str(e),
        }
