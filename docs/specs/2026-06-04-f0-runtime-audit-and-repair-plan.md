# F0 Intake 运行时审计 + 并行修复扩展方案

> **日期**：2026-06-04
> **方式**：4 个只读侦察 Agent 并行排查（Line V 门控，未改任何文件），主控 Agent 汇总。
> **HEAD**：`d4e6c96d`
> **定位**：本文件同时作为 (1) F0 运行时 baseline report，(2) 后续实现型并行 Agent 声明 ownership / 冲突文件 / 验收命令的依据。

---

## 0. 一句话结论

F0 的问题**不在架构、不在测试**（126 个 F0 测试全绿、2026-06-03 审阅评"完整度高"），而在**运行时全是炸点 + 持久化七套各自为政 + Project Memory 从没接上电 + 前端 Import Console 是空壳**。静态审阅看不到这些，因为测试 mock 掉了所有外部依赖，"测试绿 ≠ 运行时可用"。

---

## 1. 运行时炸点（P0，今天点下去就断）

| # | 渠道/层 | 炸点 | 证据 | 性质 |
|---|---|---|---|---|
| 1 | 飞书 | lark-cli user token **2026-04-30 已过期**，live-poll 一点就断 | `lark-cli auth status` → tokenStatus=expired | 环境（需 re-login） |
| 2 | B站 BBDown | BBDown 需 **.NET 8**，本机只有 .NET 10 → 整链路挂掉 | `BBDown --help` 报缺 `8.0.0`；测试 mock subprocess 才显绿 | 环境（需装 runtime） |
| 3 | B站 classic | 缺 `DASHSCOPE_API_KEY` → `BilibiliAdapter.__init__` 构造即抛 ValueError | `bilibili_adapter.py:283,518` | 环境 + 代码（应延迟 require） |
| 4 | F0 核心 | **Project Memory SQLite 是空库（0 张表）**，每次 `/api/files` 都全盘 `os.walk` `data/raw`+`data/L0_ingest`(650MB) | `data/project_memory/finer.project.sqlite3` 仅 4096B；`asset_builder.py:255` | 代码（违反"不递归扫 raw"红线） |
| 5 | 前端 | **`/api/f0-index/*` 前端代理路由完全缺失** → Import Console 健康/历史/重建全部 404 | `src/app/api/` 下无 `f0-index/` 目录；`ImportConsole.tsx:24,40` | 代码（控制台空壳） |
| 6 | 微信公众号 | exporter service 没托管、没启动方式，端口 **3 处不一致**(3000/3001) | `configs/wechat.yaml:2` vs `config.py:70,145,151` vs `wechat_exporter_client.py:137` | 环境 + 代码 |

> 6 个炸点里 4 个有环境成分（token/.NET/DashScope/exporter service），但**根因都叠加了代码层缺乏优雅降级**：依赖缺失时不是返回带 fix_hint 的 canonical envelope，而是裸崩 / 误报 / 静默空态。

---

## 2. 结构性根因（真正的 F0 问题）

### 根因 A：七条渠道 = 五套落盘口径，Project Memory 完全没接电

**F0 持久化真值表**（从代码实读）：

| 渠道 | raw 落点 | ContentRecord | receipt | PM 写入 | index 可查 |
|---|---|---|---|---|---|
| 飞书 orchestrator | `data/raw/{creator}/{type}/` | ❌ | ❌（仅发飞书群通知） | ❌ | 仅 os.walk |
| 飞书 f0_importer | `data/raw/feishu/{chat}/` | ✅ `F0_intake/feishu/` | ❌（产 pack manifest） | ❌ | 仅 os.walk |
| NLM | `data/nlm_sync_pool/` | ❌ | ❌ | ❌ | 仅 os.walk |
| 本地上传 | `data/raw/_inbox/unclassified/` | ❌ | ❌ | ❌ | 仅 os.walk |
| 公众号 | `data/raw/wechat/{account}/` | ❌（仅 md+metadata） | ❌ | ❌ | 仅 os.walk |
| 视频号 | `data/raw/wechat/channels/` | ✅ `F0_intake/wechat/channels/` | ✅ `.receipt.json` | ❌ | 仅 os.walk |
| B站 | `F0_intake/bilibili/` | ✅ + **额外**写 `processed/manifests/` | ❌ | ❌ | 仅 os.walk |
| B站 BBDown | `data/raw/bilibili/` | ❌（纯下载器） | ❌ | ❌ | 仅 os.walk |

