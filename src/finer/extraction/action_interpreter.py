from typing import List, Dict, Any
from finer.schemas.segment import SegmentRecord
from finer.schemas.content import ContentRecord

class ActionInterpreter:
    """
    Orchestrates the context feeding for the event extraction process.
    Aggregates global summaries, local contexts, and slang tags into a coherent prompt payload.
    """

    @staticmethod
    def prepare_segment_context(content: ContentRecord, segment: SegmentRecord) -> str:
        """
        Builds a rich context string for a specific segment.
        """
        context_parts = []
        
        # 1. Global Context
        if content.overall_summary:
            context_parts.append(f"【全文核心摘要】：\n{content.overall_summary}")
        
        # 2. Local Logic Context
        struct_ctx = []
        prev_sum = segment.metadata.get("prev_context_summary")
        if prev_sum:
            struct_ctx.append(f"前置逻辑回顾：{prev_sum}")
        
        next_sum = segment.metadata.get("next_context_summary")
        if next_sum:
            struct_ctx.append(f"后继内容预告：{next_sum}")
            
        if struct_ctx:
            context_parts.append("\n".join(struct_ctx))
            
        # 3. Slang Recognition Hints
        slang_tags = segment.metadata.get("slang_tags", [])
        if slang_tags:
            hints = []
            for tag in slang_tags:
                hints.append(f"- {tag['original_term']} => {tag['normalized_name']} ({tag.get('ticker') or '非上市/分类'})")
            context_parts.append("【关键术语/黑话提示】：\n" + "\n".join(hints))
            
        return "\n\n---\n\n".join(context_parts)

    @staticmethod
    def format_extraction_guideline() -> str:
        """
        Returns structured few-shot or specific logic guidelines.
        """
        return (
            "请遵循以下多步操作链（Action Chain）提取原则：\n"
            "1. 识别前提条件：若原文说'等回调'，第一步应是'watch'，第二步才是'long'。\n"
            "2. 拆解复合指令：若原文说'破了240就卖'，应提取为'close_long'且trigger_condition为'price < 240'。\n"
            "3. 标的标准化：请使用提示词中的标准化名称填充 Ticker 字段。"
        )
