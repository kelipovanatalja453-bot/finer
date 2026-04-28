"""FunASR Client — Local audio transcription using FunASR (阿里达摩院).

Provides local ASR (Automatic Speech Recognition) using FunASR models,
optimized for M2 Mac (Apple Silicon) with Metal/MPS support.

Features:
- Runs locally on M2 Mac (no API needed)
- Supports Chinese, English, and dialects
- Real-time streaming mode available
- No CUDA required (uses CPU/MPS)

Model options:
- paraformer-zh-streaming: Lightweight streaming model (~220MB)
- paraformer-zh: Standard model (~840MB)
"""

from __future__ import annotations

import logging
import os
import tempfile
import wave
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class FunASRError(Exception):
    """FunASR operation error."""
    pass


class FunASRNotAvailableError(FunASRError):
    """FunASR is not available."""
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
class FunASRConfig:
    """FunASR configuration for local inference."""

    model: str = "paraformer-zh-streaming"  # Lightweight model for M2 Mac
    model_revision: str = "v2.0.4"
    language: str = "zh"
    device: str = "cpu"  # Use CPU for M2 Mac (MPS support limited)
    disable_pbar: bool = True
    disable_log: bool = True


class FunASRClient:
    """Client for FunASR local inference.

    Runs entirely on M2 Mac without requiring API calls.

    Usage:
        client = FunASRClient()
        result = await client.transcribe(Path("audio.m4a"))
        print(result.full_text)
    """

    def __init__(self, config: Optional[FunASRConfig] = None):
        self.config = config or FunASRConfig()
        self._model = None

    def _ensure_model(self):
        """Ensure the FunASR model is loaded."""
        if self._model is None:
            try:
                from funasr import AutoModel
                self._model = AutoModel(
                    model=self.config.model,
                    model_revision=self.config.model_revision,
                    disable_pbar=self.config.disable_pbar,
                    disable_log=self.config.disable_log,
                    disable_update=True,
                )
                logger.info(f"FunASR model loaded: {self.config.model}")
            except ImportError:
                raise FunASRNotAvailableError(
                    "FunASR not installed. Run: pip install funasr"
                )
            except Exception as e:
                raise FunASRError(f"Failed to load FunASR model: {e}")
        return self._model

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> ASRResult:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (wav, mp3, m4a, etc.)
            language: Language code (zh, en, auto)

        Returns:
            ASRResult with transcription
        """
        model = self._ensure_model()

        # Convert audio to wav if needed
        wav_path = await self._convert_to_wav(audio_path)

        try:
            # Run transcription
            result = model.generate(input=str(wav_path))

            if not result:
                return ASRResult(
                    segments=[],
                    full_text="",
                    duration_seconds=0.0,
                    language=language or self.config.language,
                    model=self.config.model,
                )

            # Parse result
            text = result[0].get("text", "") if result else ""

            # Get audio duration
            duration = self._get_audio_duration(wav_path)

            return ASRResult(
                segments=[
                    ASRSegment(
                        start_time=0.0,
                        end_time=duration,
                        text=text,
                        confidence=1.0,
                    )
                ],
                full_text=text,
                duration_seconds=duration,
                language=language or self.config.language,
                model=self.config.model,
            )

        finally:
            # Clean up temp file if created
            if wav_path != audio_path and wav_path.exists():
                wav_path.unlink()

    async def _convert_to_wav(self, audio_path: Path) -> Path:
        """Convert audio to WAV format if needed."""
        if audio_path.suffix.lower() == ".wav":
            return audio_path

        # Use ffmpeg to convert
        import subprocess
        import shutil

        if not shutil.which("ffmpeg"):
            raise FunASRError("ffmpeg not found, required for audio conversion")

        temp_dir = tempfile.mkdtemp(prefix="funasr_")
        wav_path = Path(temp_dir) / f"{audio_path.stem}.wav"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-ar", "16000",  # 16kHz sample rate
            "-ac", "1",      # Mono
            "-f", "wav",
            str(wav_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise FunASRError(f"Audio conversion failed: {result.stderr}")

        return wav_path

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        try:
            with wave.open(str(audio_path), "r") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                return frames / float(rate)
        except Exception:
            return 0.0

    def is_available(self) -> bool:
        """Check if FunASR is available."""
        try:
            from funasr import AutoModel
            return True
        except ImportError:
            return False


# Convenience function
async def transcribe_audio(
    audio_path: Path,
    model: str = "paraformer-zh-streaming",
) -> ASRResult:
    """Transcribe audio using FunASR.

    Args:
        audio_path: Path to audio file
        model: FunASR model name

    Returns:
        ASRResult with transcription
    """
    config = FunASRConfig(model=model)
    client = FunASRClient(config)
    return await client.transcribe(audio_path)