**权威结论**：
- 只有**视频号**做到完整三件套（ContentRecord + receipt）。
- **没有任何渠道写 Project Memory** —— 唯一写入者是从未被 wire 的离线脚本 `scripts/project_memory_backfill.py`。所以"导入成功 ≠ 进 catalog"，PM 永远空，`/api/f0-index/health` 永远 `missing`，每次查询全盘扫盘。
- ContentRecord 落点本身就有 3 个前缀，加 manifest 共 4 套并存。
- "receipt" 一词指代两个完全不同的东西（飞书群通知 vs 视频号手写 dict），**没有统一 Pydantic receipt model**。

### 根因 B：F0 内混入 F1/LLM 职责（架构边界破损）

- 飞书 `sync_chat()` 混入 Vision 描述 + Summary(LLM) + NLM sync（`orchestrator.py:348,368,401`）。
- B站 `/transcribe` 在 F0 route 内做 Paraformer ASR（`bilibili.py:196`）；`/sync` 强依赖先跑 transcript。
- BBDown 两处显式 `from finer.parsing.mimo_asr_client import`（`bbdown_client.py:846`、`bbdown.py:38`）跨层进 F1。

### 根因 C：前端 Import Console 是空壳，状态硬编码

- 三大功能端点（health/import-runs/rebuild）后端都有、契约**零 drift**、build/tsc 全过——但**前端缺代理路由**，全部 404，且 404 被显示成"无数据"（误导）。
- `SourceChannelStatus` 渠道状态**硬编码静态常量**，不反映后端真实健康。
- `UploadButton` 成功显示裸 "SUCCESS"——踩 CLAUDE.md 红线"不得把导入成功显示为解析成功"。
- 多处裸 `fetch` 绕过 `apiFetch`，丢弃 canonical 错误码/request_id/fix_hint。

### 根因 D：安全 / 合规风险

- 本地上传 `file.filename` 未消毒 → **路径穿越 / 覆盖**（`files.py:298`）。
- 公众号老 `WeChatAuthClient` 死代码含**模拟登录**（`_test_poll_count >= 10` 返回登录成功，`wechat_adapter.py:456`）——生产会误报。
- `wx_channels_download` vendored 目录：GPLv3 + Commons Clause + MITM root CA + RSA 私钥，发布风险（详见 `2026-05-wx-channels-dependency-policy.md`），binary 路径硬编码两处：`wechat.py:439`、`wechat_adapter.py:1365`。
- WeChat 前端代理 `headers: request.headers` 整体透传 cookie/auth（`wechat/[...path]/route.ts:13,71`）。

---

## 3. 全量问题清单（按严重度）

