"""Summary Generator — LLM-powered file summary with caching and timestamp extraction.

Generates summaries for ingested files using GLM-5.1/Qwen text models.
Caches results based on file hash + prompt hash to avoid redundant API calls.
Extracts timestamps from multiple sources with priority ranking.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from finer.llm import LLMClient
from finer.model_config import get_text_registry

logger = logging.getLogger(__name__)

# Import performance tracking
try:
    from finer.services.performance import track_performance
    _PERF_TRACK_AVAILABLE = True
except ImportError:
    _PERF_TRACK_AVAILABLE = False
    # Fallback: identity decorator
    def track_performance(op):
        def decorator(f):
            return f
        return decorator

# Financial content summary prompt
FINANCIAL_SUMMARY_PROMPT = """你是一个金融研究助手。请分析以下内容并生成结构化摘要。

请按以下格式输出：

## 核心观点
（一句话概括主要内容，不超过50字）

## 关键标的
（涉及的股票、基金、行业等，用逗号分隔）

## 方向判断
（看多/看空/中性，或具体观点）

## 时间线索
（内容中提到的具体时间点，如会议、数据发布、事件等）

## 要点列表
- 要点1
- 要点2
- 要点3

---

内容：
{content}
"""

# Generic summary prompt for non-financial content
GENERIC_SUMMARY_PROMPT = """请为以下内容生成简明摘要：

1. 用一句话概括核心内容（不超过50字）
2. 列出3-5个关键要点
3. 标注内容中提到的时间信息

---

