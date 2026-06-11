# F0 Intake 运行时修复轮次 · 审阅报告

> **日期**：2026-06-05
> **分支**：`f0-runtime-repair` → `main`（fast-forward，15 commits）
> **基准**：`d4e6c96d`（main pre-merge）→ `2d2c25fc`（main post-merge）
> **规模**：66 files changed, +7276 / -2211 lines
> **验证**：固定顺序（`-p no:randomly`）**2772 passed / 1 pre-existing failed / 15 skipped**（后端，唯一失败 `test_get_price_routing` 为 F8 pre-existing，与 F0 无关）；`npm run build` + `tsc --noEmit` 通过（前端）。⚠️ 随机顺序下存在 order-dependent 测试污染（坏种子触发 ~6 失败 + 连带 error），见 §7.1 / §8

---

## 1. 概述（Overview）

本轮修复将 F0 Intake 层从"测试全绿但运行时全是炸点"修到"6 渠道均可导入、Project Memory 接电、Import Console 可用"。核心工作分 4 个阶段：运行时止血（Phase 1）→ 共享契约冻结 + 6 渠道收口（Phase 2）→ PM 深化（P4-IDP01/P4-COVERAGE）→ 验证债清理（§7）。

---

## 2. 变更清单（Changes）

### 2.1 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/finer/ingestion/f0_index_writer.py` | 235 | PM 单条写入器（确定性 key，幂等，写 contents+source_record+asset_index+artifacts+storage_objects） |
| `src/finer/ingestion/wechat_mp_adapter.py` | 1230 | 从 wechat_adapter.py 拆出的公众号模块 |
| `src/finer/ingestion/wechat_channels_adapter.py` | 530 | 从 wechat_adapter.py 拆出的视频号模块 |
| `src/finer/schemas/import_receipt.py` | 178 | 统一 ImportReceipt 模型（6 渠道复用） |
| `src/finer/utils/time.py` | 43 | `now_utc()` / `ensure_aware_utc()` |
| `src/finer/utils/__init__.py` | — | utils 包入口 |
| `src/finer_dashboard/src/app/api/f0-index/[...path]/route.ts` | 58 | Import Console 前端代理路由 |
| `tests/test_f0_index_writer.py` | 188 | F0IndexWriter 契约测试 |
| `tests/test_files_upload_f0.py` | 341 | 本地上传 E2E 测试 |
| `tests/test_bk1_feishu_nlm_f0.py` | 375 | 飞书+NLM F0 契约测试 |
| `tests/test_import_receipt.py` | 223 | ImportReceipt 序列化/安全测试 |
| `docs/specs/2026-06-04-f0-runtime-audit-and-repair-plan.md` | 295 | 完整审计报告 |
| `docs/specs/2026-06-05-f0-repair-task-cards.md` | 191 | 分阶段任务卡（断点续传真相源） |