| ID | P | 区域 | 问题 | 证据 |
|---|---|---|---|---|
| R-01 | P0 | 飞书 | lark-cli token 过期，live-poll 断 | `lark-cli auth status` |
| R-02 | P0 | B站 | BBDown .NET8/10 不匹配，全链挂 | `BBDown --help` |
| R-03 | P0 | F0核心 | PM 空库，每次查询全盘 os.walk 650MB | sqlite 0 表；`asset_builder.py:255` |
| R-04 | P0 | F0核心 | 无任何 adapter 写 PM，catalog 永久 fallback | `ingestion/` 内 0 处 PM 写入 |
| R-05 | P0 | 前端 | `/api/f0-index/*` 代理路由缺失，控制台空壳 | `src/app/api/` 无 f0-index |
| R-06 | P1 | 微信 | exporter 未托管 + 端口 3 处不一致 | config 3000/3001 |
| R-07 | P1 | 微信 | 视频号 binary 硬编码、无 fallback | `wechat.py:439`,`wechat_adapter.py:1365` |
| R-08 | P1 | 微信 | binary 缺失被误报 `F0_IN_001`(不可重试) | `wechat_adapter.py:1322`→`wechat.py:487` |
| R-09 | P1 | B站 | `/transcribe` 在 F0 做 ASR + 缺 DashScope 构造即崩 | `bilibili.py:196`,`bilibili_adapter.py:283` |
| R-10 | P1 | B站 | `/sync` 强依赖先跑 `/transcribe`，否则永 404 | `bilibili.py:364-380` |
| R-11 | P1 | B站 | BBDown 两处跨层 import F1 ASR | `bbdown_client.py:846`,`bbdown.py:38` |
| R-12 | P1 | 飞书 | live-poll 违反 F0-only(混 Vision/Summary/NLM)，产 manifest 非 ContentRecord | `orchestrator.py:348,368,401` |
| R-13 | P1 | 飞书 | `sources.py` 用 HTTPException 非 FinerError | `sources.py:78,140,186` |
| R-14 | P1 | NLM | `nlm_sync.py` 默认路径 `/usr/local/bin/nlm` 不存在 → FileNotFoundError | `nlm_sync.py:18` |
| R-15 | P1 | NLM | `source_type="nlm_source"` 非 canonical(应 `nlm_note`) | `integrations.py:220` vs `content.py:27` |
| R-16 | P1 | 本地 | 上传不建 ContentRecord，sourceRecordId=None，F1 不可回溯 | `files.py:292-322` |
| R-17 | P1 | 本地 | 文件名未消毒 → 路径穿越/覆盖（安全） | `files.py:298` |
| R-18 | P1 | F0核心 | `collected_at` naive utcnow → deprecation + 跨渠道时区混用 | `content.py:45` |
| R-19 | P1 | F0核心 | 无统一 receipt model | `receipt.py` vs `wechat_adapter.py:1460` |
| R-20 | P1 | 前端 | UploadButton 裸 "SUCCESS" 误导（红线） | `upload-button.tsx:35` |
| R-21 | P2 | 微信 | 老 WeChatAuthClient 死代码 + 模拟登录 | `wechat_adapter.py:456-466` |
| R-22 | P2 | F0核心 | `/api/f0-index/records` 查 asset_index 但 schema 定义 content_records | `f0_index.py:74` |
| R-23 | P2 | F0核心 | source_type literal 缺 `wechat_channels_video`(unclassified workaround) | `content.py:22`,`wechat_adapter.py:1623` |
| R-24 | P2 | 前端 | SourceChannelStatus 硬编码，不反映真实健康 | `SourceChannelStatus.tsx:17` |
| R-25 | P2 | 前端 | 多处裸 fetch 绕过错误 envelope | `WeChatConfig.tsx:124`,`upload-button.tsx:35` |
| R-26 | P2 | 前端 | base URL 硬编码 127.0.0.1:8000，无 env 覆盖 | `src/app/api/**/route.ts` |
| R-27 | P2 | 前端 | WeChat 代理整体转发 cookie/auth header | `wechat/[...path]/route.ts:13` |
| R-28 | P2 | 本地 | 上传无 size/type 限制、无 dedupe | `files.py:293` |
| R-29 | P2 | NLM | `/nlm/fetch` 无 dedupe/external_source_id；refresh 分支死代码 | `integrations.py:236`,`sources.py:144` |
| R-30 | P2 | 落盘 | 口径分裂(channels receipt vs bilibili manifest vs 公众号无) | 见真值表 |
| R-31 | P3 | NLM | 内层异常 print 吞掉 | `integrations.py:246` |
| R-32 | P3 | B站 | `/sync` 残留 except HTTPException 死分支；search_videos stub | `bilibili.py:468` |
| R-33 | P3 | 微信 | `WeChatSyncResult.l0_triggered` legacy 命名 | schemas/wechat.py |

---

## 4. 修复 + 扩展方案

### 设计原则
1. **先冻结共享契约，再放渠道并行** —— 否则每个渠道 agent 继续各写各的，制造第 6、第 7 套口径。
2. **前端可与后端真正并行** —— Import Console 接通、UX 收敛不依赖后端契约冻结，立即可动。
3. **SQLite 写入/建表是红线** —— PM 接电需用户单独确认。
4. **环境炸点双轨** —— 用户侧修环境 + 代码侧优雅降级（依赖缺失也走 canonical envelope，不裸崩）。

### 阶段与任务卡

#### 🚪 GATE（串行，1 agent，阻塞所有后端渠道）— F0 共享契约冻结

