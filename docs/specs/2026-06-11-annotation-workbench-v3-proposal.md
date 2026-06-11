# 标注工作台 v3 优化提案 — 对照 doccano / Label Studio / brat 与四个实际使用问题

> 状态：**已实施（2026-06-11，全部六项，实施记录见 §10）**。基于 2026-06-11 用户实际标注一轮后反馈的四个问题，
> 对照此前讨论过的标注工具（doccano、Label Studio、brat，见 `configs/label_studio/event-labeling-spec.md`
> 旧 spec）逐项给出方案。所属线：F+ Training Loop（annotation workbench）。

## 概述

当前工作台（v2，`docs/specs/2026-06-10-annotation-workbench.md`）已覆盖键盘流、实体 chip、
价位可溯、弃权拦截、草稿持久化。一轮真实标注暴露出四个结构性缺口：**上下文缺失、多标的、
KOL 风格信息无处沉淀、无行情对照**。本提案给出每个问题的落地设计、schema 影响和实施顺序。

## 1. 对照成熟标注工具的差距盘点

| 能力 | doccano | Label Studio | brat | 本工作台 v2 | 结论 |
|---|---|---|---|---|---|
| 文档级上下文（整文展示+区域高亮） | ✅ | ✅ | ✅ | ❌ 只展示孤立段落 | **缺口 → 问题 1** |
| 重叠/多实体标注 | ✅ span 多标签 | ✅ 多 region | ✅ 关系标注 | ❌ gold 单 ticker | **缺口 → 问题 2** |
| 模型预标注（pre-annotation） | ✅ auto-label | ✅ ML backend | ❌ | 部分（实体 chip、建议 conviction） | **最大吞吐杠杆，见 §6** |
| 选区即标注（select span → label） | ✅ | ✅ | ✅ | ❌ 表单流，与原文割裂 | 部分采纳（选区→动作菜单） |
| 标注者间一致性（IAA） | ✅ | ✅ | ✅ | ❌ 单标注者 | 后置（P3，10% 双标） |
| 外部数据面板（行情对照） | ❌ | ❌ | ❌ | ❌ | 本项目特有需求 → 问题 4 |
| 任务队列/抽样 | ✅ | ✅ | ❌ | ✅ seeded 抽样 | 已对齐 |
| 键盘流/吞吐优化 | 弱 | 弱 | 弱 | ✅ | 已领先 |

通用工具解决不了问题 3（KOL profile 沉淀）和问题 4（行情对照）——这正是自建工作台的价值；
问题 1、2 则是通用工具的标配能力，必须补齐。

## 2. 问题 1：上下文缺失 → 上下文扩展 + 并入证据（P0）

### 现状与可行性

- eval 任务源 `data/dpo/eval/passages.jsonl` 每条带 `source_file`（飞书聊天导出
  `chat_history_*.md`）+ `timestamp`，由 `scripts/select_passages.py` 按消息块头
  `### [ts] ou_xxx (kind)` 切块产生。
- 后端可用同一正则重新切块、按 timestamp（或内容 hash = item id）定位当前块，返回前后 ±N 块。
  **零新数据依赖。**

### 关键设计决策：补充的上下文必须写回 eval 样本

如果标注者看了邻近消息才定出 gold，而评测时模型只看到孤立段落，评测就不公平
（标注者信息量 > 被测模型信息量）。所以"展开上下文"必须分两个动作：

1. **只看**（默认）：展开邻近消息辅助判断，不影响样本。
2. **并入证据**：勾选某几条邻近消息 → 写入标注的 `context_blocks` 字段 →
   formal export 时把 context 拼进 eval 样本的 prompt（`evidence_text` 保持原样，
   导出时组装 `context_before + evidence + context_after`），保证模型与标注者看到同样的输入。

### 契约变更

```
GET /api/annotation/context?task_id=eval_gold&item_id=psg_xxx&before=5&after=5
→ {ok, data: {blocks: [{position: "before"|"self"|"after", offset: -2, timestamp, content}]}}
```

`EvalGoldAnnotation` 新增：

```python
class ContextBlock(BaseModel):
    offset: int          # 相对当前块的位置，-2 = 前面第 2 条
    timestamp: str
    content: str

context_blocks: List[ContextBlock] = []   # 标注者勾选并入证据的邻近消息
```

前端：EvidenceCard 顶部/底部"⌄ 展开上文 / 展开下文"按钮（每次 +3 条，懒加载），
每条展开的消息带"并入证据"checkbox；并入后该消息变为正式证据样式（与原文同色）。

## 3. 问题 2：一段话多个标的 → 主 gold + 备选 gold（P0）

### 现状

`GoldExtraction.ticker` 是单值；实测样例"吉利和速腾"（吉利 0175.HK + 速腾聚创 2498.HK）
无法标注，标注者被迫填"吉利 速腾"触发告警。`scripts/eval_compare.py` 的 `ref_score`
只对单 gold 比对 direction/ticker/承诺一致性。

