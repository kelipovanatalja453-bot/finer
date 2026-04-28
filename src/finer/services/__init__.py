"""Services module for Finer — lazy imports to avoid loading all submodules at startup."""

# Lazy import mapping: attribute name → (module, symbol)
_LAZY_IMPORTS = {
    # Finance Skills
    "FinanceSkillsClient": ("finer.services.finance_skills_client", "FinanceSkillsClient"),
    "FinanceSkillsConfig": ("finer.services.finance_skills_client", "FinanceSkillsConfig"),
    "SkillName": ("finer.services.finance_skills_client", "SkillName"),
    "CacheConfig": ("finer.services.finance_skills_client", "CacheConfig"),
    "get_finance_skills_client": ("finer.services.finance_skills_client", "get_finance_skills_client"),
    # Summary Generator
    "SummaryGenerator": ("finer.services.summary_generator", "SummaryGenerator"),
    "SummaryCache": ("finer.services.summary_generator", "SummaryCache"),
    "TimestampExtractor": ("finer.services.summary_generator", "TimestampExtractor"),
    "get_summary_cache": ("finer.services.summary_generator", "get_summary_cache"),
    "init_summary_cache": ("finer.services.summary_generator", "init_summary_cache"),
    "generate_file_summary": ("finer.services.summary_generator", "generate_file_summary"),
    # KOL Rating Engine
    "KOLRatingEngine": ("finer.services.kol_rating_engine", "KOLRatingEngine"),
    "KOLRatingResult": ("finer.services.kol_rating_engine", "KOLRatingResult"),
    "DimensionScores": ("finer.services.kol_rating_engine", "DimensionScores"),
    "StarRating": ("finer.services.kol_rating_engine", "StarRating"),
    "MedalType": ("finer.services.kol_rating_engine", "MedalType"),
    "DirectionType": ("finer.services.kol_rating_engine", "DirectionType"),
    "ViewValidation": ("finer.services.kol_rating_engine", "ViewValidation"),
    "get_kol_rating_engine": ("finer.services.kol_rating_engine", "get_kol_rating_engine"),
    "calculate_kol_rating": ("finer.services.kol_rating_engine", "calculate_kol_rating"),
    "get_top_kols": ("finer.services.kol_rating_engine", "get_top_kols"),
    # Storage & Repository
    "DateRange": ("finer.services.storage", "DateRange"),
    "TradeActionDB": ("finer.services.storage", "TradeActionDB"),
    "TradeActionRepository": ("finer.services.repository", "TradeActionRepository"),
    "KOLTimeline": ("finer.services.repository", "KOLTimeline"),
    "get_repository": ("finer.services.repository", "get_repository"),
    # Performance Monitoring
    "PerformanceBudget": ("finer.services.performance", "PerformanceBudget"),
    "PerformanceMonitor": ("finer.services.performance", "PerformanceMonitor"),
    "PerformanceTracker": ("finer.services.performance", "PerformanceTracker"),
    "track_performance": ("finer.services.performance", "track_performance"),
    "monitor": ("finer.services.performance", "monitor"),
    "PERFORMANCE_BUDGETS": ("finer.services.performance", "PERFORMANCE_BUDGETS"),
    # Version Management
    "VersionManager": ("finer.services.versioning", "VersionManager"),
    "compute_config_hash": ("finer.services.versioning", "compute_config_hash"),
    "compute_prompt_hash": ("finer.services.versioning", "compute_prompt_hash"),
    "get_version_manager": ("finer.services.versioning", "get_version_manager"),
    # Lineage Tracking
    "LineageTracker": ("finer.services.lineage", "LineageTracker"),
    "get_lineage_tracker": ("finer.services.lineage", "get_lineage_tracker"),
    "create_lineage_for_content": ("finer.services.lineage", "create_lineage_for_content"),
    "trace_trade_action_source": ("finer.services.lineage", "trace_trade_action_source"),
    # Quality Gate
    "QualityGateDecision": ("finer.services.quality_gate", "QualityGateDecision"),
    "QualityGatePolicy": ("finer.services.quality_gate", "QualityGatePolicy"),
    "evaluate_quality_card": ("finer.services.quality_gate", "evaluate_quality_card"),
    "evaluate_envelope_quality": ("finer.services.quality_gate", "evaluate_envelope_quality"),
    "get_default_policy": ("finer.services.quality_gate", "get_default_policy"),
    "create_strict_policy": ("finer.services.quality_gate", "create_strict_policy"),
    "create_lenient_policy": ("finer.services.quality_gate", "create_lenient_policy"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, symbol = _LAZY_IMPORTS[name]
        import importlib
        module = importlib.import_module(module_path)
        value = getattr(module, symbol)
        # Cache for subsequent access
        globals()[name] = value
        return value
    raise AttributeError(f"module 'finer.services' has no attribute {name!r}")
