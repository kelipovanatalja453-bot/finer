"""Pipeline package — Declarative pipeline orchestration.

Provides both the legacy synchronous API (init_storage, register_directory,
run_perception_pipeline, dry_run_pipeline) and the new PipelineOrchestrator
for end-to-end async pipeline processing.

Legacy usage (backward compatible):
    from finer.pipeline import init_storage, register_directory

New usage:
    from finer.pipeline import PipelineOrchestrator, PipelineResult
"""

# Re-export legacy functions from the original module
# (now living in finer.pipeline._legacy)
from finer.pipeline._legacy import (
    init_storage,
    register_directory,
    run_perception_pipeline,
    dry_run_pipeline,
)

# Re-export new orchestrator API
from finer.pipeline.orchestrator import (
    PipelineOrchestrator,
    PipelineResult,
    BacktestPipelineResult,
    DateRange,
    StageResult,
    StageCompletionTracker,
)

__all__ = [
    # Legacy
    "init_storage",
    "register_directory",
    "run_perception_pipeline",
    "dry_run_pipeline",
    # New
    "PipelineOrchestrator",
    "PipelineResult",
    "BacktestPipelineResult",
    "DateRange",
    "StageResult",
    "StageCompletionTracker",
]