### 方案：primary + alternates（不拆样本）

基座模型的抽取合同是单对象 `{ticker, direction, action_chain}`——一段多标的文本，
模型抽出**任何一个**正确意图都应得分。因此：

```python
# EvalGoldAnnotation 新增
alt_golds: List[GoldExtraction] = Field(
    default_factory=list,
    description="次要标的的 gold（多标的段落）；评测时 match-any 计分",
)
```

`eval_compare.py` 改动一行逻辑：`score = max(ref_score(pred, g) for g in [gold, *alt_golds])`。

不选「拆分样本」方案的理由：拆样本会改变 item 身份（id、manifest、防泄漏比对全要跟着改），
且两个子样本共享同一段证据文本，模型对同一输入只输出一个抽取，必然有一半"答错"——
评测语义反而失真。

### 前端

- gold 表单加"+ 次要标的"按钮，展开精简版子表单（ticker + direction + conviction，
  不含完整 action chain——次要标的通常没有完整动作链，留 notes 即可）。
- 实体 chip 检测到 ≥2 实体时自动提示"本段含多个标的"。

### 配套快赢：实体库缺口收集

"吉利""速腾聚创"都不在 `entity_registry.py`。在 ticker 告警旁加"提交实体库候补"按钮，
追加写入 `data/annotation/registry_gaps.jsonl`（alias + 建议 ticker + item_id），
人工 review 后批量进 registry——不允许标注端直接写 registry（防污染）。

## 4. 问题 3：KOL 风格信息沉淀 → 选区速记进 KOL Profile（P1）

### 现状

`services/kol_profile.py` + `schemas/kol_profile.py` 已有完整的 KOLProfile 管理
（`data/kol_profiles/{kol_id}.json`，含 bio/tags/rating），`api/routes/kol.py` 已存在。
缺的只是：标注流中把"描述投资风格的段落"一键存进去的通道。

### 方案：append-only 速记，不直接改 bio

```
POST /api/annotation/kol-note
{creator, category: "style"|"discipline"|"preference"|"track_record",
 text, source_item_id, source_file, reviewer_id}
→ 追加 data/kol_profiles/notes/{creator}.jsonl
```

- creator slug（maodaren/9you）→ kol_id 映射用 `KOLProfileManager.get_or_create(
  platform="annotation", account_id=creator)`，不阻塞主流程。
- 不直接覆盖 `bio`：速记是原始观察，bio 是人工综述。KOL 页后续聚合展示 notes，
  由人决定何时提炼进 bio。
- 前端：在 EvidenceCard 选中文本 → 浮动菜单出现「存入 KOL Profile」→
  弹出小卡片（预填选中文本 + category 单选 + 确认）。无选区时点按钮 = 全段存入。

实测样例（"猫大的风格是非常左侧+短中长周期错配兑现逻辑的交易风格…逐步左侧建仓"）
正是 `category=style` 的典型条目。

## 5. 问题 4：行情对照面板 → 接入本地 tushare 库（P1，有前置条件）

### 现状盘点

- `src/finer/market_data/` 已有完整的 **LocalPro**（tushare 兼容接口，DuckDB 查本地
  Parquet，零网络零积分），支持 `stock_basic` / `daily` / `pro_bar`（qfq/hfq 复权）/
  `trade_cal`。CLI：`finer market-data sync / status`。
- **但 `data/market/tushare/parquet/` 目前是空的** ——同步从未跑过。前置条件：
  1. `.env` 或环境变量配 `TUSHARE_TOKEN`（用户自己操作，不进代码）
  2. 跑 `python -m finer.cli market-data sync`（A 股日线 2016 至今，首次全量较久）
- **覆盖范围限制**：tushare daily_kline 只有 A 股（SSE/SZSE）。港股（0700.HK）、
  美股（TME/CSIQ）本地库没有 → 面板必须优雅降级显示"本地库无此市场数据"。

### 方案

```
GET /api/annotation/market?ticker=300750.SZ&date=2026-03-13
→ {ok, data: {ts_code, name, anchor_date, anchor_close, pct_chg_1d,
              window: [{trade_date, close, pct_chg}]  # T±10 交易日
              coverage: "local" | "unsupported_market"}}
```

- ticker → ts_code 解析复用 `entity_registry`（market 字段判 CN/HK/US）；
  CN 之外直接返回 `unsupported_market`。
- route 薄封装，查询逻辑放 `services/`（遵守"route 不写业务逻辑"）；
  LocalPro 每查询独立连接，无状态，加 TTL dict 缓存（同一 ticker+date 重复查询免 IO）。
