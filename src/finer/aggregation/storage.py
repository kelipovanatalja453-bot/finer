"""F2 Anchor 聚合层持久化存储.

使用 SQLite 存储聚合数据，支持冷启动恢复。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from finer.aggregation import AggregatedContext, EntityReference

logger = logging.getLogger(__name__)


class AggregationStorage:
    """聚合数据持久化存储.

    使用 SQLite 存储:
    - entity_index: 实体 -> 内容 ID 列表
    - content_store: 内容 ID -> AggregatedContext
    - entity_contexts: 实体的跨内容上下文

    遵循 Repository Pattern，与业务逻辑解耦。
    """

    def __init__(self, db_path: Path):
        """初始化存储.

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- 内容上下文表
                CREATE TABLE IF NOT EXISTS content_contexts (
                    content_id TEXT PRIMARY KEY,
                    clean_text TEXT NOT NULL,
                    summary TEXT,
                    market_data TEXT,  -- JSON
                    cross_references TEXT,  -- JSON array
                    timestamp TEXT,
                    author TEXT,
                    source_platform TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- 实体引用表
                CREATE TABLE IF NOT EXISTS entity_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    normalized TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    market TEXT,
                    FOREIGN KEY (content_id) REFERENCES content_contexts(content_id) ON DELETE CASCADE,
                    UNIQUE(content_id, raw_text, normalized)
                );

                -- 实体索引表 (normalized_entity -> content_ids)
                CREATE TABLE IF NOT EXISTS entity_index (
                    normalized_entity TEXT PRIMARY KEY,
                    content_ids TEXT NOT NULL  -- JSON array
                );

                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_entity_refs_normalized ON entity_references(normalized);
                CREATE INDEX IF NOT EXISTS idx_entity_refs_content ON entity_references(content_id);
                CREATE INDEX IF NOT EXISTS idx_content_timestamp ON content_contexts(timestamp);
            """)
            conn.commit()

    def save_context(self, context: AggregatedContext) -> None:
        """保存上下文到数据库.

        Args:
            context: 聚合后的上下文
        """
        with sqlite3.connect(self.db_path) as conn:
            # 保存内容上下文
            conn.execute("""
                INSERT OR REPLACE INTO content_contexts
                (content_id, clean_text, summary, market_data, cross_references,
                 timestamp, author, source_platform, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                context.content_id,
                context.clean_text,
                context.summary,
                json.dumps(context.market_data) if context.market_data else None,
                json.dumps(context.cross_references) if context.cross_references else None,
                context.timestamp.isoformat() if context.timestamp else None,
                context.author,
                context.source_platform,
            ))

            # 保存实体引用
            for entity in context.entities:
                conn.execute("""
                    INSERT OR IGNORE INTO entity_references
                    (content_id, raw_text, normalized, entity_type, confidence, market)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    context.content_id,
                    entity.raw_text,
                    entity.normalized,
                    entity.entity_type,
                    entity.confidence,
                    entity.market,
                ))

            conn.commit()

    def load_context(self, content_id: str) -> Optional[AggregatedContext]:
        """从数据库加载上下文.

        Args:
            content_id: 内容 ID

        Returns:
            上下文对象，不存在则返回 None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 加载内容上下文
            row = conn.execute(
                "SELECT * FROM content_contexts WHERE content_id = ?",
                (content_id,)
            ).fetchone()

            if not row:
                return None

            # 加载实体引用
            entity_rows = conn.execute(
                "SELECT * FROM entity_references WHERE content_id = ?",
                (content_id,)
            ).fetchall()

            entities = [
                EntityReference(
                    raw_text=er["raw_text"],
                    normalized=er["normalized"],
                    entity_type=er["entity_type"],
                    confidence=er["confidence"],
                    market=er["market"],
                )
                for er in entity_rows
            ]

            return AggregatedContext(
                content_id=row["content_id"],
                clean_text=row["clean_text"],
                entities=entities,
                summary=row["summary"],
                market_data=json.loads(row["market_data"]) if row["market_data"] else None,
                cross_references=json.loads(row["cross_references"]) if row["cross_references"] else [],
                timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                author=row["author"],
                source_platform=row["source_platform"],
            )

    def load_all_contexts(self) -> Dict[str, AggregatedContext]:
        """加载所有上下文.

        Returns:
            内容 ID -> 上下文的映射
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 获取所有内容 ID
            content_ids = [
                row[0] for row in conn.execute(
                    "SELECT content_id FROM content_contexts"
                )
            ]

        return {cid: self.load_context(cid) for cid in content_ids if (ctx := self.load_context(cid))}

    def load_entity_index(self) -> Dict[str, List[str]]:
        """加载实体索引.

        Returns:
            标准化实体 -> 内容 ID 列表的映射
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT normalized_entity, content_ids FROM entity_index").fetchall()

            return {
                row["normalized_entity"]: json.loads(row["content_ids"])
                for row in rows
            }

    def save_entity_index(self, entity_index: Dict[str, List[str]]) -> None:
        """保存实体索引.

        Args:
            entity_index: 标准化实体 -> 内容 ID 列表的映射
        """
        with sqlite3.connect(self.db_path) as conn:
            for entity, content_ids in entity_index.items():
                conn.execute("""
                    INSERT OR REPLACE INTO entity_index (normalized_entity, content_ids)
                    VALUES (?, ?)
                """, (entity, json.dumps(content_ids)))

            conn.commit()

    def update_entity_index(self, entity: str, content_id: str) -> None:
        """增量更新实体索引.

        Args:
            entity: 标准化实体
            content_id: 内容 ID
        """
        with sqlite3.connect(self.db_path) as conn:
            # 获取当前索引
            row = conn.execute(
                "SELECT content_ids FROM entity_index WHERE normalized_entity = ?",
                (entity,)
            ).fetchone()

            if row:
                content_ids = json.loads(row[0])
                if content_id not in content_ids:
                    content_ids.append(content_id)
                    conn.execute("""
                        UPDATE entity_index SET content_ids = ?
                        WHERE normalized_entity = ?
                    """, (json.dumps(content_ids), entity))
            else:
                conn.execute("""
                    INSERT INTO entity_index (normalized_entity, content_ids)
                    VALUES (?, ?)
                """, (entity, json.dumps([content_id])))

            conn.commit()

    def query_timeline(
        self,
        entity: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """查询某实体的时间线.

        Args:
            entity: 标准化实体
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制

        Returns:
            时间线条目列表
        """
        # 先获取实体对应的内容 ID
        entity_index = self.load_entity_index()
        content_ids = entity_index.get(entity, [])

        if not content_ids:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # 构建查询
            placeholders = ",".join("?" * len(content_ids))
            sql = f"""
                SELECT content_id, timestamp, summary, author, source_platform
                FROM content_contexts
                WHERE content_id IN ({placeholders})
            """
            params: List[Any] = list(content_ids)

            if start_date:
                sql += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                sql += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            return [
                {
                    "content_id": row["content_id"],
                    "timestamp": row["timestamp"],
                    "summary": row["summary"],
                    "author": row["author"],
                    "source": row["source_platform"],
                }
                for row in rows
                if row["timestamp"]  # 过滤掉无时间戳的
            ]

    def delete_context(self, content_id: str) -> None:
        """删除上下文.

        Args:
            content_id: 内容 ID
        """
        with sqlite3.connect(self.db_path) as conn:
            # 由于有 ON DELETE CASCADE，删除 content_contexts 会自动删除相关 entity_references
            conn.execute("DELETE FROM content_contexts WHERE content_id = ?", (content_id,))

            # 更新实体索引
            conn.execute("""
                UPDATE entity_index
                SET content_ids = (
                    SELECT json_group_array(content_id)
                    FROM entity_references
                    WHERE normalized = entity_index.normalized_entity
                )
            """)

            # 清理空的索引
            conn.execute("DELETE FROM entity_index WHERE content_ids = '[]' OR content_ids IS NULL")

            conn.commit()

    def clear(self) -> None:
        """清空所有数据（用于测试）."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM entity_references")
            conn.execute("DELETE FROM content_contexts")
            conn.execute("DELETE FROM entity_index")
            conn.commit()

    def stats(self) -> Dict[str, int]:
        """获取存储统计.

        Returns:
            统计信息字典
        """
        with sqlite3.connect(self.db_path) as conn:
            content_count = conn.execute("SELECT COUNT(*) FROM content_contexts").fetchone()[0]
            entity_count = conn.execute("SELECT COUNT(DISTINCT normalized) FROM entity_references").fetchone()[0]
            index_count = conn.execute("SELECT COUNT(*) FROM entity_index").fetchone()[0]

            return {
                "content_count": content_count,
                "unique_entities": entity_count,
                "index_entries": index_count,
            }