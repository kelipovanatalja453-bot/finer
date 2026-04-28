"""Version Management Service.

Provides version tracking and configuration hashing for reproducibility.

Key Features:
    - Compute config hashes for version tracking
    - Detect when re-processing is needed
    - Manage prompt and model versions
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional

from finer.schemas.lineage import VersionInfo


# =============================================================================
# Current Version Constants
# =============================================================================

CURRENT_SCHEMA_VERSION = "1.0"
CURRENT_PROMPT_VERSION = "2.0"  # Updated for multi-step action chain


# =============================================================================
# Config Hashing
# =============================================================================

def compute_config_hash(
    prompt_template: str,
    model_name: str,
    temperature: float,
    **kwargs: Any,
) -> str:
    """Compute a hash of extraction configuration.

    This hash enables detecting when configuration changes require re-processing.

    Args:
        prompt_template: The prompt template used
        model_name: Model identifier
        temperature: Temperature setting
        **kwargs: Additional configuration parameters

    Returns:
        16-character hex hash string

    Example:
        hash1 = compute_config_hash("Extract trades...", "glm-5.1", 0.3)
        hash2 = compute_config_hash("Extract trades...", "glm-5.1", 0.5)
        assert hash1 != hash2  # Different temperature
    """
    config = {
        # Truncate prompt to avoid excessively long hashes
        "prompt": prompt_template[:500] if prompt_template else "",
        "model": model_name,
        "temperature": temperature,
    }

    # Add additional params
    for key, value in sorted(kwargs.items()):
        if value is not None:
            # Convert non-serializable types to string
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                value = str(value)
            config[key] = value

    # Sort keys for deterministic hashing
    config_str = json.dumps(config, sort_keys=True, ensure_ascii=False)

    # SHA-256 truncated to 16 chars (64 bits)
    return hashlib.sha256(config_str.encode('utf-8')).hexdigest()[:16]


def compute_prompt_hash(prompt_template: str) -> str:
    """Compute hash of prompt template only.

    Args:
        prompt_template: The prompt template

    Returns:
        16-character hex hash string
    """
    if not prompt_template:
        return ""
    return hashlib.sha256(prompt_template.encode('utf-8')).hexdigest()[:16]


# =============================================================================
# Version Manager
# =============================================================================

class VersionManager:
    """Manages version information for extraction pipeline.

    Responsibilities:
        - Create version info for new extractions
        - Detect when re-processing is needed
        - Track prompt and model versions

    Example:
        manager = VersionManager()
        version = manager.create_version_info(
            model_name="glm-5.1",
            prompt_template="...",
            temperature=0.3,
        )
    """

    def __init__(
        self,
        schema_version: str = CURRENT_SCHEMA_VERSION,
        prompt_version: str = CURRENT_PROMPT_VERSION,
    ):
        """Initialize version manager.

        Args:
            schema_version: Current schema version
            prompt_version: Current prompt version
        """
        self.schema_version = schema_version
        self.prompt_version = prompt_version

    def create_version_info(
        self,
        model_name: str,
        prompt_template: str,
        temperature: float = 0.7,
        model_provider: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> VersionInfo:
        """Create version information for an extraction.

        Args:
            model_name: Model identifier
            prompt_template: Prompt template used
            temperature: Temperature setting
            model_provider: Model provider (optional)
            additional_params: Additional extraction parameters

        Returns:
            VersionInfo instance
        """
        config_hash = compute_config_hash(
            prompt_template=prompt_template,
            model_name=model_name,
            temperature=temperature,
            **(additional_params or {}),
        )

        prompt_hash = compute_prompt_hash(prompt_template)

        return VersionInfo(
            schema_version=self.schema_version,
            extraction_config_hash=config_hash,
            model_version=model_name,
            model_provider=model_provider,
            prompt_version=self.prompt_version,
            prompt_hash=prompt_hash,
            temperature=temperature,
            additional_params=additional_params or {},
        )

    def should_reprocess(
        self,
        existing: VersionInfo,
        current_prompt_version: Optional[str] = None,
        current_config_hash: Optional[str] = None,
    ) -> bool:
        """Determine if data needs re-processing.

        Re-processing is needed when:
            - Prompt version changed
            - Config hash changed (different model/temperature/prompt)
            - Schema version is incompatible

        Args:
            existing: Existing version info from stored data
            current_prompt_version: Current prompt version (uses manager's if None)
            current_config_hash: Current config hash (computed if None)

        Returns:
            True if re-processing is needed
        """
        if current_prompt_version is None:
            current_prompt_version = self.prompt_version

        # Prompt version changed
        if existing.prompt_version and existing.prompt_version != current_prompt_version:
            return True

        # Config hash changed (if both available)
        if current_config_hash and existing.extraction_config_hash:
            if current_config_hash != existing.extraction_config_hash:
                return True

        # Schema version incompatible (major version mismatch)
        if existing.schema_version:
            try:
                existing_major = int(existing.schema_version.split('.')[0])
                current_major = int(self.schema_version.split('.')[0])
                if existing_major != current_major:
                    return True
            except (ValueError, AttributeError):
                pass

        return False

    def needs_enrichment_update(
        self,
        existing: VersionInfo,
        enrichment_stale_hours: int = 24,
    ) -> bool:
        """Check if enrichment data needs updating.

        Args:
            existing: Existing version info
            enrichment_stale_hours: Hours before enrichment is considered stale

        Returns:
            True if enrichment should be updated
        """
        if not existing.created_at:
            return True

        age_hours = (datetime.now() - existing.created_at).total_seconds() / 3600
        return age_hours > enrichment_stale_hours


# =============================================================================
# Global Instance
# =============================================================================

_default_manager: Optional[VersionManager] = None


def get_version_manager() -> VersionManager:
    """Get the default version manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = VersionManager()
    return _default_manager


def set_version_manager(manager: VersionManager) -> None:
    """Set the default version manager instance."""
    global _default_manager
    _default_manager = manager