### 2.2 修改文件（核心）

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/finer/ingestion/wechat_adapter.py` | 重构 | 1743 行 → 35 行兼容 shim（re-export MP + Channels） |
| `src/finer/ingestion/orchestrator.py` | 修复 | F0-only 收口；Vision/Summary/NLM 解耦留 `F1_HANDOFF_SEAM`；`_register_f0_index` 返回 `bool` |
| `src/finer/ingestion/bilibili_adapter.py` | 修复 | `search_videos()` 从 stub 改为真实 B站搜索 API；`BilibiliAdapter` lazy transcriber |
| `src/finer/ingestion/classifier.py` | 修复 | gemini 硬编码路径 → `shutil.which("gemini")` 动态查找 |
| `src/finer/ingestion/feishu_poller.py` | 修复 | lark-cli 失败分类→canonical FinerError，stderr 不外泄 |
| `src/finer/ingestion/nlm_sync.py` | 修复 | `resolve_nlm_cli()` 用 `shutil.which` 替坏死默认路径；source_type `nlm_source` → `nlm_note` |
| `src/finer/ingestion/bbdown_client.py` | 修复 | 消除两处 F0→F1 ASR 跨层 import |
| `src/finer/ingestion/wechat_exporter_client.py` | 修复 | exporter 端口统一单一真相源 |
| `src/finer/schemas/content.py` | 修复 | `source_type` 补 `wechat_channels_video`；`collected_at` 改 aware UTC |
| `src/finer/paths.py` | 修复 | 既有公共模块；新增 F0 落点 helper（`f0_raw_dir`/`f0_intake_dir`/`f0_record_path`/`f0_receipt_path`）|
| `src/finer/schemas/wechat.py` | 修复 | `l0_triggered` → `f0_triggered` |
| `src/finer/scripts/project_memory_backfill.py` | 修复 | `_random_id("art")` → `_det_id()` 确定性去重 |
| `src/finer/api/routes/files.py` | 修复 | 本地上传产 ContentRecord+ImportReceipt+PM；路径穿越防护 |
| `src/finer/api/routes/files_utils.py` | 新增 | 文件名消毒 + 扩展名白名单 |
| `src/finer/api/routes/wechat.py` | 修复 | 视频号 PM 接线；`_register_f0_index` 返回 `bool`；import 更新 |
| `src/finer/api/routes/bilibili.py` | 修复 | 新增 `POST /import/{bvid}`（F0-only）；`_register_f0_index` 返回 `bool` |
| `src/finer/api/routes/integrations.py` | 修复 | NLM source_type 修正；飞书+NLM F0 收口；`_register_f0_index` 返回 `bool` |
| `src/finer/api/routes/sources.py` | 修复 | 4 处 `HTTPException` → `FinerError`（canonical envelope） |
| `src/finer/api/routes/f0_index.py` | 修复 | `/api/f0-index/records` 对齐 `asset_index` 真实列 |
| `src/finer/api/routes/asset_builder.py` | 修复 | fallback scan 移除 `data/L0_ingest` |
| `src/finer/api/routes/bbdown.py` | 修复 | BBDown 缺 .NET → `F0_EXT_001` + `fix_hint` |
| `src/finer/config.py` | 修复 | exporter 端口统一 |
| `src/finer/scripts/project_memory_migrate.py` | 修复 | `apply_migrations()` 接进 `cli init-storage` |

### 2.3 修改文件（前端）

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/finer_dashboard/src/app/api/f0-index/[...path]/route.ts` | 新增 | Import Console 代理路由 |
| `src/finer_dashboard/src/lib/api-proxy.ts` | 新增 | 通用 API 代理 helper |
| `src/finer_dashboard/src/lib/contracts.ts` | 修复 | `l0_triggered` → `f0_triggered` |
| `src/finer_dashboard/src/components/import-console/ImportConsole.tsx` | 修复 | 区分 404 与空数据 |
| `src/finer_dashboard/src/components/import-console/ImportHistoryTable.tsx` | 修复 | 对齐真实 import_runs 列 |
| `src/finer_dashboard/src/components/import-console/IndexHealthCard.tsx` | 修复 | 真实探活 |
| `src/finer_dashboard/src/components/import-console/SourceChannelStatus.tsx` | 修复 | 硬编码→真实探活 + unknown/checking 态 |
| `src/finer_dashboard/src/components/layout/upload-button.tsx` | 修复 | "SUCCESS" → "已入库 F0"（仅 intake 非解析） |
| `src/finer_dashboard/src/components/data-source-config/WeChatConfig.tsx` | 修复 | 对齐新 API |
| `src/finer_dashboard/src/app/api/wechat/[...path]/route.ts` | 修复 | header 白名单不透传 cookie/auth |
| 13 个代理路由 `route.ts` | 修复 | `BACKEND_ORIGIN` env 化 |

---

## 3. 架构影响（Architecture Impact）

### 3.1 F0 层间边界

**修复前**：F0 混入 F1 职责（飞书 sync_chat 跑 Vision/Summary/NLM、B站 /transcribe 做 ASR、BBDown import F1 ASR）。

**修复后**：
- 飞书 `orchestrator.sync_chat` 解耦 Vision/Summary/NLM，留 `F1_HANDOFF_SEAM` 标记
- B站 `/transcribe` 移出 F0 标 F1-adjacent；`BilibiliAdapter` lazy transcriber，缺 DashScope 不崩
- BBDown 两处 F1 ASR 跨层 import 消除
- F0 只输出 `ContentRecord` + raw archive + `ImportReceipt` + PM 行，不做 OCR/ASR/Summary/Intent/TradeAction

