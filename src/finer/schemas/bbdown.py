"""BBDown API Schemas — Request/Response models for BBDown integration.

BBDown is a C# .NET CLI tool for Bilibili video/audio/subtitle download.
This module defines schemas for interacting with BBDown's JSON API server mode.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class VideoQuality(str, Enum):
    """Bilibili video quality options."""

    Q4K = "120"  # 4K 超高清
    Q1080P60 = "116"  # 1080P 60fps
    Q1080P_PLUS = "74"  # 1080P+ 高码率
    Q1080P = "80"  # 1080P 高清
    Q720P60 = "74"  # 720P 60fps
    Q720P = "64"  # 720P 高清
    Q480P = "32"  # 480P 清晰
    Q360P = "16"  # 360P 流畅


class AudioQuality(str, Enum):
    """Bilibili audio quality options."""

    HI_RES = "30251"  # Hi-Res 无损
    DOLBY = "30250"  # Dolby 杜比全景声
    FLAC = "30280"  # FLAC 无损
    HIGH = "30232"  # 132kbps 高品质
    MEDIUM = "30216"  # 64kbps 中品质


class SubtitleFormat(str, Enum):
    """Subtitle format options."""

    SRT = "srt"
    JSON = "json"
    ASS = "ass"


class DownloadTaskStatus(str, Enum):
    """BBDown task status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BBDownVideoInfo(BaseModel):
    """Video information from BBDown."""

    model_config = ConfigDict(strict=True)

    bvid: str = Field(..., description="B站 BV ID")
    aid: int = Field(..., description="AV ID")
    title: str = Field(..., description="视频标题")
    uploader: str = Field(..., description="上传者名称")
    uploader_id: int = Field(..., description="上传者 mid")
    publish_time: datetime = Field(..., description="发布时间")
    duration: int = Field(..., description="时长（秒）")
    description: str = Field(default="", description="视频简介")
    cover_url: str = Field(default="", description="封面图片 URL")
    page_count: int = Field(default=1, description="分P数量")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    has_subtitle: bool = Field(default=False, description="是否有 CC 字幕")


class BBDownSubtitle(BaseModel):
    """Subtitle data from BBDown."""

    model_config = ConfigDict(strict=True)

    language: str = Field(..., description="字幕语言 (zh-CN, en-US)")
    format: SubtitleFormat = Field(default=SubtitleFormat.JSON, description="字幕格式")
    content: str = Field(..., description="字幕内容")
    segments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="解析后的字幕片段（带时间戳）",
    )


class BBDownDownloadRequest(BaseModel):
    """Request for BBDown download task."""

    model_config = ConfigDict(strict=True)

    bvid_or_url: str = Field(..., description="BV ID 或 B站 URL")
    quality: VideoQuality = Field(default=VideoQuality.Q1080P, description="视频画质")
    audio_quality: AudioQuality = Field(default=AudioQuality.FLAC, description="音频品质")
    download_video: bool = Field(default=False, description="是否下载视频文件")
    download_audio: bool = Field(default=True, description="是否下载音频文件")
    download_subtitle: bool = Field(default=True, description="是否下载 CC 字幕")
    subtitle_format: SubtitleFormat = Field(default=SubtitleFormat.JSON, description="字幕格式")
    page_index: Optional[int] = Field(None, description="分P视频页码")
    cookie: Optional[str] = Field(None, description="B站 cookie（会员内容）")
    output_dir: Optional[str] = Field(None, description="输出目录")


class BBDownTaskResponse(BaseModel):
    """BBDown task response."""

    model_config = ConfigDict(strict=True)

    task_id: str = Field(..., description="任务 ID")
    bvid: str = Field(..., description="BV ID")
    status: DownloadTaskStatus = Field(..., description="任务状态")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="下载进度")
    video_path: Optional[str] = Field(None, description="视频文件路径")
    audio_path: Optional[str] = Field(None, description="音频文件路径")
    subtitle: Optional[BBDownSubtitle] = Field(None, description="字幕数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class BBDownConfigResponse(BaseModel):
    """BBDown service configuration."""

    model_config = ConfigDict(strict=True)

    service_url: str = Field(..., description="BBDown API 服务地址")
    is_running: bool = Field(..., description="服务是否运行")
    version: Optional[str] = Field(None, description="BBDown 版本")
    supported_qualities: List[VideoQuality] = Field(default_factory=list)
    supported_audio_qualities: List[AudioQuality] = Field(default_factory=list)


class BBDownTranscribeRequest(BaseModel):
    """Request for video transcription."""

    model_config = ConfigDict(strict=True)

    bvid_or_url: str = Field(..., description="BV ID 或 B站 URL")
    prefer_subtitle: bool = Field(default=True, description="优先使用 CC 字幕")
    fallback_to_asr: bool = Field(default=True, description="无字幕时使用 ASR")
    language: str = Field(default="zh", description="语言")


class BBDownTranscribeResult(BaseModel):
    """Video transcription result."""

    model_config = ConfigDict(strict=True)

    bvid: str = Field(..., description="BV ID")
    title: str = Field(..., description="视频标题")
    source: str = Field(..., description="转录来源 (cc_subtitle, mimo_asr)")
    segments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="转录片段（带时间戳）",
    )
    full_text: str = Field(default="", description="完整文本")
    duration_seconds: float = Field(default=0.0, description="视频时长")
    language: str = Field(default="zh", description="语言")