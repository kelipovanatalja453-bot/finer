"""
猫大人图片策略 Fixture 契约测试

验证图片策略 fixture 满足 Agent D 的契约要求。
"""

import json
import pytest
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kol"


class TestCatLordImageMarkdownFixture:
    """测试猫大人图片策略 Markdown fixture"""

    def test_markdown_file_exists(self):
        """验证 Markdown 文件存在"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        assert md_path.exists(), f"Markdown fixture not found: {md_path}"

    def test_markdown_has_source_image_path(self):
        """验证 Markdown 包含来源图片路径"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        content = md_path.read_text(encoding="utf-8")

        assert "来源图片" in content, "Missing source image path marker"
        assert ".jpg" in content, "Missing image file extension"

    def test_markdown_has_source_type_image(self):
        """验证 Markdown 标明 source_type=image"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        content = md_path.read_text(encoding="utf-8")

        assert "source_type" in content, "Missing source_type marker"
        assert "image" in content, "source_type should be image"

    def test_markdown_has_kol_marker(self):
        """验证 Markdown 标明 KOL 为猫大人"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        content = md_path.read_text(encoding="utf-8")

        assert "猫大人" in content, "Missing KOL marker (猫大人)"

    def test_markdown_has_placeholder_markers(self):
        """验证 Markdown 包含 placeholder 标记"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        content = md_path.read_text(encoding="utf-8")

        # 至少包含 OCR_UNREADABLE, TABLE_REGION, CHART_REGION, IMAGE_REGION 中的 2 种
        placeholders = ["[OCR_UNREADABLE]", "[TABLE_REGION]", "[CHART_REGION]", "[IMAGE_REGION]"]
        found = [p for p in placeholders if p in content]
        assert len(found) >= 2, f"Expected at least 2 placeholder types, found: {found}"

    def test_markdown_has_investment_content(self):
        """验证 Markdown 包含投资相关内容"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        content = md_path.read_text(encoding="utf-8")

        investment_keywords = ["目标价", "看好", "风险", "机会", "盈利"]
        found = [kw for kw in investment_keywords if kw in content]
        assert len(found) >= 3, f"Missing investment keywords, found: {found}"

    def test_markdown_no_position_percentage(self):
        """验证 Markdown 不包含仓位百分比"""
        md_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.md"
        content = md_path.read_text(encoding="utf-8")

        # 不应包含仓位百分比相关内容
        position_patterns = ["仓位%", "仓位建议", "10%", "20%", "30%"]
        for pattern in position_patterns:
            if pattern in content:
                # 允许在说明中提到"不提供仓位百分比"
                if "不提供" in content:
                    continue
                pytest.fail(f"Found position percentage pattern: {pattern}")