- 前端：左栏 EvidenceCard 下方挂 MarketPanel——检测到实体 + item 自带 timestamp 即自动查询，
  展示：锚定日收盘价、当日涨跌、±10 日 sparkline（纯 SVG，不引图表库）。
- **对标注质量的直接价值**：① 验证"修复空间 20%"是比例而非价位（conviction 0.45 档的判据）；
  ② 填入的目标价与当时股价量级对不上时（如股价 180 填 400）前端直接告警。

## 6. 加餐（对照 Prodigy/Label Studio 得出的最大吞吐杠杆）：模型初稿预填

Prodigy 的核心洞见：**纠错远快于从零书写**。当前 gold 表单全手填；而仓库里
`scripts/run_inference.py` 已能对段落跑基座模型抽取。设计：

- 对 eval passages 离线跑一次基座模型 → `data/dpo/eval/drafts.jsonl`（标注辅助 sidecar，
  **不是训练数据**，与防泄漏无冲突——eval 段落本来就要喂给被测模型）。
- 工作台检测到 draft 存在时显示"模型初稿"卡片 + 一键采纳进表单，标注者只做修正。
- 防锚定偏置：初稿默认折叠，标注者先选了 标gold/应弃权 之后才展示。

预期把单条标注时间从 ~2min 压到 ~40s（`duration_ms` 字段已就位，可实测验证）。

## 7. Schema 版本策略

新增字段（`context_blocks` / `alt_golds`）→ `ANNOTATION_SCHEMA_VERSION = "2026-06-11.annotation.v3"`。
当前校验器 pin 单一版本，直接 bump 会把已有 v2 标注行全部打成 legacy。处理：

- 读取/合并：接受 `{v2, v3}`（v2 行缺新字段按默认值处理，合法）。
- 新提交：只接受 v3。
- formal export 阻断条件不变（坏行/悬空/泄漏），不因 v2 行存在而阻断。

## 8. 实施优先级与验收

| 序 | 项 | 改动面 | 验收 |
|---|---|---|---|
| 1 | 上下文扩展+并入 | annotation.py(schema/route/store) + EvidenceCard + export 拼装 | pytest 新增 context 用例；formal export 含 context 的样本 prompt 正确拼装 |
| 2 | 多标的 alt_golds | schema + EvalGoldForm + eval_compare match-any | 双标的段落可标注；eval_compare 单测 max 计分 |
| 3 | 实体库缺口收集 | 1 route + 1 button | registry_gaps.jsonl 追加成功 |
| 4 | KOL 速记 | 1 route + 选区菜单 | notes jsonl 落盘；KOL 页可见（后续） |
| 5 | 行情面板 | 1 route + MarketPanel 组件 | 前置：market-data sync 完成；A 股查得到、HK/US 降级 |
| 6 | 模型初稿预填 | run_inference 产 drafts + 表单采纳 | duration_ms 中位数下降 |

每步独立可交付；1、2 动 schema（版本 bump 一次完成），3-6 零 schema 变更。

## 9. 未解决项

- 港/美股行情来源（finance_skills_client 是否可补这块）未定，本提案先降级处理。
- IAA 双标流程（10% 抽样双标 + 冲突仲裁）后置 P3。
- `creator: "unknown"` 的样本（select_passages 识别失败）KOL 速记无处归属，
  需先修 creator_of() 或允许速记时人工选 creator。→ 已缓解：速记弹窗 creator 可手填。

## 10. 实施记录（2026-06-11）

### 变更清单

