# Finer OS ML/AI 路线图

> 最后更新: 2026-04-29

## 执行摘要

Finer OS 是一个 AI-native 投研自动化流水线，核心目标是将 KOL 社交媒体内容转化为结构化、可回测、可审计的投资事件。本文档定义了 ML/AI 能力的发展路线图。

**当前状态:**
- ✅ F0-F8 流水线架构（canonical，详见 AGENTS.md / docs/ARCHITECTURE.md）
- ✅ TradeAction 抽取 (LLM)
- ✅ 市场数据融合 (Finance-Skills)
- ✅ DPO 训练数据导出
- ✅ 数据血缘追踪
- ✅ 回测引擎实现 (`backtest/engine.py`)
- ✅ KOL 评分模型 (`ml/kol_scorer.py`)
- ✅ 本地情绪分析模块 (`ml/sentiment/`)
- ❌ ML 模型训练流程（数据量不足，contract-only）

---

## P0: 核心能力补全 (立即执行)

### 1. 回测引擎 (`src/finer/backtest/`)

**问题:** `BacktestResult` schema 存在，但无实际计算逻辑

**方案:**
```python
class BacktestEngine:
    def run_backtest(actions, price_data, config) -> BacktestResult
    def simulate_portfolio(actions, initial_capital) -> PortfolioHistory
    def calculate_metrics(returns) -> Dict[str, float]
```

**实现状态:** ✅ 已完成
- `engine.py`: 完整的 Portfolio 模拟器
- 支持做多/做空
- 可配置滑点、手续费、借券成本
- 自动计算 Sharpe、Sortino、Calmar、Max Drawdown
- KOL 归因分析

**预期收益:**
- 验证 KOL 观点质量
- 为评分模型提供数据支撑
- 支持 Portfolio 级别回测

**实现复杂度:** 中 (已完成)

---

### 2. KOL 评分模型 (`src/finer/ml/kol_scorer.py`)

**问题:** `KOLProfile.rating` 只是单值，无多维度评分体系

**方案:**
```python
class KOLScorer:
    def compute_scores(kol_profile, backtest_results) -> DimensionScores
    def compute_overall(dimension_scores) -> float
    def explain(kol_id) -> Dict[str, Any]  # 可解释性
```

**实现状态:** ✅ 已完成
- 五维度评分: Accuracy, Timeliness, Return, Consistency, Depth
- 可配置权重 (YAML)
- 时间衰减机制
- 内置可解释性

**评分维度说明:**

| 维度 | 权重 | 衡量指标 |
|------|------|----------|
| Accuracy | 30% | 方向准确率、目标价命中 |
| Timeliness | 15% | 提前量、信号时效性 |
| Return | 30% | 风险调整收益、Win Rate |
| Consistency | 15% | 收益波动率、连续性 |
| Depth | 10% | 分析深度、置信度 |

**预期收益:**
- KOL 量化和对比
- 支持 KOL 推荐
- 为 RLHF 提供反馈信号

**实现复杂度:** 中 (已完成)

---

### 3. 情绪分析模块 (`src/finer/ml/sentiment/`)

**问题:** 情绪分析完全依赖外部服务，无本地 fallback

**方案:**
```python
class SentimentAnalyzer:
    def analyze(text, context) -> SentimentResult
    def batch_analyze(texts) -> List[SentimentResult]
```

**实现状态:** ✅ 已完成
- 双模式: Rule-based (主要) + ML-based (可选)
- 支持中英文金融关键词
- 强度修饰词和否定词处理
- FinBERT 集成 (可选)

**预期收益:**
- 降低外部依赖
- 支持离线处理
- 更快的响应速度

**实现复杂度:** 低 (已完成)

---

## P1: ML/AI 增强 (规划并执行)

### 1. TradeAction 抽取模型优化

**问题:** 当前使用通用 LLM，无领域优化

**方案:**
- Few-shot Learning: 构建高质量示例库
- Active Learning: 从 RLHF 反馈中迭代学习
- DPO 微调: 利用已实现的 DPO pipeline

**技术路线:**

| 阶段 | 方法 | 数据需求 | 预期提升 |
|------|------|----------|----------|
| Phase 1 | Few-shot + Prompt Engineering | 50 高质量样本 | 准确率 +10% |
| Phase 2 | DPO 微调 Qwen-14B | 500+ RLHF 反馈 | 准确率 +20% |
| Phase 3 | 领域预训练 | 10000+ 标注数据 | 准确率 +30% |

**实现复杂度:** 高

**关键指标:**
- 抽取准确率 (F1)
- 字段覆盖率
- 幻觉率

---

### 2. 实体链接增强

**问题:** 当前使用规则匹配，召回率低

**方案:**
- NER 模型: 中文金融领域 NER
- 知识图谱: 实体消歧和链接
- 上下文感知: 根据上下文判断实体类型

**技术选择:**
- 中文 NER: `uer/roberta-base-finetuned-jd-binary-chinese`
- 实体消歧: 自定义规则 + 向量相似度
- 知识图谱: Neo4j 或本地图存储

**实现复杂度:** 中高

---

### 3. 主动学习 Pipeline

