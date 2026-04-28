# Finer OS 架构文档

> **版本**: 1.3.0  
> **最后更新**: 2026-04-27  
> **状态**: 持续演进  
> **审阅状态**: 已根据当前代码、`docs/architecture-alignment-plan.md` 与 `docs/agent-execution-plan.md` 更新

---

## 目录

1. [项目愿景](#1-项目愿景)
2. [系统架构总览](#2-系统架构总览)
3. [分层架构详解](#3-分层架构详解)
4. [数据模型](#4-数据模型)
5. [API 参考](#5-api-参考)
6. [前端架构](#6-前端架构)
7. [外部集成](#7-外部集成)
8. [配置管理](#8-配置管理)
9. [已实现功能清单](#9-已实现功能清单)
10. [规划中的功能](#10-规划中的功能)
11. [部署与运维](#11-部署与运维)
12. [开发规范](#12-开发规范)
13. [数据治理](#13-数据治理)
14. [非功能性需求](#14-非功能性需求)
15. [已知问题与改进计划](#15-已知问题与改进计划)

---

## 1. 项目愿景

### 1.0 配套规划文档

| 文档 | 用途 |
|---|---|
| `docs/architecture-alignment-plan.md` | 架构对齐与阶段拆解 |
| `docs/agent-execution-plan.md` | 多 Agent 并行任务、文件合约与验收流程 |

### 1.1 核心目标

**将财经 KOL 的所有发布内容按时间线整理，并进行回测，验证如果对这个 KOL 进行跟随交易的收益率和市场表现。**

### 1.2 三个不可约子目标

| # | 子目标 | 本质问题 |
|---|---|---|
| G1 | **KOL 内容采集与归一化** | 任意平台的 KOL 内容 → 统一结构化记录 |
| G2 | **按时间线聚合** | 以 KOL 为中心轴，以时间为排序键，构建完整的"观点编年史" |
| G3 | **跟随交易回测** | 模拟一个"完全跟单者"的 Portfolio 随时间的收益曲线，与基准对比 |

### 1.3 项目定位

**AI-native 投研自动化流水线**：将 KOL 社交媒体内容转化为结构化、可回测、可审计的投资事件。

---

## 2. 系统架构总览

### 2.1 技术栈

| 层级 | 技术选型 |
|---|---|
| **后端** | Python 3.11+ / FastAPI / Pydantic V2 |
| **前端** | TypeScript / Next.js 16 / React 19 / TailwindCSS 4 |
| **LLM** | GLM-5.1 (SVIPS) / Qwen-Plus (DashScope) / Qwen-VL-Plus |
| **数据存储** | 文件系统 (JSON/Markdown) + SQLite 索引层 |
| **外部服务** | Finance-Skills / Feishu API / NotebookLM |

### 2.2 目标流水线架构

当前 Finer 的长期目标不是“从文本直接抽取交易动作”，而是建立一条可审计、可复核、可回测、可训练的 KOL 观点处理链。

目标链路:

```text
S0 Raw Source
  -> V0 Content Standardization
  -> V0.5 Quality + Temporal + Entity Anchoring
  -> V1 NormalizedInvestmentIntent
  -> V2 Policy Mapping
  -> V3 ExecutableTradeAction
  -> V4 Timeline + Viewpoint State
  -> V5 Backtest + KOL Evaluation
  -> V6 Training Data + Model Improvement
```

与现有 L0-L8 的关系:

| 目标层 | 对应现有层 | 说明 |
|---|---|---|
| S0 Raw Source | L0 | 原始文件、飞书消息、图片、音频、PDF、链接文档 |
| V0 Content Standardization | L2/L3 前置 | 新增统一内容 envelope/block |
| V0.5 Quality/Time/Entity | L1/L3/L4 | 质量卡、时间锚、实体锚定 |
| V1 Intent | L5 前置 | 新增投资意图层，不直接进入 TradeAction |
| V2 Policy Mapping | 新增 | 全局 policy + 风格 policy + 风险偏好 + KOL 个体修正 |
| V3 TradeAction | L5/L6 | 现有 TradeAction 作为可执行/可回测动作 |
| V4 Timeline State | L7 | 观点时间线 + 观点状态机 |
| V5 Backtest/Evaluation | L8 | 回测、归因、KOL 评分 |
| V6 Training Loop | ML/RLHF/DPO | 从标注和回测结果生成训练数据 |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Finer OS 数据流水线                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  L0 接入层     V0 标准化     V0.5 锚定     V1 意图层                        │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                     │
│  │ 飞书    │   │ Envelope│   │ 时间锚  │   │ direction│                    │
│  │ B站     │ → │ Block   │ → │ 实体锚  │ → │ action-  │ →                  │
│  │ 微信    │   │ Quality │   │ 质量门控 │   │ ability  │                     │
│  │ 手动    │   │ Evidence│   │         │   │ conviction│                    │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                     │
│                                                     │                       │
│                                                     ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    V2 Policy Mapping                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │ Global Base │  │ Style Policy│  │ KOL Persona │                  │   │
│  │  │ Policy      │  │ Risk Policy │  │ Correction  │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                     │                       │
│                                                     ▼                       │
│  V3 动作层     L6 复核层     V4 时间线     V5 回测层                        │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐                     │
│  │ Trade   │   │ RLHF    │   │ KOL     │   │ Portfolio│                     │
│  │ Action  │ → │ 反馈    │ → │ 观点状态 │ → │ 跟单模拟 │                     │
│  │ Mapping │   │ DPO导出 │   │ 分歧图谱 │   │ KOL评分  │                     │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 当前代码基线

当前代码已具备多个模块，但主链路仍处于“直接 L5 TradeAction 抽取”的阶段。必须区分“模块存在”和“端到端闭环”。

| 能力 | 当前状态 | 主要文件 | 对齐判断 |
|---|---|---|---|
| 多源接入 | 部分端到端可用 | `ingestion/`, `api/routes/files.py` | 可作为 S0/L0 基础 |
| OCR/ASR/文档转换 | 局部逻辑完成 | `parsing/`, `services/perception.py` | 需升级为 V0 block 输出 |
| 话题/实体/情绪 | 局部逻辑完成 | `enrichment/`, `ml/sentiment/` | 需纳入 V0.5 锚定和质量卡 |
| TradeAction 抽取 | 局部逻辑完成 | `extraction/trade_action_extractor.py` | 需前置 V1 Intent |
| RLHF/DPO | 局部逻辑完成 | `api/routes/rlhf.py`, `ml/dpo_trainer.py` | 需针对 Intent 层补标签 |
| 时间线 | 逻辑完成但依赖上游质量 | `timeline/`, `api/routes/opinions.py` | 需引入观点状态机 |
| 回测引擎 | 逻辑完成，pipeline 未闭环 | `backtest/`, `api/routes/backtest.py` | 需接入 effective_trade_time |
| KOL 评分 | 逻辑完成，数据未完全打通 | `ml/kol_scorer.py`, `services/kol_rating_engine.py` | 需接真实回测和 persona |

### 2.4 当前首要任务

项目当前首要任务是修正架构契约，而不是直接训练模型。下一阶段以文档、schema、验收标准为中心推进:

1. 冻结 V0/V1 schema。
2. 明确 TradeAction 不再承担全部语义，而是 V3 可执行动作。
3. 将图片、聊天记录、飞书文档、PDF、音频转录统一进入 ContentEnvelope/ContentBlock。
4. 建立质量卡、时间锚、实体锚、证据回溯。
5. 再把 policy 和 KOL persona 接入 intent -> action 映射。

### 2.5 目录结构

```
finer/
├── src/finer/                    # 后端核心代码
│   ├── api/                      # API 层
│   │   ├── routes/               # 路由模块 (16 个)
│   │   │   ├── files.py          # 文件管理
│   │   │   ├── review.py         # 复核流程
│   │   │   ├── rlhf.py           # RLHF 反馈
│   │   │   ├── extraction.py     # 事件抽取
│   │   │   ├── aggregation.py    # L4 聚合 (新增)
│   │   │   ├── opinions.py       # 观点时间线
│   │   │   ├── enrichment.py     # L1 富化
│   │   │   ├── integrations.py   # 外部集成
│   │   │   ├── wechat.py         # 微信接入
│   │   │   ├── bilibili.py       # B站接入
│   │   │   ├── streams.py        # 数据流
│   │   │   ├── sources.py        # 数据源
│   │   │   ├── stats.py          # 统计
│   │   │   ├── system.py         # 系统状态
│   │   │   ├── asset_builder.py  # 资源构建器
│   │   │   └── files_utils.py    # 文件工具
│   │   └── server.py             # FastAPI 应用入口
│   │
│   ├── ingestion/                # L0 接入层
│   │   ├── feishu_poller.py      # 飞书消息轮询
│   │   ├── wechat_adapter.py     # 微信公众号适配器
│   │   ├── wechat_exporter_client.py  # 微信导出客户端 (新增)
│   │   ├── bilibili_adapter.py   # B站视频适配器
│   │   ├── nlm_sync.py           # NotebookLM 同步
│   │   ├── orchestrator.py       # 接入编排器
│   │   ├── classifier.py         # 文件分类器
│   │   ├── receipt.py            # 消息回执
│   │   └── vision_utils.py       # 视觉工具
│   │
│   ├── enrichment/               # L1 富化层
│   │   ├── __init__.py           # 话题拆分、实体抽取
│   │   ├── market_context.py     # 市场数据融合 (P0)
│   │   └── sentiment_fusion.py   # 情绪融合 (P1)
│   │
│   ├── parsing/                  # L3 解析层
│   │   ├── vision_extractor.py   # 视觉内容提取
│   │   ├── audio_extractor.py    # 音频转录
│   │   ├── sentiment_enricher.py # 情绪标注
│   │   ├── slang.py              # 黑话翻译
│   │   ├── slang_generator.py    # 黑话生成
│   │   └── context_summarizer.py # 上下文摘要
│   │
│   ├── aggregation/              # L4 聚合层 (新增)
│   │   └── __init__.py           # EntityLinker, ContextAggregator
│   │
│   ├── extraction/               # L5 抽取层
│   │   ├── trade_action_extractor.py  # TradeAction 抽取
│   │   ├── enriched_extractor.py # 增强版抽取器
│   │   ├── extractor.py          # 基础抽取器
│   │   └── action_interpreter.py # 操作解释器
│   │
│   ├── ml/                       # 机器学习模块
│   │   ├── dpo_trainer.py        # DPO 训练
│   │   └── export_dpo.py         # DPO 数据导出
│   │
│   ├── services/                 # 公共服务
│   │   ├── finance_skills_client.py  # Finance-Skills 客户端
│   │   ├── kol_rating_engine.py  # KOL 评级引擎
│   │   ├── summary_generator.py  # 摘要生成
│   │   ├── perception.py         # 感知服务
│   │   └── converter.py          # 转换器
│   │
│   ├── llm/                      # LLM 统一客户端 (新增)
│   │   ├── __init__.py           # 导出 LLMClient
│   │   └── client.py             # 统一客户端实现
│   │
│   ├── schemas/                  # 数据模型
│   │   ├── trade_action.py       # TradeAction 核心模型 (750 行)
│   │   ├── content.py            # ContentRecord
│   │   ├── segment.py            # SegmentRecord
│   │   ├── event.py              # EventWithActions
│   │   ├── enriched_event.py     # EnrichedEventWithActions
│   │   ├── contract.py           # 前端契约 (AssetFile)
│   │   ├── wechat.py             # 微信相关模型
│   │   └── __init__.py           # 导出
│   │
│   ├── config.py                 # 配置加载器
│   ├── paths.py                  # 路径常量
│   ├── entity_registry.py        # 统一实体注册表 (新增)
│   ├── model_config.py           # 模型注册表
│   ├── manifests.py              # 内容清单
│   ├── classification_memory.py  # 分类记忆
│   ├── pipeline.py               # 流水线入口
│   └── cli.py                    # 命令行工具
│
├── src/finer_dashboard/          # 前端 (Next.js)
│   └── src/
│       ├── app/                  # 页面路由
│       │   ├── page.tsx          # 主工作台
│       │   ├── layout.tsx        # 布局
│       │   ├── globals.css       # 全局样式
│       │   └── demo/             # 演示页面
│       │       └── kol-rating/   # KOL 评级演示
│       ├── components/           # 组件库
│       │   ├── layout/           # 布局组件 (6 个)
│       │   ├── studio/           # 工作台组件
│       │   ├── rlhf-review-panel/# RLHF 复核面板 (9 个)
│       │   ├── kol-rating-card/  # KOL 评级卡片 (7 个)
│       │   ├── opinion-timeline/ # 观点时间线 (5 个)
│       │   └── data-source-config/ # 数据源配置 (6 个)
│       └── lib/
│           ├── contracts.ts      # 前端类型定义
│           └── utils.ts          # 工具函数
│
├── configs/                      # 配置文件
│   ├── feishu.yaml               # 飞书配置
│   ├── feishu.yaml.example       # 飞书配置示例
│   ├── finance_skills.yaml       # Finance-Skills 配置
│   └── creators/                 # 创作者配置
│       └── trader_ji.yaml        # trader韭 配置
│
├── data/                         # 数据目录
│   ├── raw/                      # 原始文件 (L0)
│   ├── L0_ingest/                # 接入产物
│   ├── L1_enrichment/            # 富化产物
│   ├── L1_inbox/                 # 待处理队列
│   ├── L2_standardized/          # 标准化产物
│   ├── L3_aligned/               # 解析产物
│   ├── L4_parsed/                # 聚合产物
│   ├── L5_candidate/             # 候选事件
│   ├── L6_annotated/             # 标注数据
│   ├── L7_model_results/         # 模型结果
│   ├── L8_metrics/               # 回测指标
│   ├── processed/                # 处理后数据
│   │   ├── manifests/            # 内容清单
│   │   ├── documents/            # 文档
│   │   └── transcripts/          # 转录文本
│   ├── rlhf/                     # RLHF 反馈数据
│   ├── cache/                    # 应用缓存
│   └── inbox/                    # 下载暂存区
│
├── docs/                         # 文档
├── tests/                        # 测试
├── implementation_plan.md        # 实施规划
└── CLAUDE.md                     # 开发规范
```

---

## 3. 分层架构详解

### 3.1 L0 接入层 (Intake)

**职责**：多源数据接入，统一入库

#### 3.1.1 已实现的数据源

| 数据源 | 模块 | 状态 | 功能 |
|---|---|---|---|
| **飞书群聊** | `feishu_poller.py` | ✅ 完成 | 消息轮询、文件下载、图片提取 |
| **B站视频** | `bilibili_adapter.py` | ✅ 完成 | 视频信息获取、字幕提取、转录 |
| **微信公众号** | `wechat_adapter.py` + `wechat_exporter_client.py` | ⚠️ 部分 | 登录流程、文章获取 |
| **NotebookLM** | `nlm_sync.py` | ✅ 完成 | 笔记同步、文件上传 |
| **手动上传** | `files.py` | ✅ 完成 | 文件导入、分类 |

#### 3.1.2 飞书接入详情

```python
# 核心流程 (feishu_poller.py)
class FeishuPoller:
    def poll_chat(chat_id, since) -> List[Message]
    def download_attachment(message_id, file_key, type)
    def process_image(image_path) -> str  # 视觉解析

# 配置 (configs/feishu.yaml)
watched_chats:
  - chat_id: "oc_xxx"
    name: "群名称"
    notebook_id: "xxx"    # NotebookLM 同步
    default_creator: "creator_id"
```

#### 3.1.3 微信公众号接入 (新增)

```python
# wechat_exporter_client.py (678 行)
class WeChatExporterClient:
    """调用 wechat-article-exporter 服务"""
    
    async def get_qrcode() -> bytes           # 获取登录二维码
    async def wait_for_scan() -> ScanResult   # 等待扫码
    async def search_account(keyword)         # 搜索公众号
    async def get_articles(fakeid)            # 获取文章列表
    async def export_article(url)             # 导出文章内容
    async def get_all_articles(fakeid)        # 获取全部文章
```

**部署要求**：需要单独部署 `wechat-article-exporter` 服务 (Docker)

---

### 3.2 L1 富化层 (Enrichment)

**职责**：话题拆分、实体抽取、市场数据融合、情绪融合

#### 3.2.1 核心组件

```python
# enrichment/__init__.py
class TopicSplitter:
    """将长聊天记录按话题分割"""
    def split(content: str) -> List[Topic]
    
class EntityExtractor:
    """从内容中提取 tickers、公司、人物、事件"""
    def extract(content: str) -> EntityExtraction

# enrichment/market_context.py (P0)
class MarketContextEnricher:
    """市场数据融合 - 当前价格、52周范围、成交量"""
    async def enrich(events: List[Event]) -> EnrichmentResult

# enrichment/sentiment_fusion.py (P1)  
class SentimentFusionEnricher:
    """多源情绪聚合 - 新闻情绪、社交媒体情绪"""
    async def fuse(events: List[Event]) -> FusionResult
```

#### 3.2.2 数据流

```
原始内容 → TopicSplitter → EntityExtractor → MarketContextEnricher → SentimentFusionEnricher
                ↓                ↓                    ↓                      ↓
            话题列表          实体列表            市场数据               情绪评分
```

---

### 3.3 L2 标准化层 (Library)

**职责**：内容标准化、归档、索引构建

#### 3.3.1 核心功能

- 内容格式统一化
- 元数据标准化
- 索引构建与维护
- 文件命名规范化 (新增语义化标题)

#### 3.3.2 文件命名改进 (新增)

```python
# files_utils.py
def generate_semantic_title(text: str) -> str:
    """LLM 生成 10-15 字语义标题 (带缓存)"""
    
def classify_file_type(extension: str) -> str:
    """返回友好类型：聊天记录/图片/PDF/文档"""
    
def extract_source_name(file_name: str) -> str:
    """提取来源名称"""
    
def build_display_info(...) -> DisplayInfo:
    """组合显示信息"""
```

---

### 3.4 L3 解析层 (Parsing)

**职责**：OCR/ASR、情绪标注、黑话翻译

#### 3.4.1 核心组件

| 模块 | 功能 | 模型 |
|---|---|---|
| `vision_extractor.py` | 图片 OCR、图表分析 | Qwen-VL-Plus |
| `audio_extractor.py` | 音频转录 | Whisper API |
| `sentiment_enricher.py` | 情绪标注 | GLM-5.1 |
| `slang.py` | 黑话翻译 | 规则 + LLM |
| `context_summarizer.py` | 上下文摘要 | GLM-5.1 |

#### 3.4.2 ASR 配置 (2026-04-27 新增)

**ASR 后端选择**：

| 后端 | 适用场景 | 配置 |
|---|---|---|
| `funasr` (本地) | M2 Mac / 无 CUDA 环境 | `ASR_BACKEND=funasr` |
| `mimo_api` (远程) | 有 MiMo API key | `ASR_BACKEND=mimo_api` |

**FunASR 本地配置**：
- 模型: `paraformer-zh-streaming` (~220MB)
- 设备: CPU (M2 Mac 使用 Metal/MPS 不支持 CUDA)
- 安装: `pip install funasr torch torchaudio && brew install ffmpeg`

**MiMo-V2.5-ASR 说明**：
- 无法在 M2 Mac 本地运行（需要 CUDA >= 12.0）
- 模型约 7-10B 参数，需要 14-20GB VRAM
- 可通过 MiMo Open Platform API 远程调用

**新增文件**：
- `src/finer/parsing/funasr_client.py` - FunASR 本地客户端
- `src/finer/parsing/mimo_asr_client.py` - MiMo API 客户端
- `src/finer/config.py` - 新增 `ASRConfig`, `FunASRConfig`

---

### 3.5 L4 聚合层 (Aggregation) - 新增

**职责**：实体消歧、上下文聚合、市场预注入

> **⚠️ 架构审阅警告**：L4 层当前为内存态，进程重启后所有聚合数据丢失。需要引入持久化存储（SQLite/Redis）。

#### 3.5.1 核心组件

```python
# aggregation/__init__.py (448 行)

class EntityLinker:
    """实体消歧与链接"""
    
    def resolve(text: str) -> List[EntityReference]:
        """从文本中识别并消歧实体"""
        # "腾讯" / "TCEHY" / "0700.HK" → "0700.HK"
        
class ContextAggregator:
    """跨内容上下文聚合"""
    
    def add_context(context: AggregatedContext): 
        """添加上下文到聚合器"""
        
    def build_entity_timeline(entity: str) -> List[Dict]:
        """构建某实体的观点时间线"""

class MarketPreInjector:
    """市场数据预注入"""
    
    async def inject(context: AggregatedContext) -> AggregatedContext:
        """为上下文注入市场数据"""

class L4AggregationLayer:
    """L4 聚合层主类"""
    
    def process_text(text, content_id, ...) -> AggregatedContext
    async def process_with_market_data(...) -> AggregatedContext
    def get_entity_timeline(entity) -> List[Dict]
```

#### 3.5.2 API 端点 (新增)

```
GET  /api/aggregation/entities/{entity}/timeline  # 实体观点时间线
GET  /api/aggregation/entities/search?q=...       # 搜索实体
POST /api/aggregation/process                     # 处理文本
POST /api/aggregation/process-with-market         # 注入市场数据
GET  /api/aggregation/entity-index                # 实体索引
GET  /api/aggregation/resolve/{text}              # 解析实体
```

---

### 3.6 L5 抽取层 (Extraction)

**职责**：从解析后的内容中提取结构化 TradeAction

> **⚠️ 架构审阅警告**：`TradeAction.source.creator_id` 几乎未被填充，导致 KOL 归属链断裂。需在 Phase 1 通过 KOL Profile 管理解决。

#### 3.6.1 核心流程

```
解析文本 → TradeActionExtractor → TradeActionBatch
                    ↓
            置信度判断:
            - >= 0.8: 直接输出
            - 0.5-0.8: Finance-Skills 验证
            - < 0.5: 标记人工复核
```

#### 3.6.2 TradeAction 结构

```python
class TradeAction(BaseModel):
    # 核心字段
    trade_action_id: str
    timestamp: datetime
    source: SourceInfo          # 来源信息
    target: TargetInfo          # 标的信息
    direction: TradeDirection   # bullish/bearish/neutral
    action_chain: List[ActionStep]  # 操作序列
    
    # 富化字段
    enrichment: MarketEnrichment    # 市场数据
    confidence: float
    
    # 验证字段
    validation_status: ValidationStatus
    backtest_result: BacktestResult
    
    # 学习字段
    rlhf_feedback: RLHFFeedback
```

---

### 3.7 L6 复核层 (Review)

**职责**：人工审核、RLHF 反馈收集、DPO 数据导出

> **⚠️ 架构审阅警告**：L5→L6 无自动串联，候选事件产生后需手动触发复核。需添加事件驱动通知机制。

#### 3.7.1 复核流程

```
候选事件 → 人工审核 → RLHF 反馈 → DPO 导出
              ↓
         验证/修正/拒绝
```

#### 3.7.2 RLHF 组件

```python
# RLHFReviewPanel.tsx (前端)
- DirectionReview    # 方向复核
- TickerReview       # 标的复核
- ActionChainReview  # 操作链复核
- QuickTags          # 快捷标签
- ReviewNotes        # 复核备注
- OverallRating      # 整体评分
```

---

### 3.8 L7 时间线层 (Timeline) - 局部实现

**职责**：以 KOL 为中心聚合 TradeAction，并在目标架构中升级为观点状态机。

当前已有:

- `src/finer/timeline/engine.py`: 基于 `TradeActionRepository` 构建 KOL 时间线。
- `src/finer/timeline/models.py`: `KOLTimeline`, `TimelineEntry`, `KOLComparison`。
- `src/finer/api/routes/opinions.py`: 前端观点时间线 API，真实数据可用时读取 L5/L6，否则 fallback mock。

当前限制:

- 上游 `TradeAction.source.creator_id` 若未填充，KOL 时间线会断裂。
- 当前按 TradeAction 展示，不维护“观点状态演化”。
- 暂不支持“同一 KOL 对同一标的跨文档观点串联”和“多 KOL 同标的分歧图谱”。

```python
class TimelineEngine:
    def build_kol_timeline(kol_id, start, end) -> KOLTimeline:
        """聚合该 KOL 在时间窗口内的 TradeAction"""
        
    def compare_kols(kol_ids) -> KOLComparison:
        """对比多个 KOL 的标的覆盖和方向重合"""
```

---

### 3.9 L8 回测层 (Backtest) - 逻辑实现，主链路未闭环

**职责**：Portfolio 跟单模拟、收益率计算、KOL 表现评估。

当前已有:

- `src/finer/backtest/engine.py`: Portfolio 模拟、做多/做空、滑点、手续费、借券成本、Sharpe/Sortino/Calmar/Max Drawdown。
- `src/finer/backtest/prices.py`: 价格数据 provider、缓存、mock fallback。
- `src/finer/api/routes/backtest.py`: 回测运行、结果存储、KOL 策略对比。

当前限制:

- `pipeline/orchestrator.py` 的 L8 仍是 placeholder，没有真正调用 BacktestEngine。
- 回测动作依赖 `TradeAction.timestamp`，但当前 timestamp 未严格区分发布时间、文本提及时间、交易生效时间。
- 缺少从 V1 Intent 到 V3 TradeAction 的 policy 映射，因此仓位、持仓期、动作强度暂时只能用默认假设。

```python
class BacktestEngine:
    def run_backtest(actions, price_data, start_date, end_date) -> BacktestResult:
        """根据 TradeAction 和价格数据模拟组合收益"""

class BacktestConfig:
    initial_capital: float
    default_position_pct: float
    max_position_pct: float
    commission_pct: float
    slippage_pct: float
    max_holding_days: int
```

---

## 4. 数据模型

### 4.1 核心模型关系

```
S0 Raw Source
    └→ ContentEnvelope (V0)
         └→ ContentBlock (V0)
              └→ TemporalAnchor / QualityCard / EvidenceSpan (V0.5)
                   └→ NormalizedInvestmentIntent (V1)
                        └→ PolicyMappingResult (V2)
                             └→ TradeAction (V3)
                                  └→ TimelineEntry / ViewpointState (V4)
                                       └→ BacktestResult / KOLScore (V5)
```

现有模型对照:

| 目标模型 | 当前是否存在 | 当前近似模型 | 处理策略 |
|---|---|---|---|
| `ContentEnvelope` | ❌ | `ContentRecord` | 新增，不替换旧模型 |
| `ContentBlock` | ⚠️ 部分 | `SegmentRecord` | 扩展 block 类型、证据、质量、版面字段 |
| `QualityCard` | ❌ | 无 | 新增 |
| `TemporalAnchor` | ❌ | `published_at`, `timestamp` | 新增，拆分四类时间 |
| `NormalizedInvestmentIntent` | ❌ | `EventWithActions`, `TradeAction` | 新增，作为 L5 前置层 |
| `TradeAction` | ✅ | `schemas/trade_action.py` | 保留为 V3 执行动作 |
| `ViewpointState` | ❌ | `KOLTimeline` | 新增观点状态机 |
| `BacktestResult` | ✅ | `backtest/engine.py` | 保留，接入 pipeline |

### 4.2 V0 内容标准化模型

V0 是当前架构中最重要的缺失层。它负责把图片、聊天记录、飞书文档、PDF、音频转录稿等复杂输入统一成可追溯的内容容器和内容块。

```python
class ContentEnvelope(BaseModel):
    envelope_id: str
    source_id: str
    source_type: Literal[
        "feishu_chat",
        "feishu_doc",
        "image",
        "pdf",
        "audio_transcript",
        "video_transcript",
        "wechat_article",
        "manual",
    ]
    kol_id: Optional[str]
    creator_name: Optional[str]
    published_at: Optional[datetime]
    collected_at: datetime
    source_uri: Optional[str]
    raw_path: Optional[str]
    blocks: list[ContentBlock]
    quality_card: QualityCard
    temporal_anchors: list[TemporalAnchor]
    lineage: DataLineage
    metadata: dict

class ContentBlock(BaseModel):
    block_id: str
    envelope_id: str
    block_type: Literal[
        "chat_message",
        "paragraph",
        "image_text",
        "table",
        "chart",
        "audio_segment",
        "video_segment",
        "quote",
        "link_reference",
        "section_title",
    ]
    text: str
    order_index: int
    speaker: Optional[str]
    page_index: Optional[int]
    image_region: Optional[dict]
    start_time_sec: Optional[float]
    end_time_sec: Optional[float]
    parent_block_id: Optional[str]
    thread_id: Optional[str]
    evidence_span: Optional[EvidenceSpan]
    quality_card: QualityCard
    metadata: dict
```

### 4.3 V0.5 质量、时间、证据模型

四类时间必须分开:

| 字段 | 示例 | 用途 |
|---|---|---|
| `published_at` | 2026-04-12 20:00 | 内容发布/采集时间 |
| `mentioned_time` | 上周 | 文本中显式或隐式提到的时间 |
| `resolved_time_range` | 2026-04-05 至 2026-04-11 | 相对时间解析后的绝对范围 |
| `effective_trade_time` | 2026-04-06 开盘后 | 回测采用的交易生效时间 |

```python
class QualityCard(BaseModel):
    completeness: float
    readability: float
    structure: float
    temporal_resolvability: float
    entity_resolvability: float
    evidence_fidelity: float
    gate: Literal["pass", "soft_pass", "review", "reject"]
    warnings: list[str]

class TemporalAnchor(BaseModel):
    anchor_id: str
    text_span: str
    anchor_type: Literal["published", "mentioned", "resolved", "effective_trade"]
    resolved_start: Optional[datetime]
    resolved_end: Optional[datetime]
    confidence: float
    resolution_rule: Optional[str]
    needs_review: bool

class EvidenceSpan(BaseModel):
    source_path: Optional[str]
    block_id: str
    text_start: Optional[int]
    text_end: Optional[int]
    image_region: Optional[dict]
    page_index: Optional[int]
```

### 4.4 V1 投资意图模型

V1 负责把非标准化发言转成标准投资意图，但暂不直接生成交易。

必须拆分四个主轴:

| 轴 | 含义 | 示例 |
|---|---|---|
| `direction` | 看多/看空/中性/风险提示 | “看好腾讯长期护城河” -> bullish |
| `actionability` | 只是观点，还是明确动作 | “看好”低于“加仓” |
| `position_delta_hint` | 仓位变化提示 | 开仓/加仓/减仓/持有/退出 |
| `conviction` | 信念强度 | “坚定抄底”高于“可以看看” |

```python
class NormalizedInvestmentIntent(BaseModel):
    intent_id: str
    envelope_id: str
    block_ids: list[str]
    kol_id: Optional[str]
    target: TargetInfo
    direction: Literal["bullish", "bearish", "neutral", "watchlist", "risk_warning"]
    actionability: Literal["view_only", "implicit_action", "explicit_action"]
    position_delta_hint: Literal["open", "add", "reduce", "hold", "exit", "unknown"]
    conviction: float
    sentiment_features: dict
    time_horizon: Optional[str]
    temporal_anchor_id: Optional[str]
    rationale: str
    evidence_text: str
    ambiguity_notes: list[str]
    confidence: float
    policy_context: Optional[dict]
```

### 4.5 TradeAction 完整模型

```python
class TradeAction(BaseModel):
    # ==================== 核心字段 ====================
    trade_action_id: str           # UUID
    timestamp: datetime            # ISO 8601
    source: SourceInfo             # 来源归属
    target: TargetInfo             # 标的信息
    direction: TradeDirection      # 方向
    action_chain: List[ActionStep] # 操作序列
    
    # ==================== 来源信息 ====================
    class SourceInfo:
        creator_id: Optional[str]      # KOL ID
        content_id: str                # 内容 ID
        evidence_text: str             # 原文证据
        evidence_start_idx: int        # 起始位置
        evidence_end_idx: int          # 结束位置
        content_url: Optional[str]     # 原文链接
        
    # ==================== 标的信息 ====================
    class TargetInfo:
        ticker: str                    # 原始代码
        ticker_normalized: str         # 标准化代码
        market: str                    # US/HK/CN/CRYPTO
        instrument_type: str           # stock/option/etf
        company_name: Optional[str]    # 公司全名
        
    # ==================== 操作步骤 ====================
    class ActionStep:
        sequence: int                  # 执行顺序
        action_type: ActionType        # long/short/watch
        trigger_condition: str         # 触发条件
        trigger_type: TriggerType      # price_threshold/breakout
        target_price_low: float        # 目标价下限
        target_price_high: float       # 目标价上限
        position_size_pct: float       # 仓位比例
        
    # ==================== 市场富化 ====================
    class MarketEnrichment:
        market_price_at_time: float    # 发布时价格
        volume_avg_20d: float          # 20日均量
        high_52wk: float               # 52周最高
        low_52wk: float                # 52周最低
        pe_ratio: float                # 市盈率
        market_cap: float              # 市值
        
    # ==================== 回测结果 ====================
    class BacktestResult:
        return_pct: float              # 收益率
        holding_days: int              # 持仓天数
        exit_reason: ExitReason        # 退出原因
        exit_price: float              # 退出价格
        max_drawdown_pct: float        # 最大回撤
        
    # ==================== RLHF 反馈 ====================
    class RLHFFeedback:
        rating: int                    # 1-5 星
        is_correct: bool               # 是否正确
        corrections: List[str]         # 修正列表
        corrected_direction: TradeDirection
        corrected_ticker: str
        reviewer_id: str
        reviewed_at: datetime
```

### 4.6 前端契约 (AssetFile)

```typescript
// contracts.ts
interface AssetFile {
  id: string;
  name: string;
  size: string;
  date: string;
  type: string;
  status: string;
  workflowStage: WorkflowStage;
  stageBadge: string;
  creatorName: string;
  sourcePlatform: string;
  sourceType: SourceType;
  sourceGroupId?: string;
  sourceGroupName?: string;
  fileTimestamp?: string;
  preview?: string;
  matchTokens?: string[];
  
  // 新增字段
  fileType?: string;        // 聊天记录/图片/PDF/文档
  sourceName?: string;      // 来源名称
  semanticTitle?: string;   // LLM 生成语义标题
}
```

### 4.7 实体注册表

```python
# entity_registry.py
ENTITY_REGISTRY: Dict[str, EntityEntry] = {
    # US 股票
    "苹果": ("AAPL", "US", "ticker"),
    "微软": ("MSFT", "US", "ticker"),
    "英伟达": ("NVDA", "US", "ticker"),
    
    # HK 股票
    "腾讯": ("0700.HK", "HK", "ticker"),
    "阿里巴巴": ("9988.HK", "HK", "ticker"),
    
    # CN 股票
    "茅台": ("600519.SH", "CN", "ticker"),
    "宁德时代": ("300750.SZ", "CN", "ticker"),
    
    # 指数
    "大A": ("000001.SH", "CN", "index"),
    "沪深300": ("000300.SH", "CN", "index"),
    
    # 加密货币
    "比特币": ("BTC", "CRYPTO", "crypto"),
}
```

---

## 5. API 参考

### 5.1 API 总览

| 路由前缀 | 模块 | 功能 |
|---|---|---|
| `/api/files` | files.py | 文件管理、上传、列表 |
| `/api/review` | review.py | 复核流程 |
| `/api/rlhf` | rlhf.py | RLHF 反馈 |
| `/api/extraction` | extraction.py | 事件抽取 |
| `/api/aggregation` | aggregation.py | L4 聚合 (新增) |
| `/api/opinions` | opinions.py | 观点时间线 |
| `/api/enrichment` | enrichment.py | L1 富化 |
| `/api/integrations` | integrations.py | 外部集成 |
| `/api/wechat` | wechat.py | 微信接入 |
| `/api/bilibili` | bilibili.py | B站接入 |
| `/api/streams` | streams.py | 数据流 |
| `/api/sources` | sources.py | 数据源 |
| `/api/stats` | stats.py | 统计 |
| `/api/system` | system.py | 系统状态 |

### 5.2 核心 API 详情

#### 5.2.1 文件管理 (`/api/files`)

```
GET  /api/files                    # 获取文件列表
POST /api/files                    # 上传文件
GET  /api/files/enrichment/{entity} # 获取实体相关内容
```

#### 5.2.2 复核流程 (`/api/review`)

```
POST /api/review                   # 保存复核记录
```

#### 5.2.3 RLHF 反馈 (`/api/rlhf`)

```
POST /api/rlhf/submit              # 提交反馈
GET  /api/rlhf/pending             # 待复核列表
GET  /api/rlhf/action/{id}         # 获取详情
PUT  /api/rlhf/action/{id}         # 更新反馈
GET  /api/rlhf/stats               # 统计
GET  /api/rlhf/export              # 导出 DPO 数据
```

#### 5.2.4 事件抽取 (`/api/extraction`)

```
POST /api/extraction/extract       # 执行抽取
POST /api/extraction/batch         # 批量抽取
POST /api/extraction/pipeline      # 运行流水线
GET  /api/extraction/status        # 获取状态
```

#### 5.2.5 L4 聚合 (`/api/aggregation`) - 新增

```
GET  /api/aggregation/entities/{entity}/timeline  # 实体时间线
GET  /api/aggregation/entities/search?q=...       # 搜索实体
POST /api/aggregation/process                     # 处理文本
POST /api/aggregation/process-with-market         # 注入市场数据
GET  /api/aggregation/entity-index                # 实体索引
GET  /api/aggregation/resolve/{text}              # 解析实体
```

#### 5.2.6 观点时间线 (`/api/opinions`)

```
GET  /api/opinions/timeline        # 获取时间线
GET  /api/opinions/meta            # 获取元数据
GET  /api/opinions/{id}            # 获取详情
GET  /api/opinions/stats/summary   # 统计摘要
```

#### 5.2.7 微信接入 (`/api/wechat`)

```
POST /api/wechat/login             # 创建登录会话
GET  /api/wechat/login/status/{id} # 检查登录状态
GET  /api/wechat/accounts          # 列出账户
GET  /api/wechat/articles/{id}     # 列出文章
POST /api/wechat/sync/{id}         # 同步文章
```

#### 5.2.8 B站接入 (`/api/bilibili`)

```
GET  /api/bilibili/video/{bvid}    # 获取视频信息
POST /api/bilibili/transcribe/{bvid} # 转录视频
POST /api/bilibili/sync/{bvid}     # 同步到 L0
GET  /api/bilibili/list            # 列出转录视频
```

### 5.3 响应格式

```python
# 成功响应
{"ok": true, "data": {...}}

# 错误响应
{"ok": false, "error": {"code": "NOT_FOUND", "message": "..."}}
```

---

## 6. 前端架构

### 6.1 组件结构

```
finer_dashboard/src/components/
├── layout/                    # 布局组件 (6 个)
│   ├── sidebar.tsx           # 侧边栏
│   ├── main-board.tsx        # 主面板
│   ├── inspector-panel.tsx   # 检查器面板
│   ├── integrations-hub.tsx  # 集成中心
│   ├── source-filter.tsx     # 来源筛选
│   └── upload-button.tsx     # 上传按钮
│
├── studio/                    # 工作台
│   └── annotation-workbench.tsx
│
├── rlhf-review-panel/         # RLHF 复核面板 (9 个)
│   ├── RLHFReviewPanel.tsx   # 主面板
│   ├── OriginalTextCard.tsx  # 原文卡片
│   ├── DirectionReview.tsx   # 方向复核
│   ├── TickerReview.tsx      # 标的复核
│   ├── ActionChainReview.tsx # 操作链复核
│   ├── QuickTags.tsx         # 快捷标签
│   ├── ReviewNotes.tsx       # 备注
│   ├── ReviewActions.tsx     # 操作按钮
│   └── OverallRating.tsx     # 整体评分
│
├── kol-rating-card/           # KOL 评级卡片 (7 个)
│   ├── KOLRatingCard.tsx     # 主卡片
│   ├── DimensionScores.tsx   # 维度评分
│   ├── StarRating.tsx        # 星级评分
│   ├── PerformanceTimeline.tsx
│   ├── FocusAreas.tsx
│   └── RecentOpinions.tsx
│
├── opinion-timeline/          # 观点时间线 (5 个)
│   ├── OpinionTimeline.tsx   # 时间线
│   ├── TimelineNode.tsx      # 节点
│   ├── TimelineFilter.tsx    # 筛选
│   └── OpinionDetailModal.tsx
│
└── data-source-config/        # 数据源配置 (6 个)
    ├── DataSourceConfig.tsx
    ├── QRCodeDisplay.tsx
    ├── SyncStatus.tsx
    ├── BilibiliConfig.tsx
    └── WeChatConfig.tsx
```

### 6.2 工作流视图

```typescript
const WORKFLOW_VIEWS: WorkflowView[] = [
  { id: "intake",     tier: "L0", title: "接入台 / INTAKE" },
  { id: "enrichment", tier: "L1", title: "富化台 / ENRICHMENT" },
  { id: "library",    tier: "L2", title: "知识库 / LIBRARY" },
  { id: "parsing",    tier: "L3", title: "解析台 / PARSING" },
  { id: "extraction", tier: "L5", title: "抽取台 / EXTRACTION" },
  { id: "review",     tier: "L6", title: "复核台 / REVIEW" },
  { id: "backtest",   tier: "L8", title: "回测台 / BACKTEST" },
];
```

### 6.3 Next.js 配置

```typescript
// next.config.ts
const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" },
    ];
  },
};
```

### 6.4 路由规划

> **审阅建议 #6**：当前所有视图挤在单页面，需规划正式路由。

```
/                    → 主工作台（L0-L8 流水线视图）
/kol                 → KOL 列表（卡片 + 评分）        [Phase 3]
/kol/[id]            → KOL 详情（时间线 + 收益曲线）   [Phase 3]
/kol/[id]/backtest   → KOL 回测详情                   [Phase 3]
/kol/compare         → 多 KOL 对比                    [Phase 3]
/backtest            → 全局回测管理                   [Phase 2]
/settings            → 系统设置（数据源、KOL 管理）    [Phase 1]
```

### 6.5 前端工作流缺失视图

> **审阅建议 #2**：L4 和 L7 未出现在前端工作流视图中。

当前 `WORKFLOW_VIEWS` 缺少 L4（聚合）和 L7（时间线）的视图。建议增加：

```typescript
// 建议补充
{ id: "aggregation", tier: "L4", title: "聚合台 / AGGREGATION" },  // 只读浏览
{ id: "timeline",    tier: "L7", title: "时间线 / TIMELINE" },     // KOL 时间线
```

---

## 7. 外部集成

### 7.1 LLM 服务

| 服务 | 用途 | 模型 | 优先级 |
|---|---|---|---|
| GLM-5.1 (SVIPS) | 文本富化/分类 | GLM-5.1 | 0 (主) |
| Qwen-Plus (DashScope) | 文本降级 | qwen-plus | 1 (备) |
| Qwen-VL-Plus | 图像 OCR/分析 | qwen-vl-plus | 0 (主) |
| Qwen-VL-Max | 图像降级 | qwen-vl-max | 2 (备) |

```python
# model_config.py
class VisionModelRegistry:
    models = [
        ModelConfig(name="qwen-vl-plus", provider=DASHSCOPE, priority=0),
        ModelConfig(name="GLM-5.1", provider=GLM_SVIPS, priority=1),
        ModelConfig(name="qwen-vl-max", provider=DASHSCOPE, priority=2),
    ]

class TextModelRegistry:
    models = [
        ModelConfig(name="qwen-plus", provider=DASHSCOPE, priority=0),
        ModelConfig(name="GLM-5.1", provider=GLM_SVIPS, priority=1),
    ]
```

### 7.2 Finance-Skills 服务

```python
# services/finance_skills_client.py
class FinanceSkillsClient:
    """统一金融数据客户端"""
    
    SKILLS = [
        "yfinance-data",      # 行情数据
        "funda-data",         # 基本面数据
        "sentiment-analysis", # 情绪分析
        "news-aggregator",    # 新闻聚合
        "options-flow",       # 期权流
    ]
    
    # 缓存策略
    CACHE_TTL = {
        "market": 60,         # 行情 1 分钟
        "fundamentals": 300,  # 基本面 5 分钟
        "sentiment": 300,     # 情绪 5 分钟
    }
```

### 7.3 飞书集成

```yaml
# configs/feishu.yaml
feishu:
  watched_chats:
    - chat_id: "oc_xxx"
      name: "群名称"
      notebook_id: "xxx"
      default_creator: "creator_id"
  
  poll_interval_seconds: 300
  state_file: "data/.feishu_sync_state.json"
  inbox_dir: "data/inbox"
```

### 7.4 微信公众号集成 (新增)

```python
# wechat_exporter_client.py
# 需要部署 wechat-article-exporter 服务
BASE_URL = "http://localhost:3000"

# 登录流程
1. GET /api/web/login/getqrcode    → 二维码
2. GET /api/web/login/scan         → 轮询状态
3. POST /api/web/login/bizlogin    → 完成登录

# 文章获取
4. GET /api/web/mp/searchbiz       → 搜索公众号
5. GET /api/web/mp/appmsgpublish   → 获取文章列表
```

---

## 8. 配置管理

### 8.1 配置分层

| 文件 | 内容 | Git 忽略 |
|---|---|---|
| `.env` | API 密钥 | ✅ 是 |
| `configs/*.yaml` | 服务配置 | ❌ 否 |
| `src/finer/config.py` | 配置加载器 | ❌ 否 |

### 8.2 环境变量

```bash
# .env
GLM_API_KEY=xxx           # GLM-5.1 API Key
DASHSCOPE_API_KEY=xxx     # Qwen API Key
FINANCE_SKILLS_API_KEY=xxx # Finance-Skills Key
```

### 8.3 配置文件

```yaml
# configs/feishu.yaml
feishu:
  watched_chats: [...]
  poll_interval_seconds: 300

# configs/finance_skills.yaml
finance_skills:
  base_url: "https://finance-skills.himself65.com"
  timeout: 30.0
```

---

## 9. 已实现功能清单

> **完成度定义**：  
> - **Schema 完成**: 数据模型定义并可校验。  
> - **逻辑完成**: 核心算法或服务可以独立运行。  
> - **端到端可用**: 输入、存储、API、前端、测试全链路打通。  
> - **目标架构缺口**: 当前代码未覆盖，但对项目目标是必要能力。

### 9.1 端到端可用 (✅)

| 功能 | 模块 | 说明 |
|---|---|---|
| 飞书群聊同步 | `feishu_poller.py` | 消息轮询→文件下载→归档 |
| B站视频接入 | `bilibili_adapter.py` | 视频信息→字幕→转录→L0 |
| NotebookLM 同步 | `nlm_sync.py` | 文件上传→笔记同步 |
| 文件上传导入 | `files.py` | 上传→分类→入库 |
| 前端工作台 | `page.tsx` | L0-L8 流水线视图 |
| RLHF 复核面板 | `RLHFReviewPanel.tsx` | 方向/标的/操作链复核 |
| 观点时间线 UI | `OpinionTimeline.tsx` | 连接 `/api/opinions`，后端无真实数据时 fallback mock |
| 数据源配置 | `DataSourceConfig.tsx` | 飞书/B站/微信配置 |

### 9.2 逻辑完成 (⚙️)

| 功能 | 模块 | 缺失部分 |
|---|---|---|
| 话题拆分 | `enrichment/__init__.py` | 未与 L4 串联 |
| 实体抽取 | `enrichment/__init__.py` | 未与统一注册表完全打通 |
| 市场数据融合 (P0) | `market_context.py` | Finance-Skills 不可用时需要更明确的质量标记 |
| 情绪融合 (P1) | `sentiment_fusion.py` | 数据源覆盖不完整 |
| 视觉内容提取 | `vision_extractor.py` | 输出仍偏 Markdown/Segment，未升级为 ContentBlock |
| 音频转录 | `audio_extractor.py`, `funasr_client.py`, `mimo_asr_client.py` | 转录后缺语义 block 与质量卡 |
| 情绪标注 | `sentiment_enricher.py`, `ml/sentiment/` | 应作为 intent 附加维度，而非方向替代 |
| 黑话翻译 | `slang.py` | 词典需持续更新 |
| 实体消歧 (L4) | `aggregation/__init__.py` | 内存态，重启丢失 |
| 上下文聚合 (L4) | `aggregation/__init__.py` | 无持久化，无 API 暴露 |
| 市场预注入 (L4) | `aggregation/__init__.py` | 依赖 Finance-Skills 可用性 |
| TradeAction 抽取 | `trade_action_extractor.py` | 缺 V1 Intent 前置层，creator_id 和 timestamp 语义不稳定 |
| RLHF 反馈收集 | `rlhf.py` | 无与抽取流水线的自动串联 |
| DPO 数据导出 | `export_dpo.py` | 数据量不足，未实际训练 |
| 回测引擎 | `backtest/engine.py` | 引擎存在，但 pipeline L8 尚未调用 |
| 价格数据 Provider | `backtest/prices.py` | 历史行情质量和市场覆盖需加强 |
| 时间线引擎 | `timeline/engine.py` | 依赖上游 creator_id，未实现观点状态机 |
| KOL Scorer | `ml/kol_scorer.py` | 可计算分数，但需接真实回测和 intent 样本 |
| KOL 评级引擎 | `kol_rating_engine.py` | 数据来源偏文件/手动，与流水线未完全打通 |
| KOL Profile 管理 | `services/kol_profile.py` | 身份管理存在，但 persona/policy 不存在 |
| 统一 LLM 客户端 | `llm/client.py` | 部分调用方仍使用旧客户端 |
| 统一实体注册表 | `entity_registry.py` | enrichment 中仍有独立 ticker 映射 |
| 微信导出客户端 | `wechat_exporter_client.py` | 需部署 exporter 服务 |
| L4 聚合 API | `aggregation.py` | 无持久化，重启数据丢失 |
| 文件语义化标题 | `files_utils.py` | 依赖 LLM 服务可用性 |

### 9.3 目标架构缺口 (必须补齐)

| 缺口 | 当前近似能力 | 为什么必须补 |
|---|---|---|
| V0 ContentEnvelope | `ContentRecord` | 现有内容模型不足以统一图片、聊天、文档、PDF、音频 |
| V0 ContentBlock | `SegmentRecord` | 需要表达表格、图表、图片区域、聊天线程、音频时间段 |
| QualityCard | 无 | 需要决定哪些内容可进入 V1，哪些需复核或拒绝 |
| TemporalAnchor | `published_at`, `timestamp` | 需要拆分发布、提及、解析、生效交易时间 |
| NormalizedInvestmentIntent | `EventWithActions`, `TradeAction` | 需要先抽意图，再映射交易 |
| Policy Mapping | 无 | 需要根据 KOL 风格和风险偏好解释“加仓/看好/持有” |
| KOL Persona Policy | `KOLProfile` | 需要从 200-1000 条历史内容生成个性化 policy |
| ViewpointState | `KOLTimeline` | 需要串联同一 KOL 对同一标的的观点演化 |
| TargetOpinionGraph | 无 | 需要对比多个 KOL 对同一标的的分歧 |

---

## 10. 规划中的功能

当前规划以“架构契约先行”为原则。训练和大规模模型微调排在数据契约、质量评估、时间锚、intent 层之后。

### 10.1 Phase A: 架构契约冻结

| 任务 | 产出 | 验收 |
|---|---|---|
| 新增 V0 schema | `ContentEnvelope`, `ContentBlock`, `QualityCard`, `TemporalAnchor`, `EvidenceSpan` | 可序列化、可单测 |
| 新增 V1 schema | `NormalizedInvestmentIntent` | 能表达 direction/actionability/position_delta_hint/conviction |
| 定义 TradeAction 边界 | 文档 + schema 注释 | TradeAction 明确为 V3 执行动作 |
| 更新前端契约草案 | TypeScript type proposal | review 面板知道 V0/V1 字段 |

### 10.2 Phase B: V0 标准化 MVP

| 任务 | 产出 | 验收 |
|---|---|---|
| 图片 OCR block 化 | 标题/段落/表格/图表/image_region | 图片策略可追溯到原图区域 |
| 飞书聊天 block 化 | message/thread/speaker/time | 长聊天记录可按 KOL 和话题拆分 |
| 文档/PDF block 化 | section/table/page | 跨页和表格不丢结构 |
| 音频转录 block 化 | audio_segment + timestamp | 口语内容可按语义段落抽取 |
| 质量卡生成 | rule + model hybrid | pass/soft_pass/review/reject 可解释 |

### 10.3 Phase C: 时间与实体锚定

| 任务 | 产出 | 验收 |
|---|---|---|
| 四类时间字段 | published/mentioned/resolved/effective_trade | “上周/这周”能解析为绝对区间 |
| 时间置信度 | confidence + needs_review | 低置信度进入复核 |
| 实体链接 | company/ticker/sector/index | 标的、板块、指数可区分 |
| 证据回溯 | EvidenceSpan | intent 可回到 block/span/图片区域 |

### 10.4 Phase D: V1 Intent 抽取

| 任务 | 产出 | 验收 |
|---|---|---|
| Intent extractor prototype | API 模型 + schema validation | “看好”和“加仓”输出不同 actionability |
| zhiziX 接入 | sentiment_features | 情绪作为附加维度，不替代 direction |
| 模糊样本保留 | ambiguity_notes | 不确定样本不丢弃 |
| V1 review 字段 | 前端复核草案 | 人工能修 direction/actionability/position_delta_hint |

### 10.5 Phase E: Policy 与 TradeAction 映射

| 任务 | 产出 | 验收 |
|---|---|---|
| Global Base Policy | 通用语言到动作规则 | 可解释默认映射 |
| Style Archetype Policy | 短线/景气/价值/烟蒂等风格 | 同一句“加仓”因风格有不同解释 |
| Risk Preference Policy | 激进/均衡/保守 | 风险偏好影响持仓期和默认动作强度 |
| KOL Persona Policy | 基于历史内容的个体修正 | 200-1000 条内容可生成草案 |
| Intent -> TradeAction | V3 mapping | 每条 action 带 policy_version 和 rationale |

### 10.6 Phase F: 观点状态机与多 KOL 分歧

| 任务 | 产出 | 验收 |
|---|---|---|
| ViewpointState | 同一 KOL-同一标的观点状态 | 可串联腾讯/福寿园观点演化 |
| Cross-doc linking | intent 间关联边 | 支持观点增强、减弱、反转、退出 |
| TargetOpinionGraph | 多 KOL 同标的观点图 | 可展示共识/分歧 |

### 10.7 Phase G: 回测闭环与训练数据

| 任务 | 产出 | 验收 |
|---|---|---|
| pipeline L8 接 BacktestEngine | 真实回测结果 | 指定 KOL + 时间范围可生成回测 |
| KOL scorer 接真实回测 | KOL 评分闭环 | 评分不依赖 mock |
| SFT/DPO 数据导出升级 | V1/V3 双层标签 | 训练样本能追溯证据和人工修正 |
| 小模型训练 | Intent 分类/抽取模型 | 在高质量样本足够后执行 |

---

## 11. 部署与运维

### 11.1 启动命令

```bash
# 后端 API
uvicorn finer.api.server:app --reload --port 8000

# 前端 Dashboard
cd src/finer_dashboard && npm run dev

# CLI 工具
python -m finer.cli init-storage
python -m finer.cli feishu-sync
```

### 11.2 依赖安装

```bash
# 后端
pip install -r requirements.txt

# 前端
cd src/finer_dashboard && npm install
```

### 11.3 数据目录初始化

```bash
python -m finer.cli init-storage
```

创建以下目录：
- `data/raw/` - 原始文件
- `data/processed/` - 处理后数据
- `data/L0_ingest/` ~ `data/L8_metrics/` - 各层产物

### 11.4 微信导出服务部署

```bash
# Docker 部署
docker run -p 3000:3000 ghcr.io/wechat-article/wechat-article-exporter:2.3.12

# 或本地运行
git clone https://github.com/kelipovanatalja453-bot/wechat-article-exporter
cd wechat-article-exporter
yarn install && yarn dev
```

---

## 12. 开发规范

### 12.1 代码风格

- **Python**: 遵循 PEP 8，类型注解必须完整
- **TypeScript**: 使用 ESLint (`npm run lint`)
- **命名**: Python 用 snake_case，TypeScript 用 camelCase

### 12.2 分层调用规则

| 层 | 可调用 |
|---|---|
| L0 接入 | `services/llm.py`, `services/converter.py` |
| L1 富化 | `services/finance_skills_client.py`, `parsing/slang.py` |
| L3 解析 | `services/llm.py`, `parsing/slang.py` |
| L5 抽取 | `services/llm.py`, `enrichment/market_context.py` |
| L6 复核 | `services/`, `ml/` |

**禁止**：跨层直接调用（如 `extraction/` 直接调 `ingestion/`）

### 12.3 Schema 即真相源

- 数据结构变更**只改 Pydantic 模型**
- 前端 `contracts.ts` 必须与 Pydantic 模型字段名、类型一致
- 新增字段必须有 `Field(description=...)` 说明

### 12.4 测试规范

```bash
# 运行测试
pytest tests/ -v

# 前端构建验证
cd src/finer_dashboard && npm run build
```

### 12.5 Git 约定

- Commit message: `type(scope): description`
- Type: feat / fix / refactor / docs / test / chore
- Scope: ingestion / enrichment / extraction / api / dashboard / schemas / ml

---

## 附录

### A. 文件统计

| 类型 | 数量 |
|---|---|
| Python 源文件 | 68 |
| TypeScript 组件 | 50 |
| API 路由 | 16 |
| Schema 模型 | 8 |
| 配置文件 | 6 |

### B. 代码行数统计

| 模块 | 行数 |
|---|---|
| `schemas/trade_action.py` | 750 |
| `services/kol_rating_engine.py` | 935 |
| `aggregation/__init__.py` | 448 |
| `wechat_exporter_client.py` | 678 |
| `api/routes/aggregation.py` | 350 |

### C. 参考文档

- [implementation_plan.md](../implementation_plan.md) - 详细实施规划
- [architecture_review.md](../architecture_review.md) - 架构审阅与改进建议
- [CLAUDE.md](../CLAUDE.md) - 开发规范
- [wechat-article-exporter](https://github.com/kelipovanatalja453-bot/wechat-article-exporter)

---

## 13. 数据治理

> **审阅建议 #3**: 当前系统以文件系统为存储，缺乏数据生命周期管理。以下为治理框架。

### 13.1 数据生命周期

```
创建 (L0) → 富化 (L1) → 标准化 (L2) → 解析 (L3) → 聚合 (L4) → 抽取 (L5) → 复核 (L6) → 归档/淘汰
```

### 13.2 数据保留策略

| 数据层级 | 保留周期 | 归档策略 | 淘汰条件 |
|---|---|---|---|
| L0 原始文件 | 永久 | 压缩归档 | 不淘汰 |
| L1 富化产物 | 90 天 | 覆盖重算 | 模型升级后重算 |
| L3 解析产物 | 90 天 | 覆盖重算 | 模型升级后重算 |
| L5 候选事件 | 30 天 | 转入 L6 或删除 | 低置信度且无人工复核 |
| L6 标注数据 | 永久 | 版本化存储 | 不淘汰 |
| L8 回测结果 | 永久 | 版本化存储 | 不淘汰 |
| 缓存数据 | 1 小时 | 自动过期 | TTL 到期 |

### 13.3 数据质量检查

| 检查点 | 规则 | 触发时机 |
|---|---|---|
| Schema 一致性 | Pydantic 模型验证 | 每次写入 |
| 前后端契约同步 | `contracts.ts` 字段校验 | CI 构建 |
| 实体标准化 | `entity_registry.py` 查询 | L1/L4 处理 |
| 去重检查 | `content_id` 唯一性 | L0 接入 |
| 人工复核率 | L5→L6 转化率监控 | 每日统计 |

### 13.4 数据血缘追踪

```
ContentRecord.content_id
    → SegmentRecord.content_id (1:N)
        → EventWithActions.content_id (1:N)
            → TradeAction.source.content_id (1:N)
                → RLHFFeedback → TradeAction.trade_action_id
```

每条数据可沿 `content_id` 链回溯到原始来源。

---

## 14. 非功能性需求

> **审阅建议 #4**: 当前文档缺少非功能性需求。以下为系统级约束。

### 14.1 性能要求

| 指标 | 目标 | 当前状态 |
|---|---|---|
| API 响应时间 (P95) | < 2s (非 LLM) | 未测量 |
| LLM 调用延迟 | < 30s (单次) | 依赖外部服务 |
| 文件上传 | 支持 100MB | 已实现 |
| 并发请求 | 10 并发用户 | 未测试 |
| 前端首屏加载 | < 3s | 未测量 |

### 14.2 可靠性

| 指标 | 目标 | 当前状态 |
|---|---|---|
| LLM 降级 | 主模型不可用时自动切换 | ✅ 已实现 (model_config.py) |
| Finance-Skills 降级 | 不可用时跳过市场数据 | ⚠️ 部分实现 |
| 数据不丢失 | L0 原始文件永不丢失 | ✅ 文件系统保证 |
| 进度可恢复 | 飞书同步断点续传 | ✅ state_file 机制 |

### 14.3 安全性

| 要求 | 实现 | 状态 |
|---|---|---|
| API 密钥不进代码 | `.env` + `os.environ` | ✅ |
| LLM 调用鉴权 | API Key 传递 | ✅ |
| 文件访问控制 | 无认证 | ❌ 需实现 |
| 输入校验 | Pydantic 模型验证 | ✅ |
| XSS 防护 | Next.js 默认 | ✅ |

### 14.4 可观测性

| 维度 | 当前状态 | 目标 |
|---|---|---|
| 日志 | `print` / `logging` | 结构化日志 (structlog) |
| 指标 | 无 | Prometheus 指标 |
| 追踪 | 无 | OpenTelemetry |
| 告警 | 无 | LLM 调用失败率告警 |

---

## 15. 已知问题与改进计划

> 本节记录当前架构和代码的真实差距。优先修正会影响目标闭环的结构性问题。

### 15.1 架构问题

| # | 问题 | 严重度 | 改进计划 | 目标版本 |
|---|---|---|---|---|
| A1 | 缺 V0 标准化内容层 | 🔴 高 | 新增 ContentEnvelope/ContentBlock/QualityCard | v1.4 |
| A2 | 缺 V1 投资意图层 | 🔴 高 | 新增 NormalizedInvestmentIntent，前置于 TradeAction | v1.4 |
| A3 | 时间字段语义混杂 | 🔴 高 | 新增 TemporalAnchor，拆分四类时间 | v1.4 |
| A4 | `creator_id` 未稳定填充，KOL 归属断裂 | 🔴 高 | 在 L0/V0 绑定 KOLProfile，并传递到 V1/V3 | v1.4 |
| A5 | TradeAction 抽取直接面对摘要/文本，证据链弱 | 🔴 高 | V0 EvidenceSpan -> V1 Intent -> V3 Action | v1.4 |
| A6 | KOL persona/policy 未进入抽取链路 | 🔴 高 | 建立 policy 分层和 persona policy | v1.5 |
| A7 | L4 聚合层内存态，重启丢失 | 🟡 中 | 引入 SQLite/DuckDB 索引或持久化 | v1.5 |
| A8 | pipeline L8 未接 BacktestEngine | 🟡 中 | orchestrator 调用真实回测引擎 | v1.5 |
| A9 | KOL 评级与真实流水线脱节 | 🟡 中 | 用 V3/L8 结果驱动评分 | v1.6 |
| A10 | 跨文档观点状态机缺失 | 🟡 中 | 新增 ViewpointState 和 TargetOpinionGraph | v1.6 |

### 15.2 数据问题

| # | 问题 | 严重度 | 改进计划 | 目标版本 |
|---|---|---|---|---|
| D1 | 图片、聊天、文档、音频清洗质量无统一评分 | 🔴 高 | QualityCard 六维主卡 | v1.4 |
| D2 | 图片策略未被一等公民处理 | 🔴 高 | 图片 block 化，保留表格/图表/image_region | v1.4 |
| D3 | 长聊天记录缺线程恢复 | 🔴 高 | speaker/thread/time/topic 重组 | v1.4 |
| D4 | 相对时间解析缺置信度 | 🔴 高 | TemporalAnchor confidence + review gate | v1.4 |
| D5 | 无数据版本控制 | 🟡 中 | Git LFS、DVC 或内容哈希版本 | v1.6 |
| D6 | 缓存无统一失效策略 | 🟡 中 | TTL + 主动失效 + cache lineage | v1.5 |
| D7 | 大文件散落在 `src/` 下 | 🟢 低 | 移到 `data/raw/` 或 sample fixtures | v1.5 |

### 15.3 工程问题

| # | 问题 | 严重度 | 改进计划 | 目标版本 |
|---|---|---|---|---|
| E1 | pytest async 配置存在但当前环境未执行 async 测试 | 🟡 中 | 安装/配置 pytest-asyncio 或迁移到 anyio | v1.4 |
| E2 | 前端 KOL/回测页面仍有 mock 数据 | 🟡 中 | 接入真实 `/api/kol` 和 `/api/backtest` | v1.5 |
| E3 | 部分文档与代码状态不一致 | 🟡 中 | 引入完成度定义和架构状态表 | v1.4 |
| E4 | 无结构化日志和 pipeline 指标 | 🟢 低 | 引入 structlog + metrics | v1.6 |
| E5 | API 认证默认关闭 | 🟡 中 | 明确本地/生产安全配置 | v1.6 |

### 15.4 版本规划

```
v1.3 (当前)  — 架构文档对齐，明确 V0/V1/V2/V3/V4/V5 目标链路
v1.4 (2 周)  — V0/V1 schema + 质量卡 + 时间锚 + 图片/聊天标准化 MVP
v1.5 (4 周)  — Policy Mapping + KOL Persona Policy + Intent -> TradeAction
v1.6 (6 周)  — ViewpointState + 多 KOL 分歧图谱 + L8 pipeline 闭环
v2.0 (8+ 周) — SFT/DPO 训练 + 本地模型替代部分 API + 自动 policy 优化
```

---

*文档版本: 1.3.0 | 最后更新: 2026-04-27 | 审阅基准: architecture_review.md + architecture-alignment-plan.md + 当前代码状态*
