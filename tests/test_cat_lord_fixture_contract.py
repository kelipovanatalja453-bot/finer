"""
猫大人 Fixture 契约测试

验证猫大人策略 fixture 满足 Agent 4 的契约要求。
"""

import json
import pytest
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kol"


class TestCatLordMarkdownFixture:
    """测试猫大人 Markdown fixture 文件"""

    def test_markdown_file_exists(self):
        """验证 Markdown 文件存在"""
        md_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.md"
        assert md_path.exists(), f"Markdown fixture not found: {md_path}"

    def test_markdown_has_source_metadata(self):
        """验证 Markdown 包含来源说明"""
        md_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.md"
        content = md_path.read_text(encoding="utf-8")

        assert "飞书" in content, "Missing source platform (飞书)"
        assert "猫大人FIRE" in content, "Missing KOL name"
        assert "2026-03-12" in content, "Missing publish date"

    def test_markdown_has_multiple_sections(self):
        """验证 Markdown 包含多个分析段落"""
        md_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.md"
        content = md_path.read_text(encoding="utf-8")

        # 检查包含5个主要分析段落
        assert "理想汽车" in content, "Missing Li Auto analysis"
        assert "宝丰能源" in content, "Missing Baofeng Energy analysis"
        assert "算电协同" in content or "绿电" in content, "Missing green power analysis"
        assert "阿特斯" in content or "CSIQ" in content, "Missing Canadian Solar analysis"
        assert "腾讯音乐" in content, "Missing Tencent Music analysis"

    def test_markdown_has_investment_content(self):
        """验证 Markdown 包含投资相关内容"""
        md_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.md"
        content = md_path.read_text(encoding="utf-8")

        # 检查投资关键词
        investment_keywords = ["目标价", "投资价值", "盈利", "风险", "机会"]
        found_keywords = [kw for kw in investment_keywords if kw in content]
        assert len(found_keywords) >= 3, f"Missing investment keywords, found: {found_keywords}"


