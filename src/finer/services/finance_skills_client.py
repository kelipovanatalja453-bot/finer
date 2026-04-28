"""Finance Skills Client — Unified client for finance-skills service.

Supports all finance-skills with caching, batch parallel calls,
error handling and graceful degradation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Dict, List

import httpx

logger = logging.getLogger(__name__)


class SkillName(Enum):
    """Available finance-skills."""
    YFINANCE_DATA = "yfinance-data"
    FUNDA_DATA = "funda-data"
    SENTIMENT_ANALYSIS = "sentiment-analysis"
    NEWS_AGGREGATOR = "news-aggregator"
    OPTIONS_FLOW = "options-flow"


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    data: Dict[str, Any]
    timestamp: float
    ttl: int  # seconds

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


@dataclass
class CacheConfig:
    """Cache configuration for different skill types."""
    # Market data (quotes, prices) - short TTL
    market_ttl: int = 60
    # Fundamentals (PE, market cap) - medium TTL
    fundamentals_ttl: int = 300
    # Sentiment/News - medium TTL
    sentiment_ttl: int = 300
    # Options flow - short TTL
    options_ttl: int = 60

    def get_ttl(self, skill: SkillName) -> int:
        """Get TTL for a specific skill."""
        if skill == SkillName.YFINANCE_DATA:
            return self.market_ttl
        elif skill == SkillName.FUNDA_DATA:
            return self.fundamentals_ttl
        elif skill == SkillName.SENTIMENT_ANALYSIS:
            return self.sentiment_ttl
        elif skill == SkillName.OPTIONS_FLOW:
            return self.options_ttl
        else:
            return self.fundamentals_ttl  # default


@dataclass
class FinanceSkillsConfig:
    """Configuration for Finance Skills client."""
    base_url: str = "https://finance-skills.himself65.com"
    api_key_env: str = "FINANCE_SKILLS_API_KEY"
    timeout: float = 30.0
    max_retries: int = 3
    enabled: bool = True
    cache: CacheConfig = field(default_factory=CacheConfig)


class FinanceSkillsClient:
    """Unified client for finance-skills service with caching and fallback.

    Example usage:
        client = FinanceSkillsClient()
        data = await client.call(SkillName.YFINANCE_DATA, ticker="AAPL")
    """

    def __init__(self, config: Optional[FinanceSkillsConfig] = None):
        self.config = config or FinanceSkillsConfig()
        self._cache: Dict[str, CacheEntry] = {}
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment."""
        return os.getenv(self.config.api_key_env)

    def _get_cache_key(self, skill: SkillName, **params) -> str:
        """Generate cache key from skill and parameters."""
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{skill.value}:{param_str}"

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if not expired."""
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            return entry.data
        return None

    def _set_cache(self, key: str, data: Dict[str, Any], ttl: int):
        """Set cache with TTL."""
        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=ttl
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout,
                http2=False,
            )
        return self._http_client

    async def call(
        self,
        skill: SkillName,
        **params
    ) -> Optional[Dict[str, Any]]:
        """Call a finance skill with caching.

        Args:
            skill: The skill to call
            **params: Parameters for the skill (e.g., ticker="AAPL")

        Returns:
            Skill response data or None on failure
        """
        if not self.config.enabled:
            logger.debug(f"Finance skills disabled, skipping {skill.value}")
            return None

        api_key = self._get_api_key()
        if not api_key:
            logger.warning(f"No API key found for finance-skills ({self.config.api_key_env})")
            return None

        # Check cache
        cache_key = self._get_cache_key(skill, **params)
        cached = self._get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit for {skill.value}")
            return cached

        # Make API call
        url = f"{self.config.base_url}/skills/{skill.value}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = await self._get_client()

        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(url, headers=headers, json=params)

                if response.status_code == 200:
                    data = response.json()
                    # Cache the result
                    ttl = self.config.cache.get_ttl(skill)
                    self._set_cache(cache_key, data, ttl)
                    logger.debug(f"Successfully called {skill.value}")
                    return data

                elif response.status_code == 401:
                    logger.error("Invalid API key for finance-skills")
                    return None

                elif response.status_code == 429:
                    # Rate limited, wait and retry
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                else:
                    logger.error(f"Finance skills error: {response.status_code} - {response.text[:200]}")
                    return None

            except httpx.TimeoutException:
                logger.warning(f"Timeout calling {skill.value}, attempt {attempt + 1}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(1)
                    continue

            except Exception as e:
                logger.error(f"Error calling {skill.value}: {e}")
                return None

        return None

    async def call_batch(
        self,
        calls: List[tuple[SkillName, Dict[str, Any]]]
    ) -> List[Optional[Dict[str, Any]]]:
        """Call multiple skills in parallel.

        Args:
            calls: List of (skill, params) tuples

        Returns:
            List of results in same order as input
        """
        tasks = [self.call(skill, **params) for skill, params in calls]
        return await asyncio.gather(*tasks)

    async def get_market_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get market data for a ticker (yfinance-data skill)."""
        return await self.call(SkillName.YFINANCE_DATA, ticker=ticker)

    async def get_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get fundamentals for a ticker (funda-data skill)."""
        return await self.call(SkillName.FUNDA_DATA, ticker=ticker)

    async def get_sentiment(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get sentiment analysis for a ticker."""
        return await self.call(SkillName.SENTIMENT_ANALYSIS, ticker=ticker)

    async def get_options_flow(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get options flow data for a ticker."""
        return await self.call(SkillName.OPTIONS_FLOW, ticker=ticker)

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        logger.debug("Cache cleared")

    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> FinanceSkillsClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Global client instance
_client: Optional[FinanceSkillsClient] = None


def get_finance_skills_client() -> FinanceSkillsClient:
    """Get or create the global finance skills client."""
    global _client
    if _client is None:
        _client = FinanceSkillsClient()
    return _client