内容：
{content}
"""


@dataclass
class SummaryCache:
    """Cache for summary results to avoid redundant LLM calls."""
    cache_dir: Path
    index_file: Path
    index: dict[str, dict[str, Any]]  # cache_key -> cache_entry

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = cache_dir / "index.json"
        self.index = self._load_index()

    def _load_index(self) -> dict:
        """Load cache index from disk."""
        if self.index_file.exists():
            try:
                return json.loads(self.index_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load cache index: {e}")
                return {}
        return {}

    def _save_index(self):
        """Persist cache index to disk."""
        self.index_file.write_text(
            json.dumps(self.index, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file for cache key."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _compute_cache_key(self, file_path: Path, prompt: str) -> str:
        """Generate cache key from file hash + prompt hash."""
        file_hash = self._compute_file_hash(file_path)
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return f"{file_hash}_{prompt_hash}"

    def get(self, file_path: Path, prompt: str) -> Optional[dict[str, Any]]:
        """Get cached summary if available."""
        cache_key = self._compute_cache_key(file_path, prompt)

        if cache_key in self.index:
            entry = self.index[cache_key]
            cache_file = self.cache_dir / entry["cache_file"]
            if cache_file.exists():
                logger.debug(f"Cache hit for {file_path.name}")
                try:
                    cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                    return cached_data
                except (json.JSONDecodeError, OSError):
                    return None
        return None

    def set(
        self,
        file_path: Path,
        prompt: str,
        summary: str,
        extracted_timestamp: Optional[str],
        model: str,
    ) -> str:
        """Cache the summary result."""
        cache_key = self._compute_cache_key(file_path, prompt)

        # Generate cache filename
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        cache_filename = f"{cache_key[:16]}_{timestamp_str}.json"
        cache_file = self.cache_dir / cache_filename

        # Prepare cache data
        cache_data = {
            "summary": summary,
            "extracted_timestamp": extracted_timestamp,
            "original_file": str(file_path),
            "model": model,
            "cached_at": datetime.now().isoformat(),
        }

        # Write cache file
        cache_file.write_text(
            json.dumps(cache_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Update index
        self.index[cache_key] = {
            "cache_file": cache_filename,
            "original_file": str(file_path),
            "model": model,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_index()

        logger.info(f"Cached summary for {file_path.name}")
        return str(cache_file)


# Global cache instance
import threading

_summary_cache: Optional[SummaryCache] = None
_cache_lock = threading.Lock()


def get_summary_cache(root: Optional[Path] = None) -> Optional[SummaryCache]:
    """Get or create the global summary cache."""
    global _summary_cache
    if _summary_cache is None and root:
        with _cache_lock:
            if _summary_cache is None:  # double-check locking
                _summary_cache = SummaryCache(root / "data" / "cache" / "summaries")
    return _summary_cache


def init_summary_cache(root: Path) -> SummaryCache:
    """Initialize the summary cache."""
    global _summary_cache
    with _cache_lock:
        _summary_cache = SummaryCache(root / "data" / "cache" / "summaries")
    return _summary_cache


def reset_summary_cache():
    """Reset the global cache for testing."""
    global _summary_cache
    with _cache_lock:
        _summary_cache = None


class TimestampExtractor:
    """Extract timestamps from multiple sources with priority ranking.

    Priority: content_time > filename_time > file_metadata
    """

    # Filename patterns for timestamp extraction
    FILENAME_PATTERNS = [
        # 20260423_1430_xxx.png
        (r"(\d{8})_(\d{4})", "%Y%m%d_%H%M"),
        # 20260423_xxx.png
        (r"(\d{8})", "%Y%m%d"),
        # 2026-04-23_xxx.png
        (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
        # 202604231430_xxx.png
        (r"(\d{12})", "%Y%m%d%H%M"),
    ]

    # Content time patterns
    CONTENT_PATTERNS = [
        # 2026年4月23日
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "ymd_chinese"),
        # 2026-04-23 14:30
        (r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", "%Y-%m-%d %H:%M"),
        # 2026/04/23
        (r"(\d{4}/\d{2}/\d{2})", "%Y/%m/%d"),
        # 4月23日
        (r"(\d{1,2})月(\d{1,2})日", "md_chinese"),
        # 昨天、今天、前天
        (r"(昨天|今天|前天)", "relative_chinese"),
    ]

    @classmethod
    def extract_from_filename(cls, filename: str) -> Optional[datetime]:
        """Extract timestamp from filename using known patterns."""
        for pattern, fmt in cls.FILENAME_PATTERNS:
            match = re.search(pattern, filename)
            if match:
                try:
                    time_str = match.group(1)
                    if fmt == "%Y%m%d_%H%M":
                        time_str = f"{match.group(1)}_{match.group(2)}"
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue
        return None

    @classmethod
    def extract_from_content(cls, content: str) -> Optional[datetime]:
        """Extract timestamp from content text.

        Returns the earliest absolute timestamp found, or relative timestamp.
        """
        now = datetime.now()
        timestamps: list[tuple[datetime, int]] = []  # (timestamp, priority)

        for pattern, fmt in cls.CONTENT_PATTERNS:
            matches = re.findall(pattern, content)
            for match in matches:
                try:
                    if fmt == "ymd_chinese":
                        # (2026, 4, 23)
                        ts = datetime(int(match[0]), int(match[1]), int(match[2]))
                        timestamps.append((ts, 0))
                    elif fmt == "md_chinese":
                        # (4, 23) - use current year
                        ts = datetime(now.year, int(match[0]), int(match[1]))
                        # If date is in future, assume last year
                        if ts > now:
                            ts = datetime(now.year - 1, int(match[0]), int(match[1]))
                        timestamps.append((ts, 1))
                    elif fmt == "relative_chinese":
                        if match == "今天":
                            timestamps.append((now.replace(hour=0, minute=0, second=0), 2))
                        elif match == "昨天":
                            yesterday = now - timedelta(days=1)
                            timestamps.append((yesterday.replace(hour=0, minute=0, second=0), 2))
                        elif match == "前天":
                            before_yesterday = now - timedelta(days=2)
                            timestamps.append((before_yesterday.replace(hour=0, minute=0, second=0), 2))
                    else:
                        ts = datetime.strptime(match, fmt)
                        timestamps.append((ts, 0))
                except (ValueError, IndexError):
                    continue

        # Return earliest absolute timestamp (priority 0), then earliest relative
        if not timestamps:
            return None

        # Sort by priority first, then by timestamp
        timestamps.sort(key=lambda x: (x[1], x[0]))
        return timestamps[0][0]

    @classmethod
    def extract_from_exif(cls, image_path: Path) -> Optional[datetime]:
        """Extract timestamp from image EXIF data."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(image_path) as img:
                exif_data = img._getexif()
                if not exif_data:
                    return None

                # Look for DateTimeOriginal tag (0x9003)
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag in ("DateTimeOriginal", "DateTime"):
                        # Format: "2026:04:23 14:30:00"
                        try:
                            return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            continue
        except ImportError:
            logger.debug("PIL not available for EXIF extraction")
        except Exception as e:
            logger.debug(f"EXIF extraction failed: {e}")

        return None

    @classmethod
    def extract_from_file_metadata(cls, file_path: Path) -> Optional[datetime]:
        """Extract timestamp from file system metadata (creation/modification time)."""
        try:
            stat = file_path.stat()
            # Use modification time as it's more reliable
            return datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            return None

    @classmethod
    def extract_timestamp(
        cls,
        file_path: Path,
        content: Optional[str] = None,
        is_image: bool = False,
    ) -> Optional[datetime]:
        """Extract timestamp with priority: content > filename > exif > metadata.

        Returns:
            Extracted datetime or None if no timestamp found.
        """
        # Priority 1: Content time
        if content:
            content_time = cls.extract_from_content(content)
            if content_time:
                logger.debug(f"Extracted timestamp from content: {content_time}")
                return content_time

        # Priority 2: Filename time
        filename_time = cls.extract_from_filename(file_path.name)
        if filename_time:
            logger.debug(f"Extracted timestamp from filename: {filename_time}")
            return filename_time

        # Priority 3: EXIF time (images only)
        if is_image:
            exif_time = cls.extract_from_exif(file_path)
            if exif_time:
                logger.debug(f"Extracted timestamp from EXIF: {exif_time}")
                return exif_time

        # Priority 4: File metadata
        metadata_time = cls.extract_from_file_metadata(file_path)
        if metadata_time:
            logger.debug(f"Extracted timestamp from file metadata: {metadata_time}")
            return metadata_time

        return None


