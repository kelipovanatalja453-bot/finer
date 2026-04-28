"""Feishu Poller — pull new messages and download attachments via lark-cli.

This module wraps `lark-cli im` commands to:
1. List new messages from watched chats since a given timestamp
2. Download file/image attachments to the local inbox
3. Maintain sync state to avoid duplicate processing
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LARK_CLI = "/opt/homebrew/bin/lark-cli"


@dataclass
class FeishuMessage:
    """Represents a single Feishu message with attachment metadata."""
    message_id: str
    chat_id: str
    msg_type: str          # text | file | image | post | ...
    sender_id: str
    create_time: datetime
    content_raw: str       # raw content string from API
    file_keys: list[str] = field(default_factory=list)
    content_text: str = ""  # extracted text portion if any


@dataclass
class DownloadedFile:
    """A file that has been downloaded from Feishu to local inbox."""
    local_path: Path
    original_name: str
    message_id: str
    chat_id: str
    sender_id: str
    sent_at: datetime
    msg_type: str          # image | file
    context_text: str      # any text context from the message or nearby messages


def _run_lark_cli(lark_cli: str, args: list[str], timeout: int = 60) -> dict[str, Any]:
    """Execute a lark-cli command and return parsed JSON output."""
    cmd = [lark_cli] + args
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        logger.error("lark-cli error: %s", result.stderr)
        raise RuntimeError(f"lark-cli failed: {result.stderr}")
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # Some commands return non-JSON (like file downloads)
        return {"raw_output": result.stdout, "ok": True}


def _parse_create_time(time_str: str) -> datetime:
    """Parse lark-cli's create_time format (e.g. '2026-04-12 20:31')."""
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"]:
        try:
            dt = datetime.strptime(time_str, fmt)
            if dt.tzinfo is None:
                # Feishu timestamps in lark-cli output are usually local
                import time
                local_tz = datetime.now().astimezone().tzinfo
                dt = dt.replace(tzinfo=local_tz)
            return dt
        except ValueError:
            continue
    # Fallback: try Unix timestamp
    try:
        return datetime.fromtimestamp(float(time_str), tz=timezone.utc)
    except (ValueError, OSError):
        logger.warning("Cannot parse time '%s', using now", time_str)
        return datetime.now(tz=timezone.utc)


def _extract_file_keys(content_raw: str, msg_type: str) -> list[str]:
    """Extract file_key or image_key from message content string."""
    keys = []
    if msg_type == "image":
        # Format: [Image: img_v3_xxx]
        import re
        for match in re.finditer(r"img_v\d+_[a-zA-Z0-9_-]+", content_raw):
            keys.append(match.group())
    elif msg_type == "file":
        # Try to parse as JSON to get file_key
        try:
            content_json = json.loads(content_raw)
            if "file_key" in content_json:
                keys.append(content_json["file_key"])
        except (json.JSONDecodeError, TypeError):
            import re
            for match in re.finditer(r"file_[a-zA-Z0-9_-]+", content_raw):
                keys.append(match.group())
    return keys