**问题:** RLHF 反馈被动收集，效率低

**方案:**
- 不确定性采样: 选择模型不确定的样本
- 多样性采样: 覆盖不同场景
- 标注效率: 主动推送待标注样本

**实现:**
```python
class ActiveLearner:
    def select_samples(unlabeled_pool, model) -> List[Sample]
    def compute_uncertainty(prediction) -> float
    def compute_diversity(sample, labeled_pool) -> float
```

**实现复杂度:** 中

---

## P2: 高级能力 (规划)

### 1. 多模态理解

**能力:**
- 图表 OCR + 趋势识别
- 视频/音频内容理解
- 跨模态信息融合

**技术选择:**
- OCR: Qwen-VL-Plus
- 视频理解: Whisper + Qwen-VL
- 跨模态: CLIP 或相似模型

**实现复杂度:** 高

---

### 2. 实时数据流

**能力:**
- WebSocket 推送
- 流式处理
- 实时信号生成

**技术选择:**
- 后端: FastAPI WebSocket
- 流处理: Kafka 或 Redis Streams
- 存储: TimescaleDB 或 ClickHouse

**实现复杂度:** 高

---

### 3. 推荐系统

**能力:**
- KOL 推荐: 基于历史表现和用户偏好
- 观点推荐: 相关观点聚合
- Portfolio 建议: 基于用户风险偏好

**技术选择:**
- 协同过滤: 用户-KOL 交互矩阵
- 内容推荐: 观点相似度
- 混合推荐: 协同 + 内容 + 知识图谱

**实现复杂度:** 中高

---

## 架构设计原则

### 1. 模块化与解耦

```
ml/
├── sentiment/        # 情绪分析 (独立模块)
├── extraction/       # 抽取模型 (独立模块)
├── kol_scorer.py     # KOL 评分
├── dpo_trainer.py    # DPO 训练
└── model_config.py   # 模型配置中心
```

### 2. 配置驱动

所有 ML 参数通过 `configs/ml_models.yaml` 配置:
- 模型选择和版本
- 超参数
- 权重配置
- A/B 测试参数

### 3. 可观测性

每个 ML 模块提供:
- 输入输出日志
- 性能指标 (延迟、吞吐)
- 模型指标 (准确率、F1)
- 成本追踪 (API 调用次数)

### 4. 降级与容错

```python
# 模型调用链
primary_model -> fallback_model -> rule_based -> default
```

---

## 评估指标体系

### TradeAction 抽取

| 指标 | 定义 | 目标 |
|------|------|------|
| Direction Accuracy | 方向预测正确率 | > 80% |
| Ticker Recall | ticker 召回率 | > 90% |
| Field Coverage | 必填字段覆盖率 | > 95% |
| Hallucination Rate | 幻觉率 | < 5% |

### KOL 评分

| 指标 | 定义 | 目标 |
|------|------|------|
| Score Stability | 相同输入分数方差 | < 0.1 |
| Ranking Consistency | 与历史排名一致性 | > 0.8 |
| Prediction Correlation | 分数与实际收益相关性 | > 0.3 |

### 情绪分析

| 指标 | 定义 | 目标 |
|------|------|------|
| Classification Accuracy | 分类准确率 | > 75% |
| Score Correlation | 与价格变化相关性 | > 0.2 |
| Latency P99 | 99% 请求延迟 | < 100ms |

---

## 实施路径

### Phase 1: 基础建设 (已完成)

- [x] 回测引擎核心实现
- [x] KOL 评分模型
- [x] 情绪分析模块
- [x] ML 模型配置系统

### Phase 2: 数据积累 (进行中)

- [ ] 收集 RLHF 反馈数据
- [ ] 构建 Few-shot 示例库
- [ ] 标注验证数据集

### Phase 3: 模型优化 (Q2 2026)

- [ ] Few-shot 提示优化
- [ ] DPO 微调实验
- [ ] 模型评估和对比

### Phase 4: 高级功能 (Q3 2026)

- [ ] 多模态理解
- [ ] 实时数据流
- [ ] 推荐系统

---

## 风险与缓解

### 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 幻觉 | 抽取错误 | 强制 JSON Schema + 验证规则 |
| 数据不足 | 模型效果差 | 数据增强 + 迁移学习 |
| 过拟合 | 泛化差 | 交叉验证 + 正则化 |
| API 成本 | 预算超支 | 本地模型 + 缓存 + 批处理 |

### 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 评分偏见 | 用户不满 | 透明度 + 可解释性 |
| 模型漂移 | 效果下降 | 定期重新训练 + 监控 |
| 合规问题 | 法律风险 | 审计日志 + 人工审核 |

---

## 总结

本文档定义了 Finer OS 的 ML/AI 发展路线图:

1. **P0 (已完成):** 回测引擎、KOL 评分、情绪分析 — 核心能力补全
2. **P1 (规划中):** 抽取模型优化、实体链接增强、主动学习 — ML 增强
3. **P2 (规划中):** 多模态理解、实时数据流、推荐系统 — 高级能力

关键成功因素:
- 数据质量 > 模型复杂度
- 可解释性 > 准确率 (在金融场景)
- 迭代速度 > 完美设计