class SummaryGenerator:
    """Generates file summaries using LLM with caching and timestamp extraction."""

    def __init__(
        self,
        root: Optional[Path] = None,
        model: str = "qwen-plus",
        use_cache: bool = True,
        financial_mode: bool = True,
    ):
        self.registry = get_text_registry()
        self.model = model
        self.use_cache = use_cache
        self.financial_mode = financial_mode

        # Initialize cache
        self.cache = None
        if use_cache and root:
            self.cache = init_summary_cache(root)
        elif use_cache and _summary_cache:
            self.cache = _summary_cache

        # Initialize LLM client
        self._llm_client: Optional[LLMClient] = None

    def _get_llm_client(self) -> Optional[LLMClient]:
        """Get or create LLM client from registry."""
        if self._llm_client:
            return self._llm_client

        model_config = self.registry.get_available_model()
        if not model_config:
            logger.error("No available text models")
            return None

        api_key = os.getenv(model_config.api_key_env)
        if not api_key:
            logger.error(f"No API key for {model_config.name}")
            return None

        self._llm_client = LLMClient(
            api_key=api_key,
            base_url=model_config.base_url,
            model=model_config.name,
            max_tokens=model_config.max_tokens,
        )
        return self._llm_client

    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content for summary generation.

        Supports:
        - Text files (.txt, .md, .json, .csv, etc.)
        - Vision transcripts (.md with _vision suffix)
        """
        suffix = file_path.suffix.lower()

        # Text-based files
        if suffix in (".txt", ".md", ".json", ".csv", ".yaml", ".yml", ".log", ".xml"):
            # Try multiple encodings for Chinese files
            encodings = ["utf-8", "gbk", "gb2312", "utf-16", "latin-1"]
            for encoding in encodings:
                try:
                    content = file_path.read_text(encoding=encoding)
                    # Limit content length to avoid token limits
                    max_chars = 8000
                    if len(content) > max_chars:
                        return content[:max_chars] + "\n... (内容已截断)"
                    return content
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Failed to read {file_path}: {e}")
                    return None
            logger.warning(f"Could not decode {file_path} with any encoding")
            return None

        # Binary files - check for transcript
        transcript_path = file_path.parent / f"{file_path.stem}_vision.md"
        if transcript_path.exists():
            return transcript_path.read_text(encoding="utf-8")

        logger.warning(f"Cannot read content from {file_path} (unsupported format)")
        return None

    @track_performance("summary_generate")
    def generate_summary(
        self,
        file_path: Path,
        content: Optional[str] = None,
        is_image: bool = False,
        custom_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate summary for a file with caching and timestamp extraction.

        Args:
            file_path: Path to the file to summarize
            content: Pre-extracted content (optional, will read from file if not provided)
            is_image: Whether the file is an image
            custom_prompt: Custom prompt template (optional)

        Returns:
            dict with keys: summary, extracted_timestamp, cached, model
        """
        # Read content if not provided
        if content is None:
            content = self._read_file_content(file_path)

        if not content:
            return {
                "summary": None,
                "extracted_timestamp": None,
                "cached": False,
                "model": None,
                "error": "No content available for summarization",
            }

        # Select prompt
        prompt_template = custom_prompt or (
            FINANCIAL_SUMMARY_PROMPT if self.financial_mode else GENERIC_SUMMARY_PROMPT
        )
        prompt = prompt_template.format(content=content)

        # Check cache
        if self.use_cache and self.cache:
            cached = self.cache.get(file_path, prompt)
            if cached:
                return {
                    "summary": cached.get("summary"),
                    "extracted_timestamp": cached.get("extracted_timestamp"),
                    "cached": True,
                    "model": cached.get("model"),
                }

        # Generate summary via LLM
        client = self._get_llm_client()
        if not client:
            return {
                "summary": None,
                "extracted_timestamp": None,
                "cached": False,
                "model": None,
                "error": "No LLM client available",
            }

        logger.info(f"Generating summary for {file_path.name} using {client.model}")
        summary = client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        if not summary:
            return {
                "summary": None,
                "extracted_timestamp": None,
                "cached": False,
                "model": client.model,
                "error": "LLM call failed",
            }

        # Extract timestamp
        extracted_dt = TimestampExtractor.extract_timestamp(
            file_path, content, is_image
        )
        extracted_timestamp = extracted_dt.isoformat() if extracted_dt else None

        # Cache the result
        if self.use_cache and self.cache:
            self.cache.set(
                file_path, prompt, summary, extracted_timestamp, client.model
            )

        return {
            "summary": summary,
            "extracted_timestamp": extracted_timestamp,
            "cached": False,
            "model": client.model,
        }

    def summarize_text(
        self,
        text: str,
        title: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate summary for raw text content.

        Args:
            text: Text content to summarize
            title: Optional title/context
            custom_prompt: Custom prompt template

        Returns:
            dict with summary and extracted_timestamp
        """
        content = f"标题: {title}\n\n{text}" if title else text

        # Extract timestamp from content
        extracted_dt = TimestampExtractor.extract_from_content(content)
        extracted_timestamp = extracted_dt.isoformat() if extracted_dt else None

        # Select prompt
        prompt_template = custom_prompt or (
            FINANCIAL_SUMMARY_PROMPT if self.financial_mode else GENERIC_SUMMARY_PROMPT
        )
        prompt = prompt_template.format(content=content)

        # Generate summary
        client = self._get_llm_client()
        if not client:
            return {
                "summary": None,
                "extracted_timestamp": extracted_timestamp,
                "error": "No LLM client available",
            }

        logger.info(f"Summarizing text using {client.model}")
        summary = client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        return {
            "summary": summary,
            "extracted_timestamp": extracted_timestamp,
            "model": client.model,
        }


# Convenience function
def generate_file_summary(
    file_path: Path,
    root: Optional[Path] = None,
    **kwargs,
) -> dict[str, Any]:
    """Generate summary for a file.

    Convenience function that creates a SummaryGenerator and calls generate_summary.
    """
    generator = SummaryGenerator(root=root)
    return generator.generate_summary(file_path, **kwargs)
