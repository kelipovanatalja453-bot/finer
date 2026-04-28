# SPEC: P1 情绪融合模块 (SentimentFusionEnricher)

> **状态**: ✅ 已完成
> **版本**: 1.0
> **创建日期**: 2026-04-23
> **完成日期**: 2026-04-23

## 1. 目标

整合 finance-skills 的 `finance-sentiment` 技能，为 Trade Action 提供跨源情绪数据，增强 `direction` 判断的可靠性。

## 2. 背景

### 2.1 问题陈述

当前 Trade Action 提取的 `direction` (bullish/bearish/neutral) 完全依赖 LLM 内部判断，缺乏外部情绪数据验证。这导致：

1. 无法检测市场情绪与观点的背离
2. 无法识别极端情绪的反向信号
3. 缺乏多源情绪的交叉验证

### 2.2 解决方案

实现 `SentimentFusionEnricher`，从 Reddit、Twitter、News 等多源聚合情绪数据，用于：

1. 校准 `direction` 置信度
2. 检测反向信号 (contrarian signal)
3. 标记情绪-观点背离

## 3. 技术设计

### 3.1 数据模型

```python
# src/finer/schemas/enriched_event.py (扩展)

class SentimentSnapshot(BaseModel):
    """情绪数据快照"""
    ticker: str
    
    # 各源情绪分数 (-1 到 1)
    reddit_sentiment: Optional[float] = None
    twitter_sentiment: Optional[float] = None
    news_sentiment: Optional[float] = None
    polymarket_probability: Optional[float] = None
    
    # 聚合指标
    aggregated_score: float = 0.0  # 加权聚合分数
    sentiment_velocity: float = 0.0  # 情绪变化速率
    
    # 信号标记
    contrarian_signal: bool = False  # 是否出现反向信号
    extreme_sentiment: bool = False  # 是否处于极端情绪
    
    # 元数据
    sources: List[str] = []
    timestamp: datetime
    data_quality: str = "complete" | "partial" | "unavailable"
```

### 3.2 核心组件

```python
# src/finer/enrichment/sentiment_fusion.py

class SentimentFusionEnricher:
    """情绪融合增强器"""
    
    async def fetch_sentiment(self, ticker: str) -> SentimentSnapshot:
        """获取单只股票的跨源情绪"""
        
    async def enrich_event(
        self, 
        event: EventWithActions
    ) -> Tuple[EnrichedEventWithActions, List[str]]:
        """增强单个事件"""
        
    def calculate_direction_adjustment(
        self,
        llm_direction: str,
        sentiment: SentimentSnapshot
    ) -> DirectionAdjustment:
        """计算方向调整建议"""
```

### 3.3 聚合算法

```python
# 源权重配置
SOURCE_WEIGHTS = {
    "reddit": 0.25,
    "twitter": 0.25,
    "news": 0.35,
    "polymarket": 0.15
}

def aggregate_sentiment(data: dict) -> float:
    """
    加权聚合多源情绪
    
    输入: {"reddit": 0.3, "twitter": 0.5, "news": 0.2}
    输出: 0.305 (加权平均)
    """
    
def detect_contrarian(sentiment: float, velocity: float) -> bool:
    """
    检测反向信号
    
    规则:
    - 极度乐观 (>0.7) + 快速上升 (>0.3) → 可能见顶
    - 极度悲观 (<-0.7) + 快速下跌 (<-0.3) → 可能见底
    """
```

### 3.4 方向调整逻辑

| LLM 方向 | 情绪状态 | 调整动作 |
|----------|----------|----------|
| bullish | 极度乐观 (>0.7) | 降低置信度 -0.2 |
| bullish | 极度悲观 (<-0.7) | 提高置信度 +0.1 (逆向) |
| bearish | 极度悲观 (<-0.7) | 降低置信度 -0.2 |
| bearish | 极度乐观 (>0.7) | 提高置信度 +0.1 (逆向) |
| neutral | 任何极端 | 标记需人工审核 |

## 4. 集成点

### 4.1 与 P0 集成

```python
# src/finer/enrichment/market_context.py (修改)

class MarketContextEnricher:
    def __init__(self, ...):
        self.sentiment_enricher = SentimentFusionEnricher()  # 新增
        
    async def enrich_event(self, event):
        # 并行获取市场数据和情绪数据
        market_task = self.fetch_market_data(event.ticker)
        sentiment_task = self.sentiment_enricher.fetch_sentiment(event.ticker)
        
        market_data, sentiment = await asyncio.gather(market_task, sentiment_task)
```

### 4.2 API 扩展

```python
# src/finer/api/routes/enrichment.py (新增)

@router.post("/enrich/sentiment")
async def enrich_sentiment(request: SentimentRequest):
    """单独的情绪增强 API"""
    
@router.post("/enrich/full")
async def enrich_full(request: FullEnrichRequest):
    """完整增强 (市场 + 情绪)"""
```

## 5. 配置

```yaml
# configs/finance_skills.yaml (扩展)

features:
  sentiment: true  # 启用情绪融合
  
sentiment:
  sources:
    - reddit
    - twitter
    - news
  lookback_hours: 72
  contrarian_threshold: 0.7
  velocity_threshold: 0.3
```

## 6. 验收标准

- [ ] SentimentFusionEnricher 实现完成
- [ ] SentimentSnapshot 模型定义
- [ ] 集成到 EnrichedActionExtractor
- [ ] 方向调整逻辑正确
- [ ] 反向信号检测有效
- [ ] 验证脚本通过

## 7. 风险与降级

| 风险 | 降级策略 |
|------|----------|
| finance-sentiment API 不可用 | 返回空 SentimentSnapshot，标记 data_quality="unavailable" |
| 部分源数据缺失 | 使用可用源聚合，标记 data_quality="partial" |
| API 延迟过高 | 使用缓存，超时返回缓存数据 |

## 8. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/finer/enrichment/sentiment_fusion.py` | 新建 | 核心实现 |
| `src/finer/schemas/enriched_event.py` | 修改 | 扩展 SentimentSnapshot |
| `src/finer/enrichment/market_context.py` | 修改 | 集成情绪融合 |
| `configs/finance_skills.yaml` | 修改 | 添加 sentiment 配置 |
| `examples/sentiment_example.py` | 新建 | 使用示例 |