| 项 | 内容 |
|---|---|
| Line | F0 Shared Contract Freeze |
| F-stage | F0 (cross-channel infra) |
| 产出 | ① 新增 `schemas/import_receipt.py` canonical `ImportReceipt` (含 request_id/status/content_id/source_channel/dedupe/raw_hashes/error envelope)；② `schemas/content.py` 加 `wechat_channels_video` literal + `collected_at` 改 aware UTC；③ 新增 `utils/time.py::now_utc()`；④ `paths.py` 定义统一 F0 落点常量 `F0_OUTPUT_ROOT/{platform}/`；⑤ 定义 `F0IndexWriter.record_imported(record, receipt)` **接口签名**（stub，不接 SQLite 实现） |
| 允许改 | `schemas/content.py`,`schemas/import_receipt.py`(new),`utils/time.py`(new),`paths.py`,`manifests.py`,新增 `tests/test_import_receipt.py` |
| 禁止改 | 任何渠道 adapter、route、前端、SQLite schema |
| 验收 | `pytest tests/test_f0_contract.py tests/test_import_receipt.py -q` 全绿 |

#### 🔧 后端渠道（GATE 后并行，4 agents，文件 ownership 互不重叠）

| 卡 | Line | 拥有文件 | 核心动作 | 验收 |
|---|---|---|---|---|
| **BK1 飞书+NLM** | F0 Feishu+NLM | `feishu_poller.py`,`feishu_f0_importer.py`,`orchestrator.py`,`nlm_sync.py`,`integrations.py`,`sources.py`,`classifier.py` | live-poll 改产 ContentRecord+ImportReceipt；Vision/Summary/NLM 移出 F0；`sources.py`→FinerError；nlm 路径用 `shutil.which`；nlm source_type→`nlm_note`；token 过期优雅降级带 fix_hint | `pytest tests/test_feishu_f0_contract.py` + 新增 nlm/feishu live-poll 测试 |
| **BK2 微信** | F0 WeChat | `wechat_adapter.py`(建议物理拆 official/channels),`wechat_exporter_client.py`,`api/routes/wechat.py`,`config.py`(wechat段),`configs/wechat.yaml` | 端口统一单一真相源；binary 改 external-install(`shutil.which`→env→config)；binary 缺失映射 `F0_EXT_001`；公众号补 receipt；删模拟登录块；exporter 离线优雅降级 | `pytest tests/test_wechat_*` 全绿 + 新增端口/external-install 测试 |
| **BK3 B站** | F0 Bilibili | `bilibili_adapter.py`,`api/routes/bilibili.py`,`bbdown_client.py`,`api/routes/bbdown.py` | `transcribe` 移出 F0（标 F1-adjacent）；新增 F0 `download_raw_artifacts()` 只下 raw；`/sync`→`/import` 不依赖 transcript；DashScope 延迟 require；BBDown 不在 F0 import F1 ASR；缺 .NET 优雅降级 | `pytest tests/test_bilibili* tests/test_bbdown*` 全绿 |
| **BK4 本地+查询对齐** | F0 Local+Index | `api/routes/files.py`,`api/routes/files_utils.py`,`api/routes/f0_index.py`,`enrichment/asset_builder.py`(上传段) | 上传建 ContentRecord+ImportReceipt；`file.filename` 消毒+hash 去重；size/MIME 白名单；`/records` 契约对齐(查 content_records 或改文档二选一) | `pytest tests/test_files_api_catalog.py` + 新增路径穿越/上传 record 测试 |

#### 🎨 前端（**从第 0 阶段就可并行**，2 agents）

| 卡 | Surface | 拥有文件 | 核心动作 | 验收 |
|---|---|---|---|---|
| **FE1 控制台接通** | Import Console | `src/app/api/f0-index/[...path]/route.ts`(new),`components/import-console/*`,`components/data-source-config/SourceChannelStatus.tsx` | 补 f0-index 代理路由（照抄 bilibili `[...path]` 模板）；SourceChannelStatus 接真实探活(`/api/sources/status`,`/api/wechat/exporter/health`)；404 与"无数据"区分展示 | `npm run build` + 手测控制台不再 404 |
| **FE2 导入入口 UX** | Intake UX | `components/layout/upload-button.tsx`,`components/data-source-config/WeChatConfig.tsx`,`BilibiliConfig.tsx`,`src/app/api/**/route.ts`(base url),`lib/api-client.ts` | upload 文案改"已入库 F0"+走 apiFetch 展示错误码；裸 fetch→apiFetch；base URL 抽 `process.env.BACKEND_ORIGIN`；代理 header 白名单不透传 cookie | `npm run build` + `npx tsc --noEmit` |