| 文件 | 类型 | 内容 |
|---|---|---|
| `src/finer/schemas/annotation.py` | 修改 | 版本 bump `2026-06-11.annotation.v3`；`ACCEPTED_SCHEMA_VERSIONS`（读兼容 v2）；新增 `ContextBlock`；`EvalGoldAnnotation.alt_golds/context_blocks` + 校验（offset≠0、offset 不重复、alt ticker 不与主 gold 重复、exclude 不带 alt） |
| `src/finer/services/annotation_store.py` | 修改 | `context()` 邻近块定位（hash 优先、timestamp 兜底）；`_eval_drafts_map()` + items 附 `draft`；`append_registry_gap()`/`append_kol_note()`（creator slug 路径清洗）；export 合并 context 进 `evidence_text` + 导出 `alt_golds`；submit 强制当前版本；legacy 检查改 accepted set |
| `src/finer/services/market_lookup.py` | 新增 | LocalPro 封装：ticker/alias→ts_code（entity_registry）、锚定日回退、±10 交易日窗口、TTL 缓存、四种 coverage 降级态 |
| `src/finer/api/routes/annotation.py` | 修改 | 新增 `GET /context`、`POST /registry-gap`、`POST /kol-note`、`GET /market`；submit 增加 stale-version ValueError 处理；全部 Line F envelope |
| `scripts/eval_compare.py` | 修改 | `ref_score_multi()`：对 `[gold, *alt_golds]` 取 max（match-any） |
| `src/finer_dashboard/src/lib/contracts.ts` | 修改 | `ContextBlock`/`ContextResponse`/`MarketWindowResult`/`MarketBar`；`EvalGoldAnnotation.alt_golds/context_blocks`；`EvalAnnotationItem.draft` |
| `.../annotation-workbench/EvidenceCard.tsx` | 重写 | 展开上文/下文（懒加载 ±20、步进 3）、并入证据 checkbox（并入块数字可点击）、文本选区 →「存入 KOL Profile」 |
| `.../annotation-workbench/EvalGoldForm.tsx` | 重写 | 次要标的子表单（chip 快填/重复告警）、模型初稿折叠卡（选 verdict 后可见 + 采纳并修正）、实体库候补内联提交、可溯文本含并入上下文、提交携带 context_blocks/alt_golds、tickerToFill 消费 |
| `.../annotation-workbench/MarketPanel.tsx` | 新增 | 实体 tab、锚定收盘/涨跌、±10 日 SVG sparkline、三种降级文案 |
| `.../annotation-workbench/AnnotationWorkbench.tsx` | 修改 | context 状态机（fetch/depth/included/重置）、KolNoteModal（creator 可编辑 + 四分类）、notice toast、MarketPanel 挂左栏 |
| `.../annotation-workbench/AnnotationManual.tsx` | 修改 | 新增「v3 新能力」章节 |
| `tests/test_annotation_store.py` | 修改 | +8 用例：v2 读兼容/v2 提交拒绝、alt_golds 校验、export 合并、offset 校验、context 定位/边界/异常、drafts 附着、侧车落盘与路径安全 |
| `tests/test_annotation_api.py` | 修改 | +5 用例：context roundtrip、registry-gap/kol-note 端点与错误 envelope、market 降级、stale version 拒绝 |
| `tests/test_market_lookup.py` | 新增 | duckdb 真实 Parquet fixture：本地窗口/锚定回退/别名解析/降级态/日期校验 |

### 架构影响

- F+ 数据契约 v3：`data/dpo/eval/annotations.jsonl` 新增字段向后兼容（v2 行读取合法，新提交强制 v3）。
- `eval_set.jsonl` 导出新增顶层 `alt_golds`、`meta.context_blocks_merged`；`evidence_text` 为合并后文本——下游 `run_inference.py`/`eval_compare.py` 无需改动即可消费（alt_golds 由 `ref_score_multi` 使用）。
- 新侧车文件：`data/dpo/registry_gaps.jsonl`（实体候补）、`data/kol_profiles/notes/{creator}.jsonl`（KOL 速记）、`data/dpo/eval/drafts.jsonl`（模型初稿，可选）。
- annotation route 依赖 `services/market_lookup`（轻封装 `market_data.LocalPro`），不触 F0-F8 主链路。

### 关键决策

1. **版本策略**：Pydantic 校验器接受 `{v2, v3}`，store.submit 额外强制当前版本——避免 bump 把存量 v2 标注打成 legacy 阻断 formal export。
2. **context 定位**：优先内容 hash（id 即 `psg_{sha1[:16]}`），timestamp 兜底——源文件追加新消息不影响定位。
3. **市场降级是状态不是异常**：HK/US/未同步返回 `coverage` 字段而非 4xx，前端展示对应文案。
4. **初稿防锚定**：折叠默认 + 提示「先形成自己的判断再看」，仅 pending 状态展示。

### 验证结果

- `pytest tests/ -q`：**2817 passed**, 1 failed（`test_backtest_extended.py::test_get_price_routing`，已用 `git stash` 验证为**既有失败**：`data/market/tushare/parquet/` 空目录使 `_build_cn_provider` 误选真实 provider，与本次无关，已另立修复任务）。
- 标注相关 35/35 全过（store 19 + api 10 + market 6）。
- `npm run build`：编译 + 类型检查通过。
- 实机验证（uvicorn --reload 重启后）：`/enums` 返回 v3；`/context` 对真实 eval 条目返回 offsets [-2..2]；`/market` HK→`unsupported_market`、300750.SZ→`no_local_data` 带 sync 提示。

### 使用前置（用户操作）

- 行情面板出数据需先同步本地库：`.env` 配 `TUSHARE_TOKEN` 后运行
  `python -m finer.cli market-data sync`（A 股日线 2016 至今，首次较久）。
- 模型初稿生成：`export DASHSCOPE_API_KEY=...` 后运行
  `python scripts/run_inference.py --eval-set data/dpo/eval/passages.jsonl --out data/dpo/eval/drafts.jsonl --model qwen3-8b`
  （`prompt_of` 对 passages 的 `evidence_text` 自动构造 prompt，无 key 可加 `--mock` 验证链路）。
