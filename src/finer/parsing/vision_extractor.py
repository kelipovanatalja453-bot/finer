import os
import logging
from pathlib import Path
from http import HTTPStatus
import dashscope
from finer.schemas.content import ContentRecord
from finer.schemas.segment import SegmentRecord

class VisionExtractor:
    """
    Extracts text and layout structure from Images using Qwen-VL API.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set.")
        dashscope.api_key = self.api_key

    def extract_image(self, content_record: ContentRecord) -> list[SegmentRecord]:
        """
        Calls Qwen-VL-Max to extract text from a single image and parse it into manageable segments.
        """
        source_path = Path(content_record.source_path)
        if not source_path.exists():
            logging.error(f"Image not found: {source_path}")
            return []

        prompt = (
            "你是一个专业的金融文档解析助手。请精准提取这张图片中的所有文字信息，"
            "并严格按照原图的视觉排版结构，将其转化为逻辑连贯的Markdown格式返回。"
            "遇到图表，请尽可能提取表头结构和主要数据。"
            "注意：只需返回Markdown本身，不要附加额外问候语。"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"image": f"file://{source_path.absolute()}"},
                    {"text": prompt}
                ]
            }
        ]

        logging.info(f"Sending {source_path.name} to Qwen-VL-Max...")
        response = dashscope.MultiModalConversation.call(
            model='qwen-vl-max',
            messages=messages
        )

        if response.status_code == HTTPStatus.OK:
            text_result = response.output.choices[0].message.content[0]['text']
            
            # Better chunking: track Markdown headers for structural context
            lines = text_result.split("\n")
            segments = []
            current_heading = "未分类"
            current_block = []
            block_idx = 0

            def flush_block(text_lines, heading, idx):
                full_text = "\n".join(text_lines).strip()
                if not full_text:
                    return None
                return SegmentRecord(
                    segment_id=f"{content_record.content_id}-imgblock-{idx}",
                    content_id=content_record.content_id,
                    block_index=idx,
                    text=full_text,
                    source_modality="image_ocr",
                    metadata={"parent_heading": heading}
                )

            for line in lines:
                if line.strip().startswith("#"):
                    # Before changing heading, flush current block
                    if current_block:
                        seg = flush_block(current_block, current_heading, block_idx)
                        if seg:
                            segments.append(seg)
                            block_idx += 1
                        current_block = []
                    current_heading = line.strip().replace("#", "").strip()
                elif not line.strip():
                    if current_block:
                        seg = flush_block(current_block, current_heading, block_idx)
                        if seg:
                            segments.append(seg)
                            block_idx += 1
                        current_block = []
                else:
                    current_block.append(line)
            
            # Final flush
            if current_block:
                seg = flush_block(current_block, current_heading, block_idx)
                if seg:
                    segments.append(seg)

            return segments
        else:
            logging.error(f"DashScope Qwen-VL Error: {response.code} - {response.message}")
            return []