#### 🔌 阶段 2（需红线确认）— Project Memory 接电

| 卡 | 内容 | 红线 |
|---|---|---|
| **PM1** | 初始化 PM schema（wire migrate 进 `cli init-storage`）；实现 `F0IndexWriter.record_imported` 写入；各渠道导入成功后调用；Import Console 接真实 import_runs 数据 | ⚠️ **新增/迁移 SQLite 表、写入路径** —— 需用户确认表结构使用方式 |

### 依赖图

```
GATE(契约冻结) ──┬─→ BK1 飞书+NLM ──┐
                 ├─→ BK2 微信      ──┤
                 ├─→ BK3 B站       ──┼─→ PM1(需红线确认) ─→ FE1 接真实数据
                 └─→ BK4 本地+查询 ──┘
FE1 控制台接通 ───────(独立，立即可动)──────┐
FE2 导入入口 UX ──────(独立，立即可动)──────┴─→ 前端整体可用
```

---

## 5. 需用户确认的红线 / 决策

1. **本轮范围**：只修运行时炸点（让导入跑起来）/ 全量 canonical 收口（receipt+落点+PM 接电）/ 分阶段两者都要。
2. **Project Memory 接电（PM1）**：是否本轮就初始化 PM schema + 接通 adapter→PM 写入（触碰 SQLite，红线）。
3. **环境炸点处理**：环境修复清单（见 §6）由用户执行 vs 代码层优雅降级 vs 两者都做。
4. **wx_channels_download**：external-install 迁移（改 binary 查找）本轮是否做；删除 vendored 目录属红线，需单独确认。

---

## 6. 环境修复清单（用户侧，agent 不碰 .env/系统）

| 项 | 命令/动作 | 解决 |
|---|---|---|
| 飞书 token | `lark-cli auth login`（系统终端） | R-01 |
| .NET 8 | 安装 .NET 8 runtime（B站 BBDown 需要） | R-02 |
| DashScope | `.env` 加 `DASHSCOPE_API_KEY`（红线，用户改） | R-09 |
| 微信 exporter | 启动/托管 exporter service 并对齐端口 | R-06 |

---

## 7. 验证结果（侦察阶段）

- `pytest`：F0 相关 4 批共 **126 + 39 + 40 + 42 ≈ 247 passed**（全绿，但均 mock 外部依赖）。
- `npm run build` ✅ / `npx tsc --noEmit` ✅（前端唯一 TS error 是 stale `.next` 缓存，与 F0 无关）。
- 边界扫描确认 BBDown 跨层 import F1 ASR 仍在 `bbdown_client.py:846`。
- 4 个 agent 全程只读，未改任何文件/配置/schema/数据。

---

## 8. 未解决项

- 各渠道 adapter 内部下载/抓取逻辑的深度正确性（侦察聚焦边界与运行时，未逐行验证下载解析算法）。
- `data/L0_ingest`(650MB) 旧目录迁移到 `F0_intake` 的数据迁移方案（红线，需单独规划）。
- F1+ 如何消费 F0 移出的 Vision/Summary/ASR 能力（本方案只负责把它们移出 F0，落点交 F1 owner）。

---

## 9. Phase 1 执行记录（2026-06-04 ~ 06-05）

### 决策落定（用户拍板）
- **范围**：分阶段（先炸点 → 后收口）。
- **PM 接电**：批准**全量 backfill**（最初"仅 asset_index"在技术上不可行，见下）。
- **环境炸点**：环境清单用户执行 + 代码层优雅降级并入 Phase 2 渠道收口。

### P1-FE 控制台接通 — ✅ 完成验收
- 新增 `src/finer_dashboard/src/app/api/f0-index/[...path]/route.ts`（代理路由，header 白名单，不透传 cookie/auth）。
- `SourceChannelStatus.tsx` 改真实探活（`/api/sources/status` + `/api/wechat/exporter/health`），新增 `unknown`/`checking` 态，后端不可达降级"未知"而非假"可用"（修 R-24）。
- `ImportConsole`/`IndexHealthCard`/`ImportHistoryTable` 区分 404 与"无数据"。
- 验收：`npm run build` ✅（路由清单含 `ƒ /api/f0-index/[...path]`）；`tsc` 无新错误。

