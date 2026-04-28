"""
猫大人飞书文档 V0 Pipeline 测试

验证 content_standardizer 能从真实 Markdown fixture 生成 ContentEnvelope，
并与 expected_v0 golden case 进行结构级对比。
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from finer.parsing.content_standardizer import standardize_markdown_source
from finer.schemas.content_envelope import ContentEnvelope


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kol"


class TestCatLordV0Pipeline:
    """测试猫大人飞书文档 V0 生成链路"""

    @pytest.fixture
    def markdown_content(self):
        """加载 Markdown fixture"""
        md_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.md"
        return md_path.read_text(encoding="utf-8")

    @pytest.fixture
    def expected_v0(self):
        """加载 expected V0 golden case"""
        v0_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.expected_v0.json"
        with open(v0_path, encoding="utf-8") as f:
            return json.load(f)

    def test_standardizer_generates_envelope(self, markdown_content):
        """验证 standardize_markdown_source 能生成 ContentEnvelope"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            source_title="猫大人投资策略分析 — 2026年3月12日",
            creator_id="cat_lord_fire",
            creator_name="猫大人FIRE",
            published_at=datetime(2026, 3, 12, 15, 36),
        )

        assert isinstance(envelope, ContentEnvelope)
        assert envelope.source_type == "chat"
        assert envelope.creator_name == "猫大人FIRE"
        assert envelope.published_at is not None

    def test_standardizer_block_count(self, markdown_content):
        """验证生成的 block 数量在合理范围"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
        )

        # 至少 5 个 blocks（5 个分析段落）
        assert len(envelope.blocks) >= 5, \
            f"Expected at least 5 blocks, got {len(envelope.blocks)}"

        # 不超过 50 个 blocks（避免过度拆分）
        assert len(envelope.blocks) <= 50, \
            f"Too many blocks: {len(envelope.blocks)}"

    def test_standardizer_block_types(self, markdown_content):
        """验证生成的 block type 分布"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
        )

        block_types = {b.block_type for b in envelope.blocks}

        # 必须包含 paragraph 或 heading
        assert "paragraph" in block_types or "heading" in block_types, \
            f"Missing paragraph/heading, got: {block_types}"

        # 可能包含 list
        # (Markdown 有编号列表，但 standardizer 可能将其识别为 paragraph)

    def test_standardizer_block_order_continuous(self, markdown_content):
        """验证 block order 连续"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
        )

        orders = [b.order for b in envelope.blocks]
        expected_orders = list(range(len(envelope.blocks)))

        assert sorted(orders) == expected_orders, \
            f"Block orders not continuous: {orders}"

    def test_standardizer_each_block_has_quality_card(self, markdown_content):
        """验证每个 block 有 quality_card"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
        )

        for block in envelope.blocks:
            assert block.quality_card is not None, \
                f"Block {block.block_id} missing quality_card"
            assert block.quality_card.overall_score >= 0.0, \
                f"Block {block.block_id} has invalid overall_score"

    def test_standardizer_each_block_has_evidence_span(self, markdown_content):
        """验证每个 block 有 evidence_span"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
        )

        for block in envelope.blocks:
            # standardizer 默认为每个 block 创建一个 evidence_span
            assert len(block.evidence_spans) >= 1, \
                f"Block {block.block_id} missing evidence_span"

    def test_standardizer_matches_expected_creator_name(self, markdown_content, expected_v0):
        """验证生成的 creator_name 与 expected 一致"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
            published_at=datetime(2026, 3, 12, 15, 36),
        )

        assert envelope.creator_name == expected_v0["creator_name"]

    def test_standardizer_matches_expected_source_type(self, markdown_content, expected_v0):
        """验证生成的 source_type 与 expected 一致"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
        )

        assert envelope.source_type == expected_v0["source_type"]

    def test_standardizer_matches_expected_block_count_range(self, markdown_content, expected_v0):
        """验证生成的 block 数量与 expected 在同一范围

        注意: expected_v0 是手工精简的 golden case（8 blocks），而 standardizer
        按段落拆分会产生更多 blocks。这里验证 standardizer 能正确拆分内容，
        不要求与 expected 完全一致。
        """
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
        )

        expected_block_count = len(expected_v0["blocks"])

        # expected_v0 是精简版（8 blocks），standardizer 会产生更多
        # 验证 standardizer 至少产生 expected 数量的 blocks
        assert len(envelope.blocks) >= expected_block_count, \
            f"Generated fewer blocks than expected: {len(envelope.blocks)} < {expected_block_count}"

        # 验证 standardizer 不会过度拆分（不超过 50）
        assert len(envelope.blocks) <= 50, \
            f"Too many blocks generated: {len(envelope.blocks)}"

    def test_standardizer_investment_blocks_have_evidence(self, markdown_content):
        """验证投资相关 block 有 evidence span"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
            creator_name="猫大人FIRE",
        )

        # 检查包含投资关键词的 block
        investment_keywords = ["目标价", "看好", "风险", "机会", "盈利"]

        for block in envelope.blocks:
            has_investment_kw = any(kw in block.text for kw in investment_keywords)
            if has_investment_kw:
                assert len(block.evidence_spans) >= 1, \
                    f"Investment block {block.block_id} missing evidence: {block.text[:50]}..."

    def test_standardizer_schema_version(self, markdown_content):
        """验证生成的 envelope schema_version"""
        envelope = standardize_markdown_source(
            markdown=markdown_content,
            source_type="chat",
        )

        # ContentEnvelope 默认 schema_version 是 v0.5
        assert envelope.schema_version == "v0.5", \
            f"Expected schema_version v0.5, got {envelope.schema_version}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])