import os
import logging
from typing import List, Optional
import instructor
from openai import OpenAI
from finer.schemas.event import ExtractionResult, EventWithActions

class ActionExtractor:
    """
    Core engine to extract structured investment events from text using Instructor + Qwen.
    """
    
    DEFAULT_MODEL = "qwen-max"
    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY must be set.")
            
        self.model = model or self.DEFAULT_MODEL
        
        # Initialize the Instructor-patched OpenAI client
        # DashScope's compatible mode works perfectly with Instructor
        self.client = instructor.from_openai(
            OpenAI(
                api_key=self.api_key,
                base_url=self.DASHSCOPE_BASE_URL
            ),
            mode=instructor.Mode.TOOLS # TOOLS mode is generally more reliable for Qwen
        )

    def extract_events(self, text: str, context: Optional[str] = None) -> List[EventWithActions]:
        """
        Extracts structured events from the provided text, optionally using additional context.
        """
        system_prompt = (
            "你是一个专业的金融分析助理。请从文本中提取结构化的投资事件（Events）。\n"
            "每个事件必须包含：标的(ticker)、方向(direction)、证据原文(evidence_text)及操作意图链(action_chain)。\n\n"
            "【方向枚举限制】：仅限使用 'bullish' (看多), 'bearish' (看空), 'neutral' (中性), 'watchlist' (观察), 'risk_warning' (风险提示)。\n"
            "【操作链逻辑】：将复合描述进行拆解。例如：'等回调买入' -> [watch, long]。\n\n"
            "【示例 JSON 格式要求】：\n"
            "{\n"
            "  \"events\": [\n"
            "    {\n"
            "      \"ticker\": \"腾讯\",\n"
            "      \"direction\": \"bullish\",\n"
            "      \"evidence_text\": \"腾讯日线级别支撑位480，破了就止损\",\n"
            "      \"action_chain\": [\n"
            "        {\"action_type\": \"long\", \"trigger_condition\": \"at 480\", \"sequence_order\": 1},\n"
            "        {\"action_type\": \"close_long\", \"trigger_condition\": \"price < 480\", \"sequence_order\": 2}\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        )
        
        user_content = f"待分析文本：\n{text}"
        if context:
            user_content = f"背景信息：\n{context}\n\n" + user_content
            
        try:
            logging.info(f"Calling {self.model} via Instructor for extraction...")
            result = self.client.chat.completions.create(
                model=self.model,
                response_model=ExtractionResult,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
            )
            return result.events
        except Exception as e:
            logging.error(f"Failed to extract events: {e}")
            return []