### P1-PM Project Memory 接电 — ✅ 完成验收
- `apply_migrations()` 接进 `cli init-storage`（幂等）；建 19 张 PM 表，health MISSING→HEALTHY。
- `asset_builder.py` fallback scan 移除 `data/L0_ingest`（650MB）止血（修 R-03）。
- 全量 backfill：`asset_index 368`（全 F0）/ `contents 570` / `source_records 572`。
- `/api/files?tier=F0` 走 catalog 返回 368 文件，`pm.degraded=False`，不再 os.walk。
- 变更文件：`scripts/project_memory_migrate.py`、`pipeline/_legacy.py`、`api/routes/asset_builder.py`。
- 验收：`56 passed`；空库备份 `.pre-phase1.bak` 完好。

### 关键发现（修正本文档 §2/§4 假设）
1. **asset_index 对 contents 有硬 NOT NULL 外键** → "仅 asset_index"不可行；填充 catalog 必须写完整 FK 图。§4 表B "避开 contents 复杂 FK" 的判断作废。
2. **F0 真实数据源是 `data/processed/manifests/`（202 manifest）**，非 `data/F0_intake/`（仅 6 测试 fixture）。真值表中各渠道"ContentRecord 落点"实际产物大量仍以 manifest 形态存在于 `processed/manifests/`。
3. backfill 脚本真实路径是 `src/finer/scripts/project_memory_backfill.py`（已测试覆盖，写全 FK 图）。

### 状态更新
- ✅ 已修：R-03（每次 os.walk 650MB）、R-05（前端 proxy 缺失）、R-24（渠道状态硬编码）。
- 🟡 部分缓解：R-04（无 adapter 写 PM）—— backfill 已把现有 202 manifest 灌入 PM；**新导入的增量写入仍待 Phase 2 接线**。
- ⚠️ **新 Open Issue（IDP-01）**：`project_memory_backfill` 的 `artifacts` 表用随机 ID、无去重键，重复 backfill 累积 `is_canonical=0` 历史行（371→742）。canonical 稳定 368、前端只消费 canonical，不影响功能但 DB 会膨胀 → 并入 Phase 2 "PM 增量写入"任务一并修去重键。

### Phase 2 待派发（未启动）
GATE 契约冻结（统一 receipt model / 落点规则 / `now_utc()` / source_type literal / PM 写入接口签名）→ 冻结后并行 BK1 飞书+NLM / BK2 微信 / BK3 B站 / BK4 本地+查询 + PM 增量写入接线 + FE2 导入入口 UX。渠道收口阶段一并 bake 进"依赖缺失优雅降级"（R-01/02/06/09 代码侧）。

---

## 10. Phase 2 执行记录（2026-06-05）

### 提交链（分支 `f0-runtime-repair`）
| commit | 内容 |
|---|---|
| `8ff2b16c` | Phase 1 运行时止血（PM 接电 + Import Console proxy）|
| `505fb9bb` | GATE 契约冻结（ImportReceipt / paths / now_utc / source_type / F0IndexWriter）|
| `3f3ad4bd` | Batch A（BK4 本地上传 + BK2 微信 + FE2 导入入口 UX）|
| `b32e7286` | Batch B（BK1 飞书+NLM + BK3 B站，收口 + 优雅降级）|

### GATE（505fb9bb）
冻结 5 契约：`schemas/import_receipt.py`(ImportReceipt，`to_import_run()` 零-drift 投影前端、递归无敏感字段)、`content.py`(补 `wechat_channels_video` + `collected_at` aware coerce)、`utils/time.py`(`now_utc`)、`paths.py`(F0 落点 helper)、`ingestion/f0_index_writer.py`(`record_imported` 确定性 key 幂等写 contents+source_record+asset_index)。IDP-01（artifact 非幂等）明确不写 artifacts 表，留后续。