class FeishuPoller:
    """Polls Feishu chats for new messages and downloads attachments."""

    def __init__(self, inbox_dir: Path, lark_cli_path: str = DEFAULT_LARK_CLI):
        self.inbox_dir = inbox_dir
        self.lark_cli_path = lark_cli_path
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def poll_chat(
        self,
        chat_id: str,
        since: datetime | None = None,
        page_size: int = 50,
        max_pages: int = 100,
    ) -> list[FeishuMessage]:
        """Pull messages from a chat, optionally filtered by time.

        Handles pagination to fetch all messages, not just the first page.
        """
        all_messages = []
        page_token = None
        pages_fetched = 0

        while pages_fetched < max_pages:
            args = [
                "im", "+chat-messages-list",
                "--chat-id", chat_id,
                "--page-size", str(page_size),
                "--sort", "asc",
                "--format", "json",
            ]
            if since:
                # Subtract 60 seconds to avoid 'end_time is earlier than the start_time' errors
                # due to slight clock mismatches between local and server.
                since_adjusted = since - timedelta(seconds=60)
                # Ensure we convert to UTC before formatting as Z
                iso_start = since_adjusted.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                args.extend(["--start", iso_start])
            if page_token:
                args.extend(["--page-token", page_token])

            response = _run_lark_cli(self.lark_cli_path, args)
            messages_data = response.get("data", {}).get("messages", [])

            for msg in messages_data:
                if msg.get("deleted"):
                    continue

                msg_type = msg.get("msg_type", "text")
                content_raw = msg.get("content", "")
                create_time = _parse_create_time(msg.get("create_time", ""))
                sender = msg.get("sender", {})

                # Extract text content for text and post types
                content_text = ""
                if msg_type == "text":
                    content_text = content_raw
                elif msg_type == "post":
                    # Post messages have content in content_raw directly
                    content_text = content_raw

                feishu_msg = FeishuMessage(
                    message_id=msg["message_id"],
                    chat_id=chat_id,
                    msg_type=msg_type,
                    sender_id=sender.get("id", "unknown"),
                    create_time=create_time,
                    content_raw=content_raw,
                    file_keys=_extract_file_keys(content_raw, msg_type),
                    content_text=content_text,
                )
                all_messages.append(feishu_msg)

            pages_fetched += 1

            # Check for more pages
            has_more = response.get("data", {}).get("has_more", False)
            if not has_more:
                break
            page_token = response.get("data", {}).get("page_token")
            if not page_token:
                break

        logger.info(
            "Polled %d messages from chat %s (since=%s, pages=%d)",
            len(all_messages), chat_id, since, pages_fetched,
        )
        return all_messages

    def download_attachment(
        self,
        message: FeishuMessage,
        file_key: str,
    ) -> DownloadedFile | None:
        """Download a single attachment from a message."""
        # Determine resource type
        if message.msg_type == "image":
            resource_type = "image"
            ext = ".png"
        else:
            resource_type = "file"
            ext = ""

        # Build output filename
        time_prefix = message.create_time.strftime("%Y%m%d_%H%M")
        safe_key = file_key.replace("/", "_")
        output_name = f"{time_prefix}_{safe_key}{ext}"
        output_path = self.inbox_dir / output_name

        try:
            # lark-cli requires relative paths for output
            try:
                rel_output = output_path.relative_to(Path.cwd())
            except ValueError:
                # Fallback if path is not under CWD
                rel_output = output_path.name

            args = [
                "im", "+messages-resources-download",
                "--message-id", message.message_id,
                "--file-key", file_key,
                "--type", resource_type,
                "--output", str(rel_output),
            ]
            _run_lark_cli(self.lark_cli_path, args, timeout=120)
            
            if output_path.exists():
                logger.info("Downloaded: %s → %s", file_key, output_path)
                return DownloadedFile(
                    local_path=output_path,
                    original_name=output_name,
                    message_id=message.message_id,
                    chat_id=message.chat_id,
                    sender_id=message.sender_id,
                    sent_at=message.create_time,
                    msg_type=message.msg_type,
                    context_text=message.content_text,
                )
            else:
                logger.warning("Download produced no file: %s", file_key)
                return None
        except Exception as e:
            logger.error("Failed to download %s: %s", file_key, e)
            return None

    def download_all_attachments(
        self,
        messages: list[FeishuMessage],
    ) -> list[DownloadedFile]:
        """Download all attachments from a list of messages.
        
        For messages without explicit file_keys (like images), the
        file_key is extracted from the content field.
        """
        downloads = []
        
        # Build a text-context lookup from nearby text messages
        text_context: dict[str, str] = {}
        for i, msg in enumerate(messages):
            if msg.msg_type == "text":
                # Associate text with adjacent non-text messages
                for j in range(max(0, i - 2), min(len(messages), i + 3)):
                    if messages[j].msg_type != "text":
                        text_context[messages[j].message_id] = msg.content_text

        for msg in messages:
            if msg.msg_type not in ("file", "image"):
                continue
            
            # Add text context from nearby messages
            if not msg.content_text and msg.message_id in text_context:
                msg.content_text = text_context[msg.message_id]
            
            for file_key in msg.file_keys:
                downloaded = self.download_attachment(msg, file_key)
                if downloaded:
                    # Carry over text context
                    if msg.message_id in text_context:
                        downloaded.context_text = text_context[msg.message_id]
                    downloads.append(downloaded)

        return downloads


class SyncState:
    """Persists the last-synced timestamp per chat to avoid re-processing."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._state: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            self._state = json.loads(self.state_file.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_last_sync(self, chat_id: str) -> datetime | None:
        ts = self._state.get(chat_id)
        if ts:
            return datetime.fromisoformat(ts)
        return None

    def update_last_sync(self, chat_id: str, timestamp: datetime) -> None:
        self._state[chat_id] = timestamp.isoformat()
        self.save()
