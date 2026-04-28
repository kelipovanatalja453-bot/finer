import os
import logging
from typing import List
import dashscope
from finer.schemas.segment import SegmentRecord
from finer.schemas.content import ContentRecord

class ContextSummarizer:
    """
    Provides Global and Local contextual summaries for segmented content.
    Uses LLM to maintain logic hierarchy.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set.")
        dashscope.api_key = self.api_key

    def generate_overall_summary(self, segments: List[SegmentRecord]) -> str:
        """
        Generates a high-level executive summary of the entire content.
        """
        full_text = "\n\n".join([s.text for s in segments])
        # Truncate if too long for a single summary call (e.g., 6000 chars)
        if len(full_text) > 10000:
            full_text = full_text[:5000] + "..." + full_text[-5000:]

        prompt = (
            "你是一个资深投资研究助手。请阅读以下从多模态素材中提取的碎片记录，"
            "为整篇内容写一段简洁的执行摘要（Executive Summary），包含核心观点、涉及板块和关键结论。"
            "摘要字数控制在 200 字以内。"
        )

        messages = [
            {"role": "user", "content": f"{prompt}\n\n内容原文：\n{full_text}"}
        ]

        try:
            response = dashscope.Generation.call(
                model='qwen-turbo', # Faster and cheaper for summarization
                messages=messages,
                result_format='message'
            )
            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                logging.error(f"Global Summary Error: {response.message}")
                return "无法生成摘要"
        except Exception as e:
            logging.error(f"Failed to generate global summary: {e}")
            return "摘要生成出错"

    def enrich_local_context(self, segments: List[SegmentRecord]):
        """
        Adds prev/next context summaries to each segment using a window approach.
        To save costs and avoid N calls, we summarize chunks of segments.
        """
        if not segments:
            return

        # Simple approach for Phase 1: 
        # For each segment, provide a summary of its neighbors if they exist.
        # To avoid overhead, we use a rolling window and potentially cached summaries.
        
        for i in range(len(segments)):
            # Previous Context
            if i > 0:
                prev_text = segments[i-1].text
                # If too small, look back further or just use it
                segments[i].metadata["prev_context_summary"] = self._summarize_short(prev_text, "上文")
            
            # Next Context
            if i < len(segments) - 1:
                next_text = segments[i+1].text
                segments[i].metadata["next_context_summary"] = self._summarize_short(next_text, "下文")

    def _summarize_short(self, text: str, label: str) -> str:
        """
        Very brief summary for local context hint.
        """
        if len(text) < 30:
            return text
        
        # In a real SOTA system, we might perform a batch LLM call here.
        # For this version, we'll use a truncation + keyword hint or a fast LLM call.
        # To keep it efficient, let's use a very short prompt.
        prompt = f"用10字以内概括这段{label}的核心意思："
        
        messages = [
            {"role": "user", "content": f"{prompt}\n{text[:500]}"}
        ]
        
        try:
            # We use a very low limit to save costs
            response = dashscope.Generation.call(
                model='qwen-turbo',
                messages=messages,
                max_tokens=30,
                result_format='message'
            )
            if response.status_code == 200:
                return response.output.choices[0].message.content.strip()
        except:
            pass
        return text[:30] + "..."

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Simple token estimator for Chinese/English mix.
        Approx 1.5 chars per token for Chinese.
        """
        return int(len(text) * 0.8) + text.count(' ') # Improved heuristic
