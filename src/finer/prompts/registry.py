"""PromptRegistry — Jinja2-based prompt template management.

Loads prompt templates from a directory structure like:
    prompts/
      f3_intent_extraction/
        system.j2
        user.j2
      f5_trade_action/
        system.j2
        user.j2

Templates use Jinja2 syntax with optional YAML frontmatter for metadata
(name, stage, version, model_hint).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Default prompts directory: src/finer/prompts/ relative to this file
_DEFAULT_PROMPTS_DIR = Path(__file__).parent


class PromptRegistry:
    """Jinja2-based prompt template registry.

    Usage:
        registry = PromptRegistry()
        rendered = registry.render(
            "f3_intent_extraction/user",
            content_text="...",
            creator_name="...",
        )
    """

    def __init__(self, prompts_dir: Optional[str | Path] = None):
        self._prompts_dir = Path(prompts_dir) if prompts_dir else _DEFAULT_PROMPTS_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self._prompts_dir)),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def prompts_dir(self) -> Path:
        return self._prompts_dir

    def _resolve_path(self, template_name: str) -> str:
        """Resolve template name to filesystem path."""
        if not template_name.endswith(".j2"):
            template_name = f"{template_name}.j2"
        if "/" not in template_name:
            template_name = template_name.replace(".", "/")
        return template_name

    def _read_raw(self, template_name: str) -> str:
        """Read raw template source, stripping YAML frontmatter if present."""
        template_path = self._resolve_path(template_name)
        source_path = self._prompts_dir / template_path
        if not source_path.exists():
            raise TemplateNotFound(template_name, message=f"Template '{template_name}' not found")
        raw = source_path.read_text(encoding="utf-8")
        # Strip YAML frontmatter for rendering (metadata is extracted separately)
        m = _FRONTMATTER_RE.match(raw)
        if m:
            return raw[m.end():]
        return raw

    def load_metadata(self, template_name: str) -> Dict[str, Any]:
        """Extract YAML frontmatter metadata from a template.

        Args:
            template_name: Template path (e.g. "f3_intent_extraction/user").

        Returns:
            Dict of metadata fields. Empty dict if no frontmatter.
        """
        template_path = self._resolve_path(template_name)
        source_path = self._prompts_dir / template_path
        if not source_path.exists():
            raise TemplateNotFound(template_name, message=f"Template '{template_name}' not found")
        raw = source_path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(raw)
        if not m:
            return {}
        try:
            import yaml
            return yaml.safe_load(m.group(1)) or {}
        except Exception:
            # Parse frontmatter manually as key: value pairs
            meta = {}
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            return meta

    def render(self, template_name: str, **kwargs: Any) -> str:
        """Render a prompt template with the given variables.

        Strips YAML frontmatter before rendering.

        Args:
            template_name: Dot-separated template path (e.g. "f3_intent_extraction/user").
                           Automatically appends .j2 extension if missing.
            **kwargs: Template variables.

        Returns:
            Rendered prompt string.

        Raises:
            jinja2.TemplateNotFound: If the template does not exist.
        """
        template_path = self._resolve_path(template_name)
        source = self._read_raw(template_name)
        template = self._env.from_string(source)
        return template.render(**kwargs)

    def list_templates(self) -> list[str]:
        """List all available prompt templates (relative paths without .j2)."""
        templates = []
        for p in self._prompts_dir.rglob("*.j2"):
            rel = p.relative_to(self._prompts_dir)
            templates.append(str(rel.with_suffix("")))
        return sorted(templates)

    def has_template(self, template_name: str) -> bool:
        """Check if a template exists."""
        if not template_name.endswith(".j2"):
            template_name = f"{template_name}.j2"
        template_path = template_name.replace(".", "/") if "/" not in template_name else template_name
        return (self._prompts_dir / template_path).exists()
