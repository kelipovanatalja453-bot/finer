"""MiMo ASR Client — Audio transcription via MiMo Open Platform API.

Provides ASR (Automatic Speech Recognition) using MiMo's
OpenAI-compatible audio transcription API.

API Platform: https://platform.xiaomimimo.com/
Skill Documentation: https://github.com/XiaomiMiMo/MiMo-Skills

Supported models:
- whisper-1 (OpenAI Whisper)

Features:
- Small file: direct upload
- Large file: ffmpeg chunking + parallel transcription
- Timestamp adjustment for chunks
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MiMoASRError(Exception):
    """MiMo ASR operation error."""
    pass


class MiMoASRNotAvailableError(MiMoASRError):
    """MiMo ASR service is not available."""
    pass


class MiMoASRAuthError(MiMoASRError):
    """MiMo ASR authentication error."""
    pass


@dataclass
class ASRSegment:
    """Single ASR segment with timestamp."""

    start_time: float  # seconds
    end_time: float
    text: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "confidence": self.confidence,
        }


@dataclass
class ASRResult:
    """Complete ASR result."""

    segments: List[ASRSegment]
    full_text: str
    duration_seconds: float
    language: str
    model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "full_text": self.full_text,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "model": self.model,
        }


@dataclass
class MiMoASRConfig:
    """MiMo ASR configuration for MiMo Open Platform API."""

    api_url: str = "https://api.xiaomimimo.com/v1/audio/transcriptions"
    api_key: Optional[str] = None  # MIMO_API_KEY from MiMo platform
    model: str = "whisper-1"  # ASR model
    timeout: float = 300.0
    chunk_size_mb: float = 25.0
    language: str = "zh"


class MiMoASRClient:
    """Client for MiMo Open Platform ASR API (OpenAI-compatible format).

    API Platform: https://platform.xiaomimimo.com/

    Usage:
        client = MiMoASRClient()
        result = await client.transcribe(Path("audio.m4a"))
        print(result.full_text)
    """

    def __init__(self, config: Optional[MiMoASRConfig] = None):
        self.config = config or MiMoASRConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "MiMoASRClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def check_available(self) -> bool:
        """Check if MiMo ASR service is available."""
        try:
            client = await self._get_client()
            response = await client.get(
                self.config.api_url.rsplit("/", 1)[0] + "/health",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> ASRResult:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Language code (default from config)

        Returns:
            ASRResult with segments and full text
        """
        if not audio_path.exists():
            raise MiMoASRError(f"Audio file not found: {audio_path}")

        lang = language or self.config.language

        # Check file size
        file_size_mb = audio_path.stat().st_size / 1024 / 1024

        if file_size_mb > self.config.chunk_size_mb:
            logger.info(
                f"Large file ({file_size_mb:.1f}MB), using chunked transcription"
            )
            return await self._transcribe_large_file(audio_path, lang)
        else:
            return await self._transcribe_small_file(audio_path, lang)

    async def _transcribe_small_file(
        self,
        audio_path: Path,
        language: str,
    ) -> ASRResult:
        """Transcribe small file in single request using SiliconFlow OpenAI-compatible API."""
        client = await self._get_client()

        content_type = self._get_content_type(audio_path)

        with open(audio_path, "rb") as f:
            # SiliconFlow uses OpenAI-compatible format
            # file: audio file binary
            # model: model name
            files = {"file": (audio_path.name, f, content_type)}
            data = {"model": self.config.model}

            try:
                response = await client.post(
                    self.config.api_url,
                    files=files,
                    data=data,
                )

                if response.status_code == 401:
                    raise MiMoASRAuthError(f"Authentication failed: {response.text}")

                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise MiMoASRError(f"ASR API error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                raise MiMoASRNotAvailableError(f"ASR service not available: {e}")

        result = response.json()
        return self._parse_result(result, audio_path)

    async def _transcribe_large_file(
        self,
        audio_path: Path,
        language: str,
    ) -> ASRResult:
        """Transcribe large file by splitting into chunks."""
        # Check ffmpeg availability
        if not shutil.which("ffmpeg"):
            raise MiMoASRError("ffmpeg not found, required for large file chunking")

        # Get audio duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise MiMoASRError(f"Failed to get audio duration: {result.stderr}")

        total_duration = float(result.stdout.strip())

        # Calculate chunk duration based on file size
        file_size_mb = audio_path.stat().st_size / 1024 / 1024
        chunk_duration = int(
            (self.config.chunk_size_mb / file_size_mb) * total_duration * 0.9
        )
        chunk_duration = max(60, min(300, chunk_duration))  # 1-5 minutes

        logger.info(
            f"Splitting {total_duration:.0f}s audio into {chunk_duration}s chunks"
        )

        # Split and transcribe
        all_segments: List[ASRSegment] = []
        temp_dir = tempfile.mkdtemp(prefix="mimo_asr_")

        try:
            num_chunks = int(total_duration // chunk_duration) + 1

            for i in range(num_chunks):
                start_time = i * chunk_duration
                chunk_path = Path(temp_dir) / f"chunk_{i}{audio_path.suffix}"

                # Extract chunk
                split_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_time),
                    "-i", str(audio_path),
                    "-t", str(chunk_duration),
                    "-c:a", "copy",
                    str(chunk_path),
                ]
                subprocess.run(split_cmd, capture_output=True, check=True)

                if not chunk_path.exists() or chunk_path.stat().st_size == 0:
                    continue

                # Transcribe chunk
                try:
                    chunk_result = await self._transcribe_small_file(chunk_path, language)
                except MiMoASRError as e:
                    logger.warning(f"Chunk {i} transcription failed: {e}")
                    continue

                # Adjust timestamps
                for seg in chunk_result.segments:
                    seg.start_time += start_time
                    seg.end_time += start_time
                    all_segments.append(seg)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        full_text = " ".join(seg.text for seg in all_segments)

        return ASRResult(
            segments=all_segments,
            full_text=full_text,
            duration_seconds=total_duration,
            language=language,
            model=self.config.model,
        )

    def _get_content_type(self, path: Path) -> str:
        """Get content type from file extension."""
        content_types = {
            ".m4s": "audio/mp4",
            ".m4a": "audio/mp4",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".aac": "audio/aac",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
            ".opus": "audio/opus",
        }
        return content_types.get(path.suffix.lower(), "audio/mpeg")

    def _parse_result(self, data: dict[str, Any], audio_path: Path) -> ASRResult:
        """Parse SiliconFlow OpenAI-compatible API response.

        Response format:
        {
            "text": "transcribed text",
            "task": "transcribe",
            "language": "zh",
            "duration": 10.5,
            "segments": [...]  # optional
        }
        """
        segments = []

        # Parse segments if available
        for seg in data.get("segments", []):
            segments.append(
                ASRSegment(
                    start_time=seg.get("start", 0.0),
                    end_time=seg.get("end", 0.0),
                    text=seg.get("text", ""),
                    confidence=seg.get("confidence", 1.0),
                )
            )

        # If no segments, create one from full text
        if not segments and data.get("text"):
            segments.append(
                ASRSegment(
                    start_time=0.0,
                    end_time=data.get("duration", 0.0),
                    text=data.get("text", ""),
                    confidence=1.0,
                )
            )

        return ASRResult(
            segments=segments,
            full_text=data.get("text", ""),
            duration_seconds=data.get("duration", 0.0),
            language=data.get("language", self.config.language),
            model=self.config.model,
        )


# Convenience function
async def transcribe_audio(
    audio_path: Path,
    api_url: Optional[str] = None,
    language: str = "zh",
) -> ASRResult:
    """Transcribe audio file using MiMo ASR.

    Args:
        audio_path: Path to audio file
        api_url: MiMo ASR API URL (default from env)
        language: Language code

    Returns:
        ASRResult with segments and full text
    """
    config = MiMoASRConfig(
        api_url=api_url or "http://localhost:8001/api/asr",
        language=language,
    )
    async with MiMoASRClient(config) as client:
        return await client.transcribe(audio_path)
