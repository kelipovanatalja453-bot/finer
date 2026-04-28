"""Tests for Content Standardizer.

This module tests the content standardization functions for converting
text, markdown, and transcripts into ContentEnvelope format.
"""

import pytest
from datetime import datetime

from finer.parsing.content_standardizer import (
    standardize_text_source,
    standardize_markdown_source,
    standardize_chat_transcript,
    standardize_audio_transcript,
    standardize_image_strategy,
    _detect_block_type,
    _split_into_blocks,
    _create_default_quality_card,
)
from finer.schemas.content_envelope import ContentEnvelope, ContentBlock
from finer.schemas.quality import QualityCard


class TestBlockDetection:
    """Tests for block type detection."""

    def test_detect_heading_h1(self):
        """Test H1 heading detection."""
        text = "# 市场分析报告"
        assert _detect_block_type(text) == "heading"

    def test_detect_heading_h2(self):
        """Test H2 heading detection."""
        text = "## 策略建议"
        assert _detect_block_type(text) == "heading"

    def test_detect_heading_h6(self):
        """Test H6 heading detection."""
        text = "###### 小节标题"
        assert _detect_block_type(text) == "heading"

    def test_detect_unordered_list_dash(self):
        """Test unordered list detection with dash."""
        text = "- 看多信号"
        assert _detect_block_type(text) == "list"

    def test_detect_unordered_list_asterisk(self):
        """Test unordered list detection with asterisk."""
        text = "* 重要提示"
        assert _detect_block_type(text) == "list"

    def test_detect_unordered_list_plus(self):
        """Test unordered list detection with plus."""
        text = "+ 关注点"
        assert _detect_block_type(text) == "list"

    def test_detect_ordered_list(self):
        """Test ordered list detection."""
        text = "1. 第一步"
        assert _detect_block_type(text) == "list"

    def test_detect_ordered_list_double_digit(self):
        """Test ordered list detection with double digit."""
        text = "10. 第十步"
        assert _detect_block_type(text) == "list"

    def test_detect_paragraph(self):
        """Test paragraph detection."""
        text = "这是一段普通的文本内容。"
        assert _detect_block_type(text) == "paragraph"

    def test_detect_table(self):
        """Test table placeholder detection."""
        text = "| 股票 | 价格 |"
        assert _detect_block_type(text) == "table"

    def test_detect_chart_placeholder_chinese(self):
        """Test chart placeholder detection (Chinese)."""
        text = "如图所示 [图表] 分析"
        assert _detect_block_type(text) == "chart"

    def test_detect_chart_placeholder_english(self):
        """Test chart placeholder detection (English)."""
        text = "See [chart] below"
        assert _detect_block_type(text) == "chart"

    def test_detect_unknown_empty(self):
        """Test unknown detection for empty text."""
        assert _detect_block_type("") == "unknown"
        assert _detect_block_type("   ") == "unknown"

    # Placeholder type detection tests
    def test_detect_table_region_placeholder(self):
        """Test table_region placeholder detection."""
        assert _detect_block_type("[TABLE_REGION]") == "table_region"
        assert _detect_block_type("[表格区域]") == "table_region"
        assert _detect_block_type("内容 [TABLE_REGION] 更多内容") == "table_region"

    def test_detect_chart_region_placeholder(self):
        """Test chart_region placeholder detection."""
        assert _detect_block_type("[CHART_REGION]") == "chart_region"
        assert _detect_block_type("[图表区域]") == "chart_region"
        assert _detect_block_type("分析 [CHART_REGION] 数据") == "chart_region"

    def test_detect_image_region_placeholder(self):
        """Test image_region placeholder detection."""
        assert _detect_block_type("[IMAGE_REGION]") == "image_region"
        assert _detect_block_type("[图片区域]") == "image_region"
        assert _detect_block_type("描述 [IMAGE_REGION] 结束") == "image_region"

    def test_detect_ocr_unreadable_placeholder(self):
        """Test ocr_unreadable placeholder detection."""
        assert _detect_block_type("[OCR_UNREADABLE]") == "ocr_unreadable"
        assert _detect_block_type("[无法识别]") == "ocr_unreadable"
        assert _detect_block_type("部分内容 [无法识别] 继续") == "ocr_unreadable"

    def test_placeholder_priority_over_heading(self):
        """Test placeholder detection has priority over heading."""
        text = "# 标题 [TABLE_REGION]"
        assert _detect_block_type(text) == "table_region"


