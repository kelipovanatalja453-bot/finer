"""Pipeline module — Shim file.

NOTE: This file is NOT loaded by Python when ``finer.pipeline/`` package exists.
The package's ``__init__.py`` takes import precedence over this .py file.
This file is kept only as a documentation hint and should be deleted
once all references are confirmed migrated.

All functionality lives in:
- finer.pipeline._legacy       (init_storage, register_directory, etc.)
- finer.pipeline.orchestrator  (PipelineOrchestrator, PipelineResult, etc.)
"""

# When Python resolves ``finer.pipeline``, it finds the package directory
# (finer/pipeline/__init__.py) and ignores this file entirely.
# If this file were somehow loaded, it would be an error state.
raise ImportError(
    "finer.pipeline is a package, not a module. "
    "Import from finer.pipeline._legacy or finer.pipeline.orchestrator instead."
)