### 3.2 Project Memory 接电

**修复前**：PM SQLite 空库（0 张表），`/api/files` 每次全盘 `os.walk` 650MB `data/L0_ingest`。

**修复后**：
- `F0IndexWriter.record_imported()` 幂等写入 contents + source_record + source_content_links + stage_status + asset_index + storage_objects + artifacts（确定性 key，重复调用无副作用）
- 6/6 渠道 happy path 均调 `_register_f0_index` → PM
- `asset_builder` fallback scan 移除 `data/L0_ingest`
- Import Console `/api/f0-index/health` 返回真实 PM 健康状态

### 3.3 统一 ImportReceipt 契约

**修复前**：各渠道自建 receipt 形态（飞书群通知、视频号手写 dict、B站手写 dict），无统一 Pydantic model。

**修复后**：`schemas/import_receipt.py` 定义 `ImportReceipt`，6 渠道复用。`to_import_run()` 无损投影前端 `ImportRun`。递归校验无 token/secret/password/cookie/authorization/api_key 泄露。

### 3.4 错误规范化

**修复前**：依赖缺失裸崩 / 误报成功 / 静默空态。

**修复后**：canonical `FinerError` envelope（`request_id` / `stage` / `operation` / `retryable` / `fix_hint` / `source_channel`）。所有外部依赖缺失均有 fix_hint 指引用户修复。

### 3.5 WeChat 模块拆分

**修复前**：`wechat_adapter.py` 1743 行（公众号 + 视频号混杂）。

**修复后**：
- `wechat_mp_adapter.py`（1230 行）— 公众号
- `wechat_channels_adapter.py`（530 行）— 视频号
- `wechat_adapter.py`（35 行）— 兼容 re-export shim

---

## 4. 关键决策（Key Decisions）

### 4.1 `_register_f0_index` best-effort + 返回 bool

选择保留 best-effort 模式（失败不阻塞导入），但改为返回 `bool`，使调用方能感知 PM 写状态。原因：导入成功是核心保证，PM 是热索引可重建——不能因 PM 故障丢弃已落盘的 ContentRecord。

### 4.2 `_det_id` 确定性去重键

F0IndexWriter 和 backfill 统一使用 `sha256(prefix:parts)[:16]` 生成 artifact/object ID，替代 backfill 的 `_random_id("art")`。原因：随机 ID 导致重复 backfill 累积 `is_canonical=0` 历史行（371→742），确定性 key 使 `INSERT OR IGNORE` 天然幂等。

### 4.3 wechat_adapter 兼容 shim

拆分后保留 `wechat_adapter.py` 作为 re-export shim，而非强制所有外部 import 迁移。原因：`scripts/` 下有非受控脚本引用旧路径，shim 零成本且避免外部断裂。

### 4.4 `_build_wechat_channels_receipt` → `ImportReceipt`

视频号 receipt 从 plain dict 改为 `ImportReceipt` Pydantic model。原因：dict 无法通过 `F0IndexWriter.record_imported()` 注册 PM（签名要求 `ImportReceipt`），且 dict 缺少 schema 校验。

### 4.5 gemini `shutil.which` 而非 LLM 注册表

classifier 的 gemini 调用改为 `shutil.which("gemini")` 而非迁入项目 LLM 注册表。原因：gemini CLI 是 local binary subprocess 调用（`gemini -p "prompt"`），不是 HTTP API，放注册表语义不对。

---

## 5. 冻结契约（Frozen Contracts）

以下契约在本轮冻结，下游不得私自扩展（注：`f0_index_writer.py` 的"冻结"指**禁止渠道 agent 私自改**；本轮经专门卡 P4-IDP01 受控扩展过——加 artifact 确定性去重键，属协调内演进，非违例）：

