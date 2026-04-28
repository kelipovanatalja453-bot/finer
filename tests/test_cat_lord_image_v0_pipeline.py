"""
猫大人图片策略 V0 Pipeline 测试

验证 content_standardizer 能从图片策略 Markdown fixture 生成 ContentEnvelope，
并正确处理 placeholder block 类型。
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from finer.parsing.content_standardizer import standardize_image_strategy
from finer.schemas.content_envelope import ContentEnvelope


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kol"


class TestCatLordImageV0Pipeline:
    """测试猫大人图片策略 V0 生成链路"""

    @pytest.fixture
    def markdown_content(self):
        """加载图片策略 Markdown fixture"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        return md_path.read_text(encoding="utf-8")

    @pytest.fixture
    def expected_v0(self):
        """加载 expected V0 golden case"""
        v0_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.expected_v0.json"
        with open(v0_path, encoding="utf-8") as f:
            return json.load(f)

    def test_standardizer_generates_image_envelope(self, markdown_content):
        """验证 standardize_image_strategy 能生成 ContentEnvelope"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
            source_uri="/Users/zhouhongyuan/Library/Containers/com.bytedance.macos.feishu/Data/Library/Application Support/LarkShell/sdk_storage/cca2e3816618ff1cd423ead1e51b0034/resources/images/img_v3_02114_7cb4416b-0376-499c-9e39-e086723d2f0g.jpg",
            creator_id="cat_lord_fire",
            creator_name="猫大人FIRE",
            published_at=datetime(2026, 4, 26, 10, 0),
        )

        assert isinstance(envelope, ContentEnvelope)
        assert envelope.source_type == "image"
        assert envelope.creator_name == "猫大人FIRE"

    def test_standardizer_source_type_image(self, markdown_content):
        """验证生成的 source_type 为 image"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        assert envelope.source_type == "image"

    def test_standardizer_block_count(self, markdown_content):
        """验证生成的 block 数量在合理范围"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
            creator_name="猫大人FIRE",
        )

        # 至少 5 个 blocks
        assert len(envelope.blocks) >= 5, \
            f"Expected at least 5 blocks, got {len(envelope.blocks)}"

        # 不超过 100 个 blocks
        assert len(envelope.blocks) <= 100, \
            f"Too many blocks: {len(envelope.blocks)}"

    def test_standardizer_block_order_continuous(self, markdown_content):
        """验证 block order 连续"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        orders = [b.order for b in envelope.blocks]
        expected_orders = list(range(len(envelope.blocks)))

        assert sorted(orders) == expected_orders, \
            f"Block orders not continuous: {orders}"

    def test_standardizer_has_placeholder_block_types(self, markdown_content):
        """验证生成的 block 包含 placeholder 类型"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        block_types = {b.block_type for b in envelope.blocks}

        # 必须包含至少 2 种 placeholder 类型
        placeholder_types = {"table_region", "chart_region", "image_region", "ocr_unreadable"}
        found = block_types & placeholder_types

        assert len(found) >= 2, \
            f"Expected at least 2 placeholder types, found: {found}"

    def test_standardizer_has_paragraph_or_list(self, markdown_content):
        """验证生成的 block 包含 paragraph 或 list"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        block_types = {b.block_type for b in envelope.blocks}

        assert "paragraph" in block_types or "list" in block_types, \
            f"Missing paragraph/list, got: {block_types}"

    def test_standardizer_each_block_has_quality_card(self, markdown_content):
        """验证每个 block 有 quality_card"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        for block in envelope.blocks:
            assert block.quality_card is not None, \
                f"Block {block.block_id} missing quality_card"
            assert block.quality_card.overall_score >= 0.0, \
                f"Block {block.block_id} has invalid overall_score"

    def test_standardizer_placeholder_quality_card_lower(self, markdown_content):
        """验证 placeholder block 的 quality_card 分数较低"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        placeholder_types = {"table_region", "chart_region", "image_region", "ocr_unreadable"}

        for block in envelope.blocks:
            if block.block_type in placeholder_types:
                # placeholder block 的 overall_score 应低于普通 block
                assert block.quality_card.overall_score <= 0.65, \
                    f"Placeholder block {block.block_id} has too high score: {block.quality_card.overall_score}"

    def test_standardizer_placeholder_gate_status_review_or_reject(self, markdown_content):
        """验证 placeholder block 的 gate_status 为 review 或 reject"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        placeholder_types = {"table_region", "chart_region", "image_region", "ocr_unreadable"}

        for block in envelope.blocks:
            if block.block_type in placeholder_types:
                assert block.quality_card.gate_status in ("review", "reject"), \
                    f"Placeholder block {block.block_id} gate_status should be review/reject, got {block.quality_card.gate_status}"

    def test_standardizer_investment_blocks_have_evidence(self, markdown_content):
        """验证投资相关 block 有 evidence span"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        investment_keywords = ["目标价", "看好", "风险", "机会", "盈利"]
        skip_types = {"heading", "table_region", "chart_region", "image_region", "ocr_unreadable"}

        for block in envelope.blocks:
            if block.block_type in skip_types:
                continue

            has_investment_kw = any(kw in block.text for kw in investment_keywords)
            if has_investment_kw:
                assert len(block.evidence_spans) >= 1, \
                    f"Investment block {block.block_id} missing evidence: {block.text[:50]}..."

    def test_standardizer_schema_version(self, markdown_content):
        """验证生成的 envelope schema_version"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        assert envelope.schema_version == "v0.5", \
            f"Expected schema_version v0.5, got {envelope.schema_version}"

    def test_standardizer_matches_expected_source_type(self, markdown_content, expected_v0):
        """验证生成的 source_type 与 expected 一致"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
        )

        assert envelope.source_type == expected_v0["source_type"]

    def test_standardizer_matches_expected_creator_name(self, markdown_content, expected_v0):
        """验证生成的 creator_name 与 expected 一致"""
        envelope = standardize_image_strategy(
            text_content=markdown_content,
            creator_name="猫大人FIRE",
        )

        assert envelope.creator_name == expected_v0["creator_name"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])