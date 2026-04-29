"""测试 F2 聚合层持久化存储."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from finer.aggregation import (
    AggregatedContext,
    ContextAggregator,
    EntityReference,
    L4AggregationLayer,
    create_l4_layer,
)
from finer.aggregation.storage import AggregationStorage


class TestAggregationStorage:
    """测试持久化存储."""

    def test_init_creates_database(self, tmp_path: Path):
        """初始化应创建数据库文件."""
        db_path = tmp_path / "aggregation.db"
        storage = AggregationStorage(db_path)

        assert db_path.exists()

    def test_save_and_load_context(self, tmp_path: Path):
        """保存和加载上下文."""
        storage = AggregationStorage(tmp_path / "aggregation.db")

        context = AggregatedContext(
            content_id="test-001",
            clean_text="腾讯股价今天大涨",
            entities=[
                EntityReference(
                    raw_text="腾讯",
                    normalized="0700.HK",
                    entity_type="ticker",
                    confidence=1.0,
                    market="HK",
                )
            ],
            summary="腾讯股价上涨",
            timestamp=datetime(2024, 1, 15, 10, 30),
            author="分析师A",
            source_platform="wechat",
        )

        storage.save_context(context)

        loaded = storage.load_context("test-001")

        assert loaded is not None
        assert loaded.content_id == "test-001"
        assert loaded.clean_text == "腾讯股价今天大涨"
        assert loaded.summary == "腾讯股价上涨"
        assert loaded.author == "分析师A"
        assert len(loaded.entities) == 1
        assert loaded.entities[0].normalized == "0700.HK"

    def test_load_nonexistent_context(self, tmp_path: Path):
        """加载不存在的上下文应返回 None."""
        storage = AggregationStorage(tmp_path / "aggregation.db")

        result = storage.load_context("nonexistent")

        assert result is None

    def test_entity_index_operations(self, tmp_path: Path):
        """实体索引操作."""
        storage = AggregationStorage(tmp_path / "aggregation.db")

        # 增量更新
        storage.update_entity_index("0700.HK", "content-001")
        storage.update_entity_index("0700.HK", "content-002")
        storage.update_entity_index("AAPL", "content-003")

        index = storage.load_entity_index()

        assert "0700.HK" in index
        assert "content-001" in index["0700.HK"]
        assert "content-002" in index["0700.HK"]
        assert "AAPL" in index
        assert index["AAPL"] == ["content-003"]

    def test_query_timeline(self, tmp_path: Path):
        """查询时间线."""
        storage = AggregationStorage(tmp_path / "aggregation.db")

        # 创建并保存多个上下文
        contexts = [
            AggregatedContext(
                content_id=f"content-{i:03d}",
                clean_text=f"关于腾讯的第 {i} 条内容",
                entities=[EntityReference("腾讯", "0700.HK", "ticker")],
                summary=f"摘要 {i}",
                timestamp=datetime(2024, 1, 15 + i, 10, 0),
                author=f"作者{i}",
                source_platform="wechat",
            )
            for i in range(5)
        ]

        for ctx in contexts:
            storage.save_context(ctx)
            storage.update_entity_index("0700.HK", ctx.content_id)

        # 查询时间线
        timeline = storage.query_timeline(
            "0700.HK",
            start_date=datetime(2024, 1, 16),
            end_date=datetime(2024, 1, 19),
        )

        assert len(timeline) == 3  # 16, 17, 18 三天

    def test_delete_context(self, tmp_path: Path):
        """删除上下文."""
        storage = AggregationStorage(tmp_path / "aggregation.db")

        context = AggregatedContext(
            content_id="to-delete",
            clean_text="将被删除",
            entities=[EntityReference("腾讯", "0700.HK", "ticker")],
        )

        storage.save_context(context)
        assert storage.load_context("to-delete") is not None

        storage.delete_context("to-delete")
        assert storage.load_context("to-delete") is None

    def test_stats(self, tmp_path: Path):
        """获取统计信息."""
        storage = AggregationStorage(tmp_path / "aggregation.db")

        for i in range(3):
            storage.save_context(
                AggregatedContext(
                    content_id=f"content-{i}",
                    clean_text=f"内容 {i}",
                    entities=[
                        EntityReference(f"股票{i}", f"TICK{i}", "ticker"),
                        EntityReference("腾讯", "0700.HK", "ticker"),
                    ],
                )
            )

        stats = storage.stats()

        assert stats["content_count"] == 3
        assert stats["unique_entities"] == 4  # TICK0, TICK1, TICK2, 0700.HK


class TestContextAggregatorWithStorage:
    """测试带持久化的聚合器."""

    def test_cold_start_recovery(self, tmp_path: Path):
        """冷启动恢复."""
        db_path = tmp_path / "aggregation.db"

        # 第一次实例：添加数据
        storage1 = AggregationStorage(db_path)
        aggregator1 = ContextAggregator(storage=storage1)

        context = AggregatedContext(
            content_id="test-recovery",
            clean_text="冷启动测试",
            entities=[EntityReference("腾讯", "0700.HK", "ticker")],
            summary="测试摘要",
        )

        aggregator1.add_context(context)

        # 第二次实例：从数据库恢复
        storage2 = AggregationStorage(db_path)
        aggregator2 = ContextAggregator(storage=storage2)

        assert "test-recovery" in aggregator2.content_store
        assert "0700.HK" in aggregator2.entity_index

    def test_persistence_on_add(self, tmp_path: Path):
        """添加上下文时持久化."""
        db_path = tmp_path / "aggregation.db"
        storage = AggregationStorage(db_path)
        aggregator = ContextAggregator(storage=storage)

        context = AggregatedContext(
            content_id="persist-test",
            clean_text="持久化测试",
            entities=[
                EntityReference("腾讯", "0700.HK", "ticker"),
                EntityReference("AAPL", "AAPL", "ticker"),
            ],
        )

        aggregator.add_context(context)

        # 直接从数据库验证
        loaded = storage.load_context("persist-test")
        assert loaded is not None
        assert loaded.content_id == "persist-test"

        # 实体索引也应更新
        index = storage.load_entity_index()
        assert "0700.HK" in index
        assert "AAPL" in index


class TestL4LayerWithStorage:
    """测试带持久化的 F2 聚合层."""

    def test_create_with_db_path(self, tmp_path: Path):
        """通过 db_path 参数创建."""
        db_path = tmp_path / "aggregation.db"

        layer = create_l4_layer(db_path=db_path)

        assert layer.context_aggregator.storage is not None

    def test_process_text_persists(self, tmp_path: Path):
        """处理文本应持久化."""
        db_path = tmp_path / "aggregation.db"

        layer1 = create_l4_layer(db_path=db_path)

        layer1.process_text(
            text="腾讯和阿里巴巴今天都有大动作",
            content_id="test-persist",
            timestamp=datetime(2024, 1, 15),
            author="测试作者",
            source_platform="wechat",
        )

        # 创建新实例，应恢复数据
        layer2 = create_l4_layer(db_path=db_path)

        assert "test-persist" in layer2.context_aggregator.content_store
        index = layer2.get_entity_index()
        # "腾讯" 和 "阿里巴巴" 应在索引中
        assert "0700.HK" in index or "BABA" in index


class TestBackwardCompatibility:
    """测试向后兼容（无持久化）."""

    def test_memory_only_mode(self):
        """无 storage 参数时应使用纯内存模式."""
        aggregator = ContextAggregator()

        context = AggregatedContext(
            content_id="memory-only",
            clean_text="纯内存模式",
            entities=[EntityReference("腾讯", "0700.HK", "ticker")],
        )

        aggregator.add_context(context)

        assert "memory-only" in aggregator.content_store
        assert aggregator.storage is None

    def test_l4_layer_without_storage(self):
        """F2 聚合层无 storage 参数时应正常工作."""
        layer = L4AggregationLayer()

        context = layer.process_text(
            text="腾讯股价分析",
            content_id="no-storage-test",
        )

        assert context.content_id == "no-storage-test"
        assert len(context.entities) > 0