```python
# PM 单条写入器
from finer.ingestion.f0_index_writer import F0IndexWriter
F0IndexWriter().record_imported(record, receipt)  # 幂等，写全链

# 统一 receipt
from finer.schemas.import_receipt import ImportReceipt
receipt.to_import_run()  # 无损投影前端 ImportRun

# F0 落点
from finer.paths import f0_raw_dir, f0_intake_dir, f0_record_path, f0_receipt_path

# 时间
from finer.utils.time import now_utc, ensure_aware_utc

# source_type frozen literal
ContentRecord.source_type  # 含 wechat_channels_video / nlm_note / manual_upload 等
```

---

## 6. 6 渠道终态表

> 注：「ContentRecord / ImportReceipt / PM 写入 ✅」表示**代码路径已接线并通过单元测试**；除本地上传已 E2E 实证（§7.4）外，其余 5 渠道的真实 E2E 待用户完成环境（见 §8），尚未端到端跑通。

| 渠道 | 入口 | ContentRecord | ImportReceipt | PM 写入 | 优雅降级 |
|------|------|:---:|:---:|:---:|:---:|
| 本地上传 | `POST /api/files` | ✅ | ✅ | ✅ | ✅ 路径穿越拦截 + size/ext 白名单 |
| 飞书 (f0_importer) | `orchestrator.import_feishu_files` | ✅ | ✅ | ✅ | ✅ `FEISHU_AUTH_001` + fix_hint |
| 飞书 (sync_chat) | `orchestrator.sync_chat` | ✅ | ✅ | ✅ | ✅ F0-only，Vision/Summary 解耦 |
| NotebookLM | `POST /api/integrations/nlm/fetch` | ✅ | ✅ | ✅ | ✅ CLI 缺失→`NL_001` + fix_hint |
| 微信公众号 | `POST /api/wechat/sync/{id}` | ✅ | ✅ | ✅ | ✅ exporter 离线→`WX_EXT_001` |
| 微信视频号 | `POST /api/wechat/channels/import` | ✅ | ✅ | ✅ | ✅ binary 缺失→`F0_EXT_001` |
| B站 | `POST /api/bilibili/import/{bvid}` | ✅ | ✅ | ✅ | ✅ .NET 缺失→`F0_EXT_001`；transcribe F1-adjacent 不阻塞 |

---

## 7. 验证结果（Verification）

### 7.1 后端

```bash
pytest tests/ -q -p no:randomly   # 固定顺序，消除 pytest-randomly 干扰
# 1 failed, 2772 passed, 15 skipped
```

**固定顺序下只有 1 个失败**：`test_get_price_routing`（F8 backtest，`MockPriceProvider` / TD-10），在父提交 `d4e6c96d` 上同样失败 → 确认 **pre-existing 且与 F0 无关**。

> ⚠️ **更正**：本报告早前版本写"2707 passed / 7 failed，7 个全是 pre-existing"——此为**随机顺序（项目装了 `pytest-randomly`）的不稳定结果**，不可采信。坏种子下会触发 **order-dependent 测试污染**：约 6 个本应通过的测试失败（3× F1 `test_manifest_driven_assertions`、3× MiMo `test_mimo_vision_config` / `test_missing_key_produces_canonical_envelope`）+ 连带 error 约 54 个测试（passed 从 2772 掉到 2707）。这些测试**单独跑、固定顺序跑均通过**——属某测试不清理全局状态导致的污染，非稳定失败、非全部 pre-existing。需单独排查（见 §8 + 任务卡 §7）。

### 7.2 前端

```bash
cd src/finer_dashboard && npm run build   # ✅
cd src/finer_dashboard && npx tsc --noEmit # ✅
```

### 7.3 PM 幂等性

`F0IndexWriter.record_imported()` 重复调用 → 所有表行数稳定（contents / source_records / source_groups / content_identities / stage_status / asset_index / artifacts / storage_objects）。

### 7.4 E2E 本地上传

TestClient 上传 → ContentRecord + ImportReceipt + PM `asset_index` +1 + sourceRecordId 非空 + 路径穿越拦截（`../../etc/passwd` → 400 `F0_IO_001`）。

---

## 8. 未解决项（Open Issues）