class TestCatLordImageV0Fixture:
    """测试猫大人图片策略 V0 fixture"""

    @pytest.fixture
    def v0_data(self):
        """加载 V0 fixture 数据"""
        v0_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.expected_v0.json"
        with open(v0_path, encoding="utf-8") as f:
            return json.load(f)

    def test_v0_file_exists(self):
        """验证 V0 JSON 文件存在且格式正确"""
        v0_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.expected_v0.json"
        assert v0_path.exists(), f"V0 fixture not found: {v0_path}"

        with open(v0_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_v0_source_type_is_image(self, v0_data):
        """验证 V0 source_type 为 image"""
        assert v0_data["source_type"] == "image", \
            f"Expected source_type=image, got {v0_data['source_type']}"

    def test_v0_schema_version(self, v0_data):
        """验证 V0 schema_version"""
        assert v0_data["schema_version"] == "v0.5", \
            f"Expected schema_version v0.5, got {v0_data['schema_version']}"

    def test_v0_has_minimum_blocks(self, v0_data):
        """验证 V0 至少有 8 个 ContentBlock"""
        blocks = v0_data.get("blocks", [])
        assert len(blocks) >= 8, f"Expected at least 8 blocks, got {len(blocks)}"

    def test_v0_has_placeholder_block_types(self, v0_data):
        """验证 V0 包含 placeholder block 类型"""
        blocks = v0_data.get("blocks", [])
        block_types = set(block.get("block_type") for block in blocks)

        # 必须包含至少 2 种 placeholder 类型
        placeholder_types = {"table_region", "chart_region", "image_region", "ocr_unreadable"}
        found = block_types & placeholder_types
        assert len(found) >= 2, f"Expected at least 2 placeholder types, found: {found}"

    def test_v0_has_paragraph_and_list(self, v0_data):
        """验证 V0 包含 paragraph 或 list"""
        blocks = v0_data.get("blocks", [])
        block_types = set(block.get("block_type") for block in blocks)

        assert "paragraph" in block_types or "list" in block_types, \
            f"Missing paragraph/list, got: {block_types}"

    def test_v0_each_block_has_quality_card(self, v0_data):
        """验证每个 block 有 quality_card"""
        blocks = v0_data.get("blocks", [])

        for block in blocks:
            assert "quality_card" in block, \
                f"Block {block.get('block_id')} missing quality_card"
            qc = block["quality_card"]
            assert "overall_score" in qc, \
                f"Block {block.get('block_id')} quality_card missing overall_score"
            assert "gate_status" in qc, \
                f"Block {block.get('block_id')} quality_card missing gate_status"

    def test_v0_placeholder_blocks_have_review_or_reject_gate(self, v0_data):
        """验证 placeholder block 的 gate_status 为 review 或 reject"""
        blocks = v0_data.get("blocks", [])
        placeholder_types = {"table_region", "chart_region", "image_region", "ocr_unreadable"}

        for block in blocks:
            if block.get("block_type") in placeholder_types:
                gate = block["quality_card"]["gate_status"]
                assert gate in ("review", "reject"), \
                    f"Placeholder block {block.get('block_id')} should have gate_status review/reject, got {gate}"

    def test_v0_investment_blocks_have_evidence_spans(self, v0_data):
        """验证投资相关 block 有 evidence_spans（heading/placeholder除外）"""
        blocks = v0_data.get("blocks", [])

        investment_keywords = ["目标价", "看好", "风险", "机会", "盈利"]
        skip_types = {"heading", "table_region", "chart_region", "image_region", "ocr_unreadable"}

        for block in blocks:
            text = block.get("text", "")
            block_type = block.get("block_type", "")
            has_investment_kw = any(kw in text for kw in investment_keywords)

            # heading 和 placeholder block 不需要 evidence_spans
            if block_type in skip_types:
                continue

            if has_investment_kw:
                assert len(block.get("evidence_spans", [])) >= 1, \
                    f"Investment block {block.get('block_id')} missing evidence_spans"


class TestCatLordImageV1Fixture:
    """测试猫大人图片策略 V1 fixture"""

    @pytest.fixture
    def v1_data(self):
        """加载 V1 fixture 数据"""
        v1_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.expected_v1.json"
        with open(v1_path, encoding="utf-8") as f:
            return json.load(f)

    def test_v1_file_exists(self):
        """验证 V1 JSON 文件存在且格式正确"""
        v1_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.expected_v1.json"
        assert v1_path.exists(), f"V1 fixture not found: {v1_path}"

        with open(v1_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_v1_has_minimum_intents(self, v1_data):
        """验证 V1 至少有 5 条 intents"""
        intents = v1_data.get("intents", [])
        assert len(intents) >= 5, f"Expected at least 5 intents, got {len(intents)}"

    def test_v1_covers_market_or_index(self, v1_data):
        """验证覆盖市场/指数判断"""
        intents = v1_data.get("intents", [])

        macro_or_index = [
            i for i in intents
            if i.get("target_type") in ("macro", "index")
        ]

        assert len(macro_or_index) >= 1, \
            f"Expected at least 1 macro/index intent, got {len(macro_or_index)}"

    def test_v1_covers_sector(self, v1_data):
        """验证覆盖板块判断"""
        intents = v1_data.get("intents", [])

        sector_intents = [
            i for i in intents
            if i.get("target_type") == "sector"
        ]

        assert len(sector_intents) >= 1, \
            f"Expected at least 1 sector intent, got {len(sector_intents)}"

    def test_v1_covers_individual_stocks(self, v1_data):
        """验证覆盖个股判断"""
        intents = v1_data.get("intents", [])

        stock_intents = [
            i for i in intents
            if i.get("target_type") == "stock"
        ]

        assert len(stock_intents) >= 4, \
            f"Expected at least 4 stock intents, got {len(stock_intents)}"

    def test_v1_covers_risk_or_uncertainty(self, v1_data):
        """验证覆盖风险/不确定性"""
        intents = v1_data.get("intents", [])

        risk_intents = [
            i for i in intents
            if i.get("ambiguity_flags") or
               i.get("direction") in ("bearish", "unknown") or
               i.get("actionability") == "review_required"
        ]

        assert len(risk_intents) >= 1, \
            f"Expected at least 1 risk/uncertainty intent, got {len(risk_intents)}"

    def test_v1_covers_chart_or_table_evidence(self, v1_data):
        """验证覆盖图表/表格证据"""
        intents = v1_data.get("intents", [])

        # 检查是否有 intent 的 block_ids 包含 placeholder block
        placeholder_types = ["table_region", "chart_region"]

        chart_table_intents = [
            i for i in intents
            if any(flag in str(i.get("ambiguity_flags", [])) for flag in ["chart", "table", "visual"])
            or i.get("target_type") == "unknown" and "图表" in i.get("target_name", "")
        ]

        assert len(chart_table_intents) >= 1, \
            f"Expected at least 1 chart/table evidence intent, got {len(chart_table_intents)}"

    def test_v1_no_position_percentage(self, v1_data):
        """验证不包含仓位百分比"""
        intents = v1_data.get("intents", [])

        for intent in intents:
            metadata = intent.get("metadata", {})
            # 不应包含 position_percentage 字段
            assert "position_percentage" not in metadata, \
                f"Intent {intent.get('intent_id')} should not have position_percentage"

    def test_v1_ambiguity_flags_preserved(self, v1_data):
        """验证模糊内容保留 ambiguity_flags"""
        intents = v1_data.get("intents", [])

        intents_with_ambiguity = [
            i for i in intents
            if i.get("ambiguity_flags") and len(i.get("ambiguity_flags")) > 0
        ]

        assert len(intents_with_ambiguity) >= 2, \
            f"Expected at least 2 intents with ambiguity_flags, got {len(intents_with_ambiguity)}"

    def test_v1_each_intent_has_evidence_bindings(self, v1_data):
        """验证每个 intent 绑定 evidence_span（或明确标注无证据）"""
        intents = v1_data.get("intents", [])

        for intent in intents:
            evidence_ids = intent.get("evidence_span_ids", [])
            ambiguity_flags = intent.get("ambiguity_flags", [])

            # 如果没有 evidence，必须有 ambiguity_flag 说明原因
            if len(evidence_ids) == 0:
                assert len(ambiguity_flags) >= 1, \
                    f"Intent {intent.get('intent_id')} missing evidence and ambiguity_flags"


class TestV0V1ImageConsistency:
    """测试图片策略 V0 和 V1 之间的一致性"""

    @pytest.fixture
    def v0_data(self):
        v0_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.expected_v0.json"
        with open(v0_path, encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def v1_data(self):
        v1_path = FIXTURE_DIR / "cat_lord_image_strategy_2026_04_26.expected_v1.json"
        with open(v1_path, encoding="utf-8") as f:
            return json.load(f)

    def test_envelope_id_consistent(self, v0_data, v1_data):
        """验证 envelope_id 一致"""
        v0_envelope_id = v0_data.get("envelope_id")
        intents = v1_data.get("intents", [])

        for intent in intents:
            assert intent.get("envelope_id") == v0_envelope_id, \
                f"Inconsistent envelope_id: {intent.get('envelope_id')} vs {v0_envelope_id}"

    def test_source_type_consistent(self, v0_data):
        """验证 source_type 为 image"""
        assert v0_data["source_type"] == "image"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])