# 功能特性详解

本文档详细描述 Finer OS 的核心功能模块。

---

## 目录

- [多源数据导入](#多源数据导入)
- [Trade Action 提取](#trade-action-提取)
- [F2 富化/锚定层](#f2-富化锚定层)
- [RLHF 评价系统](#rlhf-评价系统)
- [KOL 评价体系](#kol-评价体系)
- [DPO 微调](#dpo-微调)
- [回测引擎](#回测引擎)

---

## 多源数据导入

Finer 支持多种数据源的无缝导入，自动归档、分类、索引。

### 飞书群同步

**核心功能**：
- 自动拉取飞书群消息（文本、图片、文件）
- 增量同步，避免重复下载
- 支持多群监控，按群配置分类规则
- 自动生成聊天记录转录文件

**配置示例**：

```yaml
feishu:
  watched_chats:
    - chat_id: "oc_xxx"
      name: "投资研究群"
      default_creator: "trader_jiu"
      classification_rules:
        - pattern: "周报"
          content_type: "weekly_strategy"
```

**使用流程**：

```bash
# 1. 同步飞书群
curl -X POST http://localhost:8000/api/integrations/feishu/fetch \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "oc_xxx"}'

# 2. 查看同步池
curl http://localhost:8000/api/integrations/pool

# 3. 导入到 F0
curl -X POST http://localhost:8000/api/integrations/import \
  -H "Content-Type: application/json" \
  -d '{"filenames": ["image.png"], "pool_type": "feishu"}'
```

**输出示例**：

```
data/L0_ingest/
└── trader_jiu/
    ├── weekly_strategy/
    │   ├── image.png
    │   └── chat_history.md
    └── daily_pre_post/
        └── report.pdf
```

---

### NotebookLM 集成

**核心功能**：
- 从 NotebookLM 笔记本拉取所有源文件
- 保留元数据（笔记本 ID、源 ID）
- 自动转换为 Markdown 格式

**使用流程**：

```bash
# 1. 获取笔记本列表
curl http://localhost:8000/api/integrations/nlm/notebooks

# 2. 同步指定笔记本
curl -X POST http://localhost:8000/api/integrations/nlm/fetch \
  -H "Content-Type: application/json" \
  -d '{"notebook_id": "nlm_xxx"}'
```

---

### B站视频/弹幕

**核心功能**：
- 使用 `BBDown` / `yt-dlp` 下载视频
- 提取视频字幕（AI 字幕或人工字幕）
- 抓取弹幕和评论

**实现路径**：

```python
# src/finer/ingestion/bilibili.py
class BilibiliIngestion:
    def download_video(self, bvid: str) -> Path:
        # 使用 BBDown 下载视频
        
    def extract_subtitle(self, video_path: Path) -> str:
        # 提取字幕文本
        
    def fetch_danmaku(self, bvid: str) -> List[Danmaku]:
        # 抓取弹幕
```

---

### 微信公众号长图

**核心功能**：
- 使用视觉大模型（Qwen-VL-Max）解析金融长图
- 保留排版结构，输出 Markdown
- 识别图表、表格、文字

**处理流程**：

```
长图 → VisionDescriptor → Markdown 文本 → 黑话翻译 → 清洗入库
```

**示例输入**：

![示例长图](../screenshots/wechat-image.png)

**示例输出**：

```markdown
# 周度策略回顾

## 核心观点

**腾讯 (TCEHY)**
- 当前价位：520 港元
- 目标建仓：480-500 港元
- 策略：短期看空，目标区间建仓

## 技术分析

| 指标 | 数值 | 信号 |
|:---|:---|:---|
| PE | 25 | 中性 |
| MACD | 金叉 | 看多 |
```

---

### 手动上传

**核心功能**：
- 支持任意格式文件上传
- 自动分类到 `_inbox/unclassified`
- 后续可在 Dashboard 中手动归类

---

## Trade Action 提取

这是 Finer 的核心功能：从自然语言文本中提取结构化的交易操作链。

### 多步操作链

**问题**：传统系统只提取"看多/看空"方向，丢失了丰富的操作细节。

**示例**：

| 原文 | 传统输出 | Finer 输出 |
|:---|:---|:---|
| "短期看空520的腾讯，目标480-500建仓" | `direction: bearish` | `actions: [short@520 → close_short → long@480-500]` |

**数据模型**：

```python
class TradingAction(BaseModel):
    action_type: Literal[
        "long",              # 买入
        "short",             # 做空
        "close_long",        # 平多
        "close_short",       # 平空
        "accumulate",        # 加仓
        "reduce",            # 减仓
        "buy_call",          # 买入看涨期权
        "sell_call",         # 卖出看涨期权
        "buy_put",           # 买入看跌期权
        "sell_put",          # 卖出看跌期权
        "hold",              # 持有
        "watch"              # 观望
    ]
    instrument_type: Literal["stock", "etf", "option", "unspecified"]
    trigger_condition: str | None     # 触发条件
    target_price_low: float | None    # 目标价格下限
    target_price_high: float | None   # 目标价格上限
    stop_loss: float | None           # 止损价
    sequence_order: int               # 操作顺序
    confidence: float                 # 置信度
```

**更多示例**：

| 原文 | 提取的操作链 |
|:---|:---|
| "sell 480的put" | `[sell_put(strike=480)]` |
| "这个位置可以轻仓先上车" | `[long(position_size=small)]` |
| "破了240就跑" | `[close_long(trigger=price<240, stop_loss=240)]` |
| "这里先不急，等一个确认信号" | `[watch]` |

---

### 条件触发器

**核心功能**：识别价格触发条件、时间触发条件。

**示例**：

```
原文："腾讯到480可以开始建仓，跌破450止损"

提取结果：
{
  "actions": [
    {
      "action_type": "long",
      "trigger_condition": "price <= 480",
      "target_price_low": 480,
      "stop_loss": 450
    }
  ]
}
```

---

### 衍生品映射

**核心功能**：将自然语言操作意图映射到衍生品策略。

**映射规则**：

| 自然语言 | 衍生品操作 |
|:---|:---|
| "短期看空，目标480建仓" | `[short@520 → close_short → long@480]` |
| "sell put收权利金" | `[sell_put]` |
| "买入看跌期权保护" | `[buy_put]` |
| "熊市价差" | `[buy_put@high_strike + sell_put@low_strike]` |

---

### 标的识别

**核心功能**：从自然语言中识别股票代码/公司名，映射到标准化代码。

**映射规则**：

| 原文 | 标准化代码 |
|:---|:---|
| "腾讯" | `TCEHY` (美股) / `0700.HK` (港股) |
| "阿里" | `BABA` (美股) / `9988.HK` (港股) |
| "苹果" | `AAPL` (美股) |
| "茅台" | `600519.SH` (A股) |

**实现**：

```python
# src/finer/enrichment/__init__.py
class EntityExtractor:
    def __init__(self):
        self.known_tickers = {
            "腾讯": "TCEHY",
            "阿里": "BABA",
            "苹果": "AAPL",
            # ...
        }
    
    def extract(self, content: str) -> EntityExtraction:
        # 字典匹配 + LLM 补充
```

---

## F2 富化/锚定层

F2 层对原始内容进行"富化"与"锚定"处理，建立内容间的关联网络。

### 话题拆分

**核心功能**：将长聊天记录按话题自动分割。

**处理流程**：

```
长聊天记录 → LLM 分析 → 话题片段
                          ↓
                   每个话题包含：
                   - 标题
                   - 相关标的
                   - 时间范围
                   - 摘要
```

**示例**：

**输入**：
```
[10:00] A: 腾讯最近怎么样？
[10:05] B: 520这个位置有点高，可以等等
[10:10] A: 那阿里呢？
[10:15] B: 阿里刚发财报，还可以...
[11:00] C: 明天大盘怎么看？
...
```

**输出**：

```json
{
  "topics": [
    {
      "title": "腾讯投资策略",
      "tickers": ["TCEHY"],
      "companies": ["腾讯"],
      "time_range": {"start": "10:00", "end": "10:10"},
      "summary": "讨论腾讯当前价位和建仓时机"
    },
    {
      "title": "阿里财报分析",
      "tickers": ["BABA"],
      "companies": ["阿里"],
      "time_range": {"start": "10:10", "end": "10:20"},
      "summary": "分析阿里最新财报表现"
    }
  ]
}
```

---

### 实体抽取

**核心功能**：提取股票代码、公司名、人物、事件、概念、指标。

**实体类型**：

| 类型 | 示例 |
|:---|:---|
| Tickers | AAPL, TCEHY, 0700.HK |
| Companies | 苹果, 腾讯, 阿里巴巴 |
| People | 巴菲特, 芒格, 段永平 |
| Events | 财报发布, 降息, 反垄断 |
| Concepts | AI, 云计算, 元宇宙 |
| Metrics | PE 25, 营收增长 15% |

**实现**：

```python
class EntityExtraction(BaseModel):
    tickers: List[str]
    companies: List[str]
    people: List[str]
    events: List[str]
    concepts: List[str]
    metrics: List[str]
```

---

### 内容关联

**核心功能**：建立内容间的关联网络，支持快速查找。

**索引结构**：

```json
{
  "index": {
    "AAPL": ["content_001", "content_002", "content_005"],
    "TCEHY": ["content_001", "content_003"],
    "腾讯": ["content_001", "content_003"],
    "财报": ["content_002", "content_004"]
  },
  "content_entities": {
    "content_001": {
      "tickers": ["AAPL", "TCEHY"],
      "companies": ["苹果", "腾讯"]
    }
  }
}
```

**查询接口**：

```bash
# 查询与 AAPL 相关的所有内容
curl http://localhost:8000/api/enrichment/by-ticker/AAPL

# 查询与腾讯相关的所有内容
curl http://localhost:8000/api/enrichment/by-company/腾讯
```

---

### 市场数据融合

**核心功能**：自动拉取实时价格、基本面数据，富化事件。

**实现**：

```python
# src/finer/enrichment/market_context.py
class MarketContextEnricher:
    async def enrich_events(self, events: List[Event]) -> List[EnrichedEvent]:
        # 并行拉取市场数据
        market_data = await self.client.call_batch([
            (SkillName.YFINANCE_DATA, {"ticker": e.ticker})
            for e in events
        ])
        
        # 验证价格区间
        for event, data in zip(events, market_data):
            current_price = data.get("current_price")
            if event.target_price_low:
                # 检查目标价是否合理
```

---

## RLHF 评价系统

Finer 提供完整的人类反馈收集和训练数据导出系统。

### 双轨标注流

**Track 1: SFT 修正**

适用于：明显的硬性错误（字段缺失、标的有误）

```
LLM 输出 → 人工修正字段值 → Gold Event Store
```

**Track 2: RLHF 偏好收集**

适用于：结构完整但有歧义的情况

```
原文 → LLM 生成 2-3 套 Action Chain → 人工选择最佳 → Preference Pair Store
```

**示例**：

原文："短期看空520的腾讯，目标480-500建仓"

**LLM 生成的选项**：

- **选项 A**：`[short@520 → close_short → long@480-500]`（现货逻辑）
- **选项 B**：`[sell_put@480]`（期权逻辑）
- **选项 C**：`[buy_put@520 + sell_put@480]`（熊市价差）

人工选择后，生成偏好对：

```json
{
  "prompt": "从以下文本提取 Trade Action:\n短期看空520的腾讯，目标480-500建仓",
  "chosen": "{\"actions\": [{\"action_type\": \"short\", ...}]}",
  "rejected": "{\"actions\": [{\"action_type\": \"sell_put\", ...}]}"
}
```

---

### 过程奖励模型 (PRM)

**核心思想**：对推理链的每一步独立打分，而非只在最终结果打分。

**投资事件抽取链**：

```
Step 1: 从原文中识别出 "腾讯" → 正确/部分正确/错误？
Step 2: 判断市场为 "HK" → 正确/错误？
Step 3: 判断方向为 "先空后多" → 正确/错误？
Step 4: 触发条件 "price=480-500" → 正确/错误？
Step 5: 操作类型 "short → long" → 正确/错误？
Step 6: 工具类型 "stock" → 正确/错误？
```

**实现**：

```python
class ProcessStepReward(BaseModel):
    step_name: str
    step_order: int
    correctness: Literal["correct", "partially_correct", "incorrect"]
    human_correction: str | None
    confidence: float
```

---

### 反馈模型

**完整反馈结构**：

```python
class RLHFFeedback(BaseModel):
    feedback_id: str
    trade_action_id: str
    
    # 整体评分 (1-5)
    rating: int
    
    # 标的正确性
    ticker_correct: bool
    ticker_correction: str | None
    
    # 方向正确性
    direction_correct: bool
    direction_correction: str | None
    
    # 操作链反馈
    action_chain_feedback: List[ActionChainFeedback]
    
    # 快捷标签
    quick_tags: List[str]  # "标的有误", "方向相反", "动作缺失"
    
    # 自由笔记
    notes: str | None
    
    # DPO 训练数据
    preference: Preference | None
```

---

## KOL 评价体系

Finer 定义了 **21 维投资观点评估矩阵**，全面评估创作者的分析能力。

### 五组维度

#### Group A: 分析能力

| 维度 | 核心含义 | 参考大师 |
|:---|:---|:---|
| 基本面分析 | 公司财务、估值催化的分析正确性 | Graham/Buffett |
| 技术面分析 | 趋势追踪、阻力支撑的分析准确度 | 经典 TA |
| 护城河判断 | 是否能识别核心壁垒 | Morningstar |
| 板块轮动 | 转换标的时是"领先市场"还是"追热点" | Sector Rotation |
| 跨资产逻辑 | 不同资产间推理不自相矛盾 | 达利欧 |

#### Group B: 环境感知

| 维度 | 核心含义 | 参考大师 |
|:---|:---|:---|
| 宏观判读 | 面对降息/经济周期的前瞻 | 达利欧 |
| 黑天鹅应激 | 突发事件的反应速度 | Taleb |
| 市场情绪 | 是否被极端贪婪/恐慌裹挟 | 行为金融学 |
| 叙事偏离度 | 能否识别市场故事偏离基本面 | **索罗斯反身性** |
| 消息面处理 | 处理公告、财报的即时性 | EMH |

#### Group C: 操作质量

| 维度 | 核心含义 |
|:---|:---|
| 仓位管理 | 建仓/减仓建议是否符合盈亏比 |
| 择时精度 | 区分"方向对但太早"和"时机恰好" |
| 操作可执行度 | 给出具体点位或区间 |
| 流动性意识 | 标的是否具备现实撮合深度 |

#### Group D: 风险调整收益（自动计算）

| 维度 | 计算方式 |
|:---|:---|
| Alpha 超额 | 组合收益 vs 基准 |
| 夏普比率 | 收益/波动 |
| Calmar 风险 | 收益/最大回撤 |

#### Group E: 元认知

| 维度 | 核心含义 |
|:---|:---|
| 情感强度 | "极度确信" vs "稍微关注" |
| 置信校准度 | 宣称胜率 vs 真实胜率 |
| 逻辑自洽性 | 是否言行一致 |
| 信息领先度 | 首发时差 |

---

## DPO 微调

Finer 支持从 RLHF 反馈自动生成 DPO 训练数据。

### 现代对齐方法

| 方法 | 核心思想 | Finer 适用场景 |
|:---|:---|:---|
| **DPO** | 将 RL 转化为分类 | 有高质量配对数据时 |
| **SimPO** | 去掉参考模型 | 数据有噪声时 |
| **KTO** | 基于前景理论 | 早期无配对数据 |
| **GRPO** | 组内互比 | ⭐ Finer 最佳匹配 |

**推荐流水线**：

```
SFT (500条标注) → KTO/SimPO (偏好数据) → GRPO + RLVR (规则验证器)
```

### 导出 DPO 数据

```bash
# 导出 JSONL 格式
curl "http://localhost:8000/api/rlhf/export?format=jsonl"

# 输出格式
{"prompt": "从以下文本提取...", "chosen": "{...}", "rejected": "{...}"}
{"prompt": "...", "chosen": "...", "rejected": "..."}
```

---

## 回测引擎

Finer 提供三种回测模式，从简单到复杂递增。

### Simple Window

**描述**：发布后持有 N 天看回报

**适用场景**：简单的"看多/看空"事件

**实现**：

```python
def simple_window_backtest(event, holding_days=10):
    entry_date = event.published_at
    exit_date = entry_date + timedelta(days=holding_days)
    
    entry_price = get_price(event.ticker, entry_date)
    exit_price = get_price(event.ticker, exit_date)
    
    return (exit_price - entry_price) / entry_price
```

---

### Trigger Entry

**描述**：仅在价格触及目标区间时才进场

**适用场景**：条件触发型操作

**实现**：

```python
def trigger_entry_backtest(event, max_wait_days=30):
    for day in range(max_wait_days):
        price = get_price(event.ticker, entry_date + day)
        if event.target_price_low <= price <= event.target_price_high:
            # 触发进场
            return calculate_return(...)
```

---

### Action Chain

**描述**：模拟完整的操作序列

**适用场景**：多步复合策略

**实现**：

```python
def action_chain_backtest(event):
    position = 0
    cash = 10000
    actions = event.actions
    
    for action in sorted(actions, key=lambda a: a.sequence_order):
        if meets_trigger(action):
            if action.action_type == "long":
                position, cash = execute_buy(...)
            elif action.action_type == "short":
                position, cash = execute_sell(...)
            # ...
```

---

### 七层评测指标

| F-Stage | 指标 | 目标值 |
|:---|:---|:---|
| F8 | Backtest Alpha | >0 |
| F6 | Human Preference Win Rate | >50% |
| F5 | Action Chain Exact Match | >60% |
| F4 | Slot-level F1 | >80% |
| F3 | Parse Success Rate | >95% |
| F2 | Entity F1 | >85% |
| F1 | Direction Accuracy | >90% |

---

## 扩展与定制

### 自定义黑话词典

编辑 `词语个人理解（持续更新）.xlsx`：

| 黑话 | 标准表达 | 类别 |
|:---|:---|:---|
| 上车 | 买入 | 操作 |
| 下车 | 卖出 | 操作 |
| 埋伏 | 提前建仓 | 策略 |
| 突破 | 价格突破阻力位 | 技术面 |

### 自定义分类规则

在 `configs/feishu.yaml` 中添加规则：

```yaml
classification_rules:
  - pattern: "周报"
    content_type: "weekly_strategy"
    creator_id: "trader_jiu"
  
  - pattern: "盘前"
    content_type: "daily_pre_post"
    creator_id: "trader_jiu"
```

### 自定义 LLM 后端

在 `src/finer/model_config.py` 中注册新模型：

```python
TEXT_MODELS = [
    ModelConfig(
        name="your-model",
        provider=ModelProvider.CUSTOM,
        base_url="https://your-api.com/v1",
        api_key_env="YOUR_API_KEY",
    ),
]
```

---

*最后更新: 2026-04-23*