class TestCatLordV0Fixture:
    """测试猫大人 V0 (ContentEnvelope) fixture"""

    @pytest.fixture
    def v0_data(self):
        """加载 V0 fixture 数据"""
        v0_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.expected_v0.json"
        with open(v0_path, encoding="utf-8") as f:
            return json.load(f)

    def test_v0_file_exists(self):
        """验证 V0 JSON 文件存在且格式正确"""
        v0_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.expected_v0.json"
        assert v0_path.exists(), f"V0 fixture not found: {v0_path}"

        # 验证 JSON 格式正确
        with open(v0_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_v0_has_envelope_metadata(self, v0_data):
        """验证 V0 包含 ContentEnvelope 元数据"""
        assert "envelope_id" in v0_data
        assert "schema_version" in v0_data
        assert v0_data["schema_version"] == "v0.5", \
            f"Expected schema_version v0.5, got {v0_data['schema_version']}"
        assert "source_type" in v0_data
        assert "creator_name" in v0_data
        assert "published_at" in v0_data

    def test_v0_has_minimum_blocks(self, v0_data):
        """验证 V0 至少有 8 个 ContentBlock"""
        blocks = v0_data.get("blocks", [])
        assert len(blocks) >= 8, f"Expected at least 8 blocks, got {len(blocks)}"

    def test_v0_has_multiple_block_types(self, v0_data):
        """验证 V0 包含多种 block 类型"""
        blocks = v0_data.get("blocks", [])
        block_types = set(block.get("block_type") for block in blocks)

        # 至少包含 paragraph, list, heading 中的 2 种
        required_types = {"paragraph", "list", "heading"}
        found_types = block_types & required_types
        assert len(found_types) >= 2, f"Expected at least 2 of {required_types}, got {found_types}"

    def test_v0_each_block_has_quality_card(self, v0_data):
        """验证每个 block 有 quality_card"""
        blocks = v0_data.get("blocks", [])
        for block in blocks:
            assert "quality_card" in block, f"Block {block.get('block_id')} missing quality_card"
            qc = block["quality_card"]
            assert "overall_score" in qc, f"Block {block.get('block_id')} quality_card missing overall_score"
            assert "gate_status" in qc, f"Block {block.get('block_id')} quality_card missing gate_status"

    def test_v0_investment_blocks_have_evidence_spans(self, v0_data):
        """验证投资相关 block 有 evidence_spans"""
        blocks = v0_data.get("blocks", [])

        # 统计有 evidence_spans 的 block 数量
        blocks_with_evidence = [
            block for block in blocks
            if block.get("evidence_spans") and len(block["evidence_spans"]) > 0
        ]

        # 至少 3 个 block 有 evidence_spans
        assert len(blocks_with_evidence) >= 3, \
            f"Expected at least 3 blocks with evidence_spans, got {len(blocks_with_evidence)}"

    def test_v0_evidence_spans_valid(self, v0_data):
        """验证 evidence_span 结构正确"""
        blocks = v0_data.get("blocks", [])

        for block in blocks:
            for span in block.get("evidence_spans", []):
                assert "evidence_span_id" in span, "Evidence span missing id"
                assert "block_id" in span, "Evidence span missing block_id"
                assert "text" in span, "Evidence span missing text"
                assert "confidence" in span, "Evidence span missing confidence"
                assert 0.0 <= span["confidence"] <= 1.0, \
                    f"Invalid confidence: {span['confidence']}"

    def test_v0_has_temporal_anchors(self, v0_data):
        """验证 V0 包含 temporal_anchors"""
        anchors = v0_data.get("temporal_anchors", [])
        assert len(anchors) >= 1, "Expected at least 1 temporal anchor"

    def test_v0_has_entity_anchors(self, v0_data):
        """验证 V0 包含 entity_anchors"""
        anchors = v0_data.get("entity_anchors", [])
        assert len(anchors) >= 4, f"Expected at least 4 entity anchors, got {len(anchors)}"


class TestCatLordV1Fixture:
    """测试猫大人 V1 (NormalizedInvestmentIntent) fixture"""

    @pytest.fixture
    def v1_data(self):
        """加载 V1 fixture 数据"""
        v1_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.expected_v1.json"
        with open(v1_path, encoding="utf-8") as f:
            return json.load(f)

    def test_v1_file_exists(self):
        """验证 V1 JSON 文件存在且格式正确"""
        v1_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.expected_v1.json"
        assert v1_path.exists(), f"V1 fixture not found: {v1_path}"

        with open(v1_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_v1_has_intents(self, v1_data):
        """验证 V1 包含 intents 列表"""
        intents = v1_data.get("intents", [])
        assert isinstance(intents, list)
        assert len(intents) >= 5, f"Expected at least 5 intents, got {len(intents)}"

    def test_v1_intent_structure(self, v1_data):
        """验证每个 intent 的结构"""
        intents = v1_data.get("intents", [])

        required_fields = [
            "intent_id", "schema_version", "envelope_id",
            "target_type", "target_name", "direction",
            "actionability", "conviction", "confidence"
        ]

        for intent in intents:
            for field in required_fields:
                assert field in intent, \
                    f"Intent {intent.get('intent_id', 'unknown')} missing field: {field}"

    def test_v1_covers_individual_stocks(self, v1_data):
        """验证覆盖个股判断"""
        intents = v1_data.get("intents", [])

        stock_intents = [
            i for i in intents
            if i.get("target_type") == "stock"
        ]

        assert len(stock_intents) >= 4, \
            f"Expected at least 4 stock intents, got {len(stock_intents)}"

        # 检查覆盖的股票
        tickers = {i.get("target_symbol") for i in stock_intents if i.get("target_symbol")}
        expected_tickers = {"LI", "600989", "CSIQ", "TME"}
        found_tickers = tickers & expected_tickers

        assert len(found_tickers) >= 3, \
            f"Expected coverage of {expected_tickers}, found: {found_tickers}"

    def test_v1_covers_sectors(self, v1_data):
        """验证覆盖行业/板块判断"""
        intents = v1_data.get("intents", [])

        sector_intents = [
            i for i in intents
            if i.get("target_type") == "sector"
        ]

        assert len(sector_intents) >= 1, \
            f"Expected at least 1 sector intent, got {len(sector_intents)}"

    def test_v1_covers_risk_warnings(self, v1_data):
        """验证包含风险提示"""
        intents = v1_data.get("intents", [])

        # 检查 ambiguity_flags 或 risk warnings
        intents_with_risk = [
            i for i in intents
            if i.get("ambiguity_flags") or
               i.get("direction") in ["bearish", "risk_warning"] or
               (i.get("metadata", {}).get("risk_warning") is not None)
        ]

        assert len(intents_with_risk) >= 1, \
            "Expected at least 1 intent with risk warning or risk-related direction"

    def test_v1_no_position_percentage(self, v1_data):
        """验证不包含仓位百分比"""
        intents = v1_data.get("intents", [])

        for intent in intents:
            # 检查 metadata 中没有 position_percentage
            metadata = intent.get("metadata", {})
            assert "position_percentage" not in metadata, \
                f"Intent {intent.get('intent_id')} should not have position_percentage"

    def test_v1_intent_has_evidence_bindings(self, v1_data):
        """验证每个 intent 绑定 evidence_span"""
        intents = v1_data.get("intents", [])

        for intent in intents:
            evidence_ids = intent.get("evidence_span_ids", [])
            assert len(evidence_ids) >= 1, \
                f"Intent {intent.get('intent_id')} should have at least 1 evidence_span_id"

    def test_v1_direction_values_valid(self, v1_data):
        """验证 direction 值有效"""
        intents = v1_data.get("intents", [])

        valid_directions = {"bullish", "bearish", "neutral", "mixed", "unknown"}

        for intent in intents:
            direction = intent.get("direction")
            assert direction in valid_directions, \
                f"Invalid direction: {direction}"

    def test_v1_actionability_values_valid(self, v1_data):
        """验证 actionability 值有效"""
        intents = v1_data.get("intents", [])

        valid_actionabilities = {"opinion", "watch", "explicit_action", "review_required"}

        for intent in intents:
            actionability = intent.get("actionability")
            assert actionability in valid_actionabilities, \
                f"Invalid actionability: {actionability}"

    def test_v1_conviction_in_range(self, v1_data):
        """验证 conviction 在有效范围"""
        intents = v1_data.get("intents", [])

        for intent in intents:
            conviction = intent.get("conviction")
            assert 0.0 <= conviction <= 1.0, \
                f"Conviction out of range: {conviction}"


class TestV0V1Consistency:
    """测试 V0 和 V1 之间的一致性"""

    @pytest.fixture
    def v0_data(self):
        v0_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.expected_v0.json"
        with open(v0_path, encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def v1_data(self):
        v1_path = FIXTURE_DIR / "cat_lord_strategy_2026_03_12.expected_v1.json"
        with open(v1_path, encoding="utf-8") as f:
            return json.load(f)

    def test_envelope_id_consistent(self, v0_data, v1_data):
        """验证 envelope_id 一致"""
        v0_envelope_id = v0_data.get("envelope_id")
        intents = v1_data.get("intents", [])

        for intent in intents:
            assert intent.get("envelope_id") == v0_envelope_id, \
                f"Inconsistent envelope_id: {intent.get('envelope_id')} vs {v0_envelope_id}"

    def test_block_ids_exist_in_v0(self, v0_data, v1_data):
        """验证 V1 引用的 block_ids 在 V0 中存在"""
        v0_block_ids = {b.get("block_id") for b in v0_data.get("blocks", [])}
        intents = v1_data.get("intents", [])

        for intent in intents:
            for block_id in intent.get("block_ids", []):
                assert block_id in v0_block_ids, \
                    f"Block {block_id} not found in V0"

    def test_evidence_span_ids_exist_in_v0(self, v0_data, v1_data):
        """验证 V1 引用的 evidence_span_ids 在 V0 中存在"""
        # 收集 V0 中所有 evidence_span_id
        v0_evidence_ids = set()
        for block in v0_data.get("blocks", []):
            for span in block.get("evidence_spans", []):
                v0_evidence_ids.add(span.get("evidence_span_id"))

        intents = v1_data.get("intents", [])

        for intent in intents:
            for evidence_id in intent.get("evidence_span_ids", []):
                assert evidence_id in v0_evidence_ids, \
                    f"Evidence span {evidence_id} not found in V0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