| 项 | 优先级 | 说明 |
|---|---|---|
| P3 渠道 E2E | 中 | 6 渠道代码已收口，但 E2E 需用户完成环境（飞书 token / .NET 8 / DashScope key / exporter / nlm login / wx binary） |
| P6-WXVENDOR | 低 | `scripts/wx_channels_download/` vendored 目录（GPLv3 + MITM root CA）发布风险，需用户确认删除 |
| P6-L0MIGRATE | 低 | `data/L0_ingest` 650MB legacy 数据迁移/归档，需用户确认 |
| `_register_f0_index` 吞错可见性 | 低 | 当前返回 `bool` 但调用方尚未消费；P4-COVERAGE 已确认 6 渠道 happy path 均落 PM 行 |
| wechat_adapter shim 清理 | 低 | 兼容 shim 保留，外部脚本迁移后可删除 |
| **order-dependent 测试污染** | **中** | 随机顺序坏种子触发 ~6 失败 + 连带 error ~54 测试（passed 2772→2707）；单独跑/固定顺序全过。需排查哪个测试泄漏全局状态（env / singleton / monkeypatch / cwd）。疑似本轮新测试引入（中途 b1ce1495 全量仅 1 失败）。见任务卡 §7。 |

---

## 9. 对下游 Agent 的影响

### F1 Standardize

- F0 产出 `ContentRecord` + raw archive 在 `data/F0_intake/{channel}/` 和 `data/raw/`
- `orchestrator.F1_HANDOFF_SEAM` 标记飞书 Vision/Summary 需 F1 阶段消费
- B站 transcribe 标 F1-adjacent，F1 可按需调用 `mimo_asr_client`
- **不得在 F0 路径重新挂回 Vision/Summary/ASR 调用**

### F2+ 各层

- `ContentRecord` schema 新增 `wechat_channels_video` source_type
- `ImportReceipt` 是 F0 专属，F2+ 不消费
- PM `asset_index` 可查所有已导入内容（`AssetIndexService.list_assets(stage="F0")`）

### 前端 Dashboard

- Import Console 代理路由 `/api/f0-index/[...path]` 已就位
- `contracts.ts` 中 `WeChatSyncResult.f0_triggered`（原 `l0_triggered`）
- 所有代理路由使用 `BACKEND_ORIGIN` env 变量，不再硬编码 localhost

### 测试

- 固定顺序 2788 收集 / 2772 通过 / 1 pre-existing 失败（随机顺序受测试污染影响，见 §7.1）
- F0 相关新增测试：`test_f0_index_writer.py`（188 行）、`test_files_upload_f0.py`（341 行）、`test_bk1_feishu_nlm_f0.py`（375 行）、`test_import_receipt.py`（223 行）
- 所有 `_register_f0_index` 调用在测试中 patch 为 no-op（避免写 live PM DB）

---

## 10. 提交链（Commit Log）

```
2d2c25fc docs(f0): mark §7 verification debt fully resolved
b2735445 fix(f0): search_videos real B站 API + classifier gemini dynamic lookup
15d0ab0b refactor(f0): split wechat_adapter.py into MP + Channels modules
853ef016 docs(f0): mark P4-COVERAGE DONE — 6/6 channels PM coverage
f680a700 fix(f0): wire wechat channels import to Project Memory
37b30ca0 docs(f0): update task cards — P4-IDP01 + §7 items 1,5 DONE
c9892ffb fix(f0): rename l0_triggered → f0_triggered + _register_f0_index returns bool
5cc2b6ae docs(f0): mark P4-IDP01 DONE + Line V verification results
6e86b2a5 feat(f0): P4-IDP01 — artifacts deterministic dedup key + backfill fix
57f173ba docs(f0): 分阶段任务卡（断点续传真相源）+ 剩余 Phase 3-6
b1ce1495 docs(f0): phase-2 执行记录 + F0 渠道终态对照表 + 遗留项
b32e7286 feat(f0): phase-2 batch-B — feishu+NLM / bilibili F0 收口 + 优雅降级
3f3ad4bd feat(f0): phase-2 batch-A — local upload + wechat F0 收口 + intake UX
505fb9bb feat(f0): phase-2 GATE — freeze shared F0 contracts
8ff2b16c fix(f0): phase-1 runtime repair — wire Project Memory catalog + Import Console proxy
```