### Batch A（3f3ad4bd）
- **BK4 本地+查询**：上传产 ContentRecord(`manual_upload`)+ImportReceipt+PM 行；文件名 neutralize-or-reject 防穿越；size(100MB)/扩展名/MIME 白名单+hash dedupe；`/records` 对齐 asset_index 真实列。
- **BK2 微信**：exporter 端口统一单一真相源(3001)；视频号 binary external-install(`shutil.which`→env→config→vendored)+缺失→`F0_EXT_001`(retryable)；删模拟登录；视频号 `source_type`→`wechat_channels_video`；公众号补 receipt+PM。
- **FE2 导入入口**：upload 文案"已入库 F0"(非解析)+5 处裸 fetch→apiFetch；base URL→`BACKEND_ORIGIN` env(13 代理)；wechat 代理 header 白名单。

### Batch B（b32e7286）
- **BK1 飞书+NLM**：飞书 F0 产 ContentRecord+receipt+PM；Vision/Summary/NLM 解耦(`F1_HANDOFF_SEAM`)；token 失败→`FEISHU_AUTH_001`+fix_hint 且 stderr 不外泄；`sources.py` HTTPException→FinerError；nlm `shutil.which`+`nlm_note`+dedupe+`print`→logger。
- **BK3 B站**：新增 F0 `POST /api/bilibili/import/{bvid}`(raw set→ContentRecord+receipt+PM，不依赖 transcript)；transcribe 移出 F0(F1-adjacent)+lazy DashScope；消除两处 F0→F1 ASR 跨层 import；BBDown 缺.NET→`F0_EXT_001`+fix_hint。

### 最终验收
- 全量后端 `pytest tests/` → **2764 passed, 15 skipped, 1 failed**。唯一失败 `test_backtest_extended.py::test_get_price_routing` 经父提交 `d4e6c96d` 复验**为 pre-existing**（F8 MockPriceProvider / TD-10，与 F0 无关）。
- 前端 `npm run build` ✅ / `tsc` ✅。
- 每 batch 合并验收 + frozen 契约零改动 + 文件 ownership 零重叠，均已逐项核验。

### R-01 ~ R-33 全部代码层解决
33 个问题全部收口。其中 R-01/02/06/09 的**环境侧**（lark-cli 登录 / .NET 8 / exporter 托管 / DashScope key）属用户执行项，代码侧已做优雅降级（依赖缺失走 canonical envelope + fix_hint，不裸崩）。

---

## 11. F0 渠道终态对照表

| 渠道 | 代码收口 | 产 ContentRecord+Receipt+PM | 能否立即 E2E | E2E 还需的环境 |
|---|---|---|---|---|
| 本地上传 | ✅ | ✅ | ✅ 立即 | 无 |
| 微信视频号 | ✅ | ✅ | 🟡 | binary 在 PATH/配置（external-install）|
| 微信公众号 | ✅ | ✅ | 🔴 | 启动并托管 exporter service |
| 飞书 | ✅ | ✅ | 🔴 | `lark-cli auth login`（token 已过期）|
| NotebookLM | ✅ | ✅ | 🔴 | nlm CLI 已登录 |
| B站 | ✅ | ✅ | 🔴 | .NET 8 runtime（+ DashScope 仅转录）|

> 所有渠道依赖缺失时均走 canonical FinerError + fix_hint，不裸崩、不误报、不泄敏感信息。F0 核心：PM catalog 已接电（asset_index 368 行）、统一 ImportReceipt、统一落点、aware UTC、`F0IndexWriter` 各渠道已接线。

## 12. 遗留项（Open Issues）
- **IDP-01**：`project_memory_backfill` / `F0IndexWriter` 暂不写 artifacts 表（随机 id 非幂等）；raw 溯源已在 receipt + 磁盘。需单独修 artifact 确定性去重键。
- **F1 接手**：Vision/Summary/ASR 已从 F0 解耦（seam 已留），F1 owner 需消费 raw + ContentRecord 跑这些阶段。
- **环境侧**：lark-cli 登录 / .NET 8 / exporter 托管 / DashScope key（用户执行清单 §6）。
- **数据迁移**：`data/L0_ingest`(650MB) legacy 目录迁移到 `F0_intake`（红线，需单独规划）。
- **pre-existing**：`test_get_price_routing`（F8 TD-10）本轮未触及。