class TestPlaceholderQualityCards:
    """Tests for placeholder type quality cards."""

    def test_table_region_quality_card(self):
        """Test table_region gets appropriate quality card."""
        quality = _create_default_quality_card("table_region")
        assert quality.readability_score == 0.5
        assert quality.financial_relevance_score == 0.7

    def test_chart_region_quality_card(self):
        """Test chart_region gets appropriate quality card."""
        quality = _create_default_quality_card("chart_region")
        assert quality.readability_score == 0.4
        assert quality.financial_relevance_score == 0.8

    def test_image_region_quality_card(self):
        """Test image_region gets appropriate quality card."""
        quality = _create_default_quality_card("image_region")
        assert quality.readability_score == 0.3
        assert quality.financial_relevance_score == 0.5

    def test_ocr_unreadable_quality_card(self):
        """Test ocr_unreadable gets lowest quality card."""
        quality = _create_default_quality_card("ocr_unreadable")
        assert quality.readability_score == 0.1
        assert quality.financial_relevance_score == 0.3

    def test_placeholder_standardization(self):
        """Test placeholder text is standardized correctly."""
        text = "分析内容\n\n[TABLE_REGION]\n\n[CHART_REGION]"
        envelope = standardize_text_source(text)

        block_types = [b.block_type for b in envelope.blocks]
        assert "table_region" in block_types
        assert "chart_region" in block_types


class TestBlockSplitting:
    """Tests for text block splitting."""

    def test_split_single_paragraph(self):
        """Test splitting single paragraph."""
        text = "这是一段文本。"
        blocks = _split_into_blocks(text)
        assert len(blocks) == 1
        assert blocks[0] == "这是一段文本。"

    def test_split_multiple_paragraphs(self):
        """Test splitting multiple paragraphs."""
        text = "第一段。\n\n第二段。\n\n第三段。"
        blocks = _split_into_blocks(text)
        assert len(blocks) == 3

    def test_split_heading_and_paragraph(self):
        """Test splitting heading and paragraph."""
        text = "# 标题\n\n这是正文内容。"
        blocks = _split_into_blocks(text)
        assert len(blocks) == 2
        assert _detect_block_type(blocks[0]) == "heading"
        assert _detect_block_type(blocks[1]) == "paragraph"

    def test_split_list_items(self):
        """Test splitting list items."""
        text = "- 项目1\n- 项目2\n- 项目3"
        blocks = _split_into_blocks(text)
        assert len(blocks) == 1  # List items grouped together
        # The block contains multiple list items, detect type by first line
        first_line = blocks[0].split('\n')[0]
        assert _detect_block_type(first_line) == "list"

    def test_split_mixed_content(self):
        """Test splitting mixed content."""
        text = """# 市场分析

今日市场表现强劲。

- 看多信号
- 成交量放大

详细分析如下。"""
        blocks = _split_into_blocks(text)
        assert len(blocks) >= 3


class TestStandardizeTextSource:
    """Tests for text source standardization."""

    def test_basic_standardization(self):
        """Test basic text standardization."""
        text = "这是一段测试文本。"
        envelope = standardize_text_source(text)

        assert isinstance(envelope, ContentEnvelope)
        assert envelope.source_type == "text"
        assert len(envelope.blocks) == 1
        assert envelope.blocks[0].text == text
        assert envelope.blocks[0].order == 0

    def test_preserve_metadata(self):
        """Test that metadata is preserved."""
        text = "测试内容"
        creator_id = "user_123"
        creator_name = "分析师A"
        published_at = datetime(2024, 1, 15, 10, 30)
        source_uri = "test://uri"
        source_title = "测试标题"

        envelope = standardize_text_source(
            text=text,
            source_type="chat",
            source_uri=source_uri,
            source_title=source_title,
            creator_id=creator_id,
            creator_name=creator_name,
            published_at=published_at,
        )

        assert envelope.source_type == "chat"
        assert envelope.source_uri == source_uri
        assert envelope.source_title == source_title
        assert envelope.creator_id == creator_id
        assert envelope.creator_name == creator_name
        assert envelope.published_at == published_at

    def test_quality_card_generation(self):
        """Test that quality cards are generated."""
        text = "# 标题\n\n正文内容。"
        envelope = standardize_text_source(text)

        # Envelope should have quality card
        assert isinstance(envelope.quality_card, QualityCard)
        assert envelope.quality_card.overall_score >= 0
        assert envelope.quality_card.overall_score <= 1

        # Each block should have quality card
        for block in envelope.blocks:
            assert isinstance(block.quality_card, QualityCard)
            assert block.quality_card.overall_score >= 0
            assert block.quality_card.overall_score <= 1

    def test_evidence_span_generation(self):
        """Test that evidence spans are generated."""
        text = "测试文本内容"
        envelope = standardize_text_source(text)

        assert len(envelope.blocks) == 1
        block = envelope.blocks[0]

        # Should have at least one evidence span
        assert len(block.evidence_spans) >= 1

        # Evidence span should cover the text
        span = block.evidence_spans[0]
        assert span.block_id == block.block_id
        assert span.text == text
        assert span.char_start == 0
        assert span.char_end == len(text)

    def test_block_order_sequential(self):
        """Test that block orders are sequential."""
        text = "第一段。\n\n第二段。\n\n第三段。"
        envelope = standardize_text_source(text)

        orders = [block.order for block in envelope.blocks]
        assert orders == list(range(len(envelope.blocks)))

    def test_different_block_types(self):
        """Test that different block types are detected."""
        text = """# 标题

- 列表项1
- 列表项2

普通段落。"""
        envelope = standardize_text_source(text)

        block_types = [block.block_type for block in envelope.blocks]
        assert "heading" in block_types
        assert "list" in block_types
        assert "paragraph" in block_types


