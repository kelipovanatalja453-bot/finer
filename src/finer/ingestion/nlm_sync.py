"""NLM Sync — automatically upload archived files to NotebookLM.

Wraps `nlm source add` CLI to upload supported files (PDF, TXT, MD, DOCX)
to designated NotebookLM notebooks.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_NLM_CLI = "/usr/local/bin/nlm"

DEFAULT_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


@dataclass
class SyncResult:
    """Result of syncing a file to NotebookLM."""
    file_path: Path
    notebook_id: str
    success: bool
    source_id: str = ""
    error: str = ""


class NLMSync:
    """Uploads files to NotebookLM notebooks via the nlm CLI."""

    def __init__(self, config: dict[str, Any]):
        nlm_config = config.get("notebooklm", {})
        self.supported_extensions = set(
            nlm_config.get("supported_extensions", DEFAULT_SUPPORTED_EXTENSIONS)
        )
        self.wait_for_processing = nlm_config.get("wait_for_processing", True)
        self.nlm_cli_path = nlm_config.get("nlm_cli_path", DEFAULT_NLM_CLI)
        
        # Track synced files to avoid duplicates
        self._synced_registry: dict[str, str] = {}  # path → source_id

    def should_sync(self, file_path: Path) -> bool:
        """Check if a file should be synced to NLM."""
        if file_path.suffix.lower() not in self.supported_extensions:
            logger.debug("Skipping %s: unsupported extension", file_path.name)
            return False
        if str(file_path) in self._synced_registry:
            logger.debug("Skipping %s: already synced", file_path.name)
            return False
        return True

    def sync_file(
        self,
        file_path: Path,
        notebook_id: str,
        title: str | None = None,
    ) -> SyncResult:
        """Upload a file to a NotebookLM notebook.
        
        Args:
            file_path: Local file to upload.
            notebook_id: Target notebook ID.
            title: Optional custom title for the source.
        """
        if not file_path.exists():
            return SyncResult(
                file_path=file_path,
                notebook_id=notebook_id,
                success=False,
                error=f"File not found: {file_path}",
            )

        args = [
            self.nlm_cli_path, "source", "add", notebook_id,
            "--file", str(file_path),
        ]
        if title:
            args.extend(["--title", title])
        if self.wait_for_processing:
            args.append("--wait")

        try:
            logger.info("Uploading %s to notebook %s", file_path.name, notebook_id)
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=600,  # NLM processing can be slow
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error("NLM upload failed: %s", error_msg)
                return SyncResult(
                    file_path=file_path,
                    notebook_id=notebook_id,
                    success=False,
                    error=error_msg,
                )

            # Try to extract source_id from output
            source_id = ""
            output = result.stdout.strip()
            if "ID:" in output:
                for line in output.splitlines():
                    if "ID:" in line:
                        source_id = line.split("ID:")[-1].strip()
                        break

            self._synced_registry[str(file_path)] = source_id
            logger.info("Uploaded %s → source %s", file_path.name, source_id or "ok")
            
            return SyncResult(
                file_path=file_path,
                notebook_id=notebook_id,
                success=True,
                source_id=source_id,
            )

        except subprocess.TimeoutExpired:
            return SyncResult(
                file_path=file_path,
                notebook_id=notebook_id,
                success=False,
                error="Upload timed out (>600s)",
            )
        except Exception as e:
            return SyncResult(
                file_path=file_path,
                notebook_id=notebook_id,
                success=False,
                error=str(e),
            )