class TestStandardizeMarkdownSource:
    """Tests for markdown source standardization."""

    def test_basic_markdown(self):
        """Test basic markdown standardization."""
        markdown = """# 市场分析报告

## 策略建议

- 看多
- 看空

详细分析内容。"""
        envelope = standardize_markdown_source(markdown)

        assert isinstance(envelope, ContentEnvelope)
        assert len(envelope.blocks) >= 3

        # Check heading detection
        heading_blocks = [b for b in envelope.blocks if b.block_type == "heading"]
        assert len(heading_blocks) >= 1

    def test_markdown_with_table(self):
        """Test markdown with table."""
        markdown = """| 股票 | 价格 |
|------|------|
| AAPL | 150 |
"""
        envelope = standardize_markdown_source(markdown)

        # Should detect table structure
        table_blocks = [b for b in envelope.blocks if b.block_type == "table"]
        assert len(table_blocks) >= 1


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_standardize_chat_transcript(self):
        """Test chat transcript standardization."""
        transcript = "用户A: 你好\n用户B: 你好"
        envelope = standardize_chat_transcript(
            transcript,
            creator_id="chat_123",
            creator_name="聊天室",
        )

        assert envelope.source_type == "chat"
        assert envelope.creator_id == "chat_123"
        assert envelope.creator_name == "聊天室"

    def test_standardize_audio_transcript(self):
        """Test audio transcript standardization."""
        transcript = "这是音频转录的文本内容。"
        envelope = standardize_audio_transcript(
            transcript,
            creator_id="audio_456",
            creator_name="播客",
        )

        assert envelope.source_type == "audio_transcript"
        assert envelope.creator_id == "audio_456"

    def test_standardize_image_strategy(self):
        """Test image strategy standardization."""
        text_content = "图片中的策略分析内容"
        envelope = standardize_image_strategy(
            text_content,
            creator_id="image_789",
            creator_name="分析师B",
            source_uri="image://chart.png",
        )

        assert envelope.source_type == "image"
        assert envelope.source_uri == "image://chart.png"


class TestEnvelopeValidation:
    """Tests for ContentEnvelope validation."""

    def test_envelope_serialization(self):
        """Test envelope can be serialized to dict."""
        text = "测试内容"
        envelope = standardize_text_source(text)

        data = envelope.to_dict()
        assert isinstance(data, dict)
        assert "envelope_id" in data
        assert "blocks" in data

    def test_envelope_get_text_content(self):
        """Test get_text_content method."""
        text = "第一段。\n\n第二段。"
        envelope = standardize_text_source(text)

        full_text = envelope.get_text_content()
        assert "第一段" in full_text
        assert "第二段" in full_text

    def test_envelope_get_blocks_by_type(self):
        """Test get_blocks_by_type method."""
        text = "# 标题\n\n段落内容。"
        envelope = standardize_text_source(text)

        headings = envelope.get_blocks_by_type("heading")
        assert len(headings) >= 1

        paragraphs = envelope.get_blocks_by_type("paragraph")
        assert len(paragraphs) >= 1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_text(self):
        """Test empty text handling."""
        text = ""
        envelope = standardize_text_source(text)

        # Should create envelope with no blocks
        assert len(envelope.blocks) == 0

    def test_whitespace_only(self):
        """Test whitespace-only text handling."""
        text = "   \n\n   \n   "
        envelope = standardize_text_source(text)

        # Should create envelope with no blocks
        assert len(envelope.blocks) == 0

    def test_very_long_text(self):
        """Test handling of very long text."""
        text = "测试内容。" * 1000
        envelope = standardize_text_source(text)

        # Should handle long text
        assert len(envelope.blocks) >= 1
        assert len(envelope.blocks[0].text) > 0

    def test_unicode_content(self):
        """Test Unicode content handling."""
        text = "中文内容\n\n日本語コンテンツ\n\n한국어 내용"
        envelope = standardize_text_source(text)

        # Should handle Unicode properly
        assert len(envelope.blocks) >= 1
        assert "中文" in envelope.get_text_content()

    def test_special_characters(self):
        """Test special character handling."""
        text = "特殊字符: @#$%^&*()\n\n表情符号: 😀🎉"
        envelope = standardize_text_source(text)

        # Should handle special characters
        assert len(envelope.blocks) >= 1


class TestBlockStructure:
    """Tests for block structure preservation."""

    def test_nested_list_not_supported(self):
        """Test that nested lists are flattened (V0 limitation)."""
        # V0 doesn't support nested structures
        text = "- 项目1\n  - 子项目1.1"
        envelope = standardize_text_source(text)

        # Should still create blocks
        assert len(envelope.blocks) >= 1

    def test_code_block_as_paragraph(self):
        """Test code block is treated as paragraph."""
        text = "```python\nprint('hello')\n```"
        envelope = standardize_text_source(text)

        # Code blocks are treated as paragraphs in V0
        assert len(envelope.blocks) >= 1
