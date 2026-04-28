# F-Stage 架构迁移、Intent 提取重写与图片预览修复

## 概述

将 finer OS 前端和后端的层级命名从 L0-L8 统一迁移至 F0-F8 规范体系；重写 intent_extractor 以支持章节分组与实体注册表联动；修复前端图片预览因路径优先级导致的无法显示问题。

## 变更清单

| 文件 | 变更 | 说明 |
|---|---|---|
| `src/finer/api/routes/files_utils.py` | 修改 | WORKFLOW_BY_TIER / STAGE_BADGE_BY_WORKFLOW 映射表新增 F-tier key，保留 L-tier 向后兼容 |
| `src/finer/api/routes/files.py` | 修改 | 默认 tier Query 参数 `L2` → `F1`；上传响应 stageBadge `L0` → `F0` |
| `src/finer/api/routes/asset_builder.py` | 修改 | fallback stageBadge `L2` → `F1` |
| `src/finer/extraction/intent_extractor.py` | 重写 | 从逐块处理改为 H2 章节分组；集成 entity_registry 字符串匹配；新增 entity_anchors 回退 |
| `src/finer/entity_registry.py` | 修改 | 新增 理想汽车(LI)、宝丰能源(600989.SH)、阿特斯/CSIQ、绿电/算电协同 等实体 |
| `src/finer/parsing/content_standardizer.py` | 修改 | 适配 F-stage 命名与输出格式 |
| `src/finer_dashboard/src/app/page.tsx` | 修改 | WORKFLOW_VIEWS 全部改用 F-tier；默认 tier `L2` → `F1`；所有条件判断 `L1`→`F2` `L5/L6`→`F5/F6` |
| `src/finer_dashboard/src/app/api/files/route.ts` | 修改 | 默认 tier `L2` → `F1` |
| `src/finer_dashboard/src/components/layout/sidebar.tsx` | 修改 | 导航项全部改为 F0-F8；标签更新为 Intake/Standardize/Anchor/Execute/Review/Backtest |
| `src/finer_dashboard/src/components/layout/inspector-panel.tsx` | 修改 | provenanceSteps 改为 F-tier；图片预览路径修复（见关键决策）；`tier.replace("L","")` → `tier.replace("F","")` |
| `src/finer_dashboard/src/components/layout/main-board.tsx` | 修改 | 默认 tier `L0` → `F1` |
| `src/finer_dashboard/src/components/layout/integrations-hub.tsx` | 修改 | 导入按钮文字 `L0` → `F0` |
| `src/finer_dashboard/src/components/data-source-config/BilibiliConfig.tsx` | 修改 | 转录完成路径 fallback `L0` → `F0` |
| `src/finer_dashboard/src/components/studio/annotation-workbench.tsx` | 修改 | stageBadge fallback `L6` → `F6` |
| `tests/test_cat_lord_pipeline_integration.py` | 新增 | 22 个测试覆盖满 cat lord fixture 的完整流水线（standardize → extract intents） |
| `docs/architecture-v2-migration-map.md` | 新增 | F-stage 迁移对照表 |
| `docs/specs/f-stage-contracts.md` | 新增 | F-stage 各层数据契约定义 |

## 架构影响

### 分层命名体系

```
F0 (Intake)    → workflow: "intake"     → 数据目录: L0_ingest / raw
F1 (Standardize)→ workflow: "library"    → manifests 索引
F2 (Anchor)    → workflow: "enrichment"  → 数据目录: L1_enrichment
F5 (Execute)   → workflow: "extraction"  → candidate events
F6 (Review)    → workflow: "review"      → L6_annotated
F8 (Backtest)  → workflow: "backtest"    → backtests / L8_metrics
```

- `STAGE_BADGE_BY_WORKFLOW` 将 workflow name 映射为 F-stage badge 显示在 UI
- `WORKFLOW_BY_TIER` 同时接受 F-tier 和 L-tier key，保证 API 向后兼容
- 数据目录名未改（`L0_ingest` 等），避免数据迁移风险

### Intent 提取器数据流

```
ContentBlock[] 
  → _group_into_sections()          # 按 H2 标题分组
    → _extract_entity_from_heading() # 从标题查 entity_registry
    → _find_entities_in_text()       # 从正文匹配已知实体名
  → LLM 调用（section 级别，非 block 级别）
  → NormalizedInvestmentIntent[]     # 含正确 target_type 映射
```

- entity_registry 中的 `entity_type: "ticker"` 需要映射为 `NormalizedInvestmentIntent.target_type: "stock"`（`_REGISTRY_TYPE_TO_TARGET_TYPE`）
- `_is_skip_block()` 阈值设为 `len(text) < 4`，过滤时间戳等元数据块
- 无 H2 标题时回退为逐块处理（保证 12 个现有测试通过）

## 关键决策

1. **保留 L-tier backward compat 而非直接删除**：WORKFLOW_BY_TIER 同时保留 `"L0"`/`"F0"` 映射。理由：CLI 脚本、内部日志、旧 API 调用方可能仍使用 L-key。后续可逐步废弃。

2. **图片预览优先 sourcePath 而非 evidencePath**：`inspector-panel.tsx:119-124`。对于 `type` 为 png/jpg 等图片格式的资产，`sourcePath` 指向原始图片文件，`evidencePath` 指向 OCR 生成的 `.md` 文本。旧代码 `evidencePath || sourcePath` 导致预览时显示 markdown 文本而非图片。新逻辑：图片类型用 `sourcePath || evidencePath`，其他类型保持原逻辑。

3. **Intent 提取改为 section 粒度而非 block 粒度**：cat lord fixture 的每个 H2 标题对应一个标的（理想汽车、宝丰能源...），一个 section 内多个 block 共同描述同一个 intent。按 block 提取会导致碎片化和实体识别丢失。

## 验证结果

```bash
# 后端测试
pytest tests/ -v
# 结果：全部通过（含 12 个已有 intent_extractor 测试 + 22 个新增集成测试）

# 前端构建
cd src/finer_dashboard && npm run build
# ✓ Compiled successfully

# 图片预览端到端
curl -sI "http://localhost:3000/api/streams/download?path=..." | grep content-disposition
# → content-disposition: inline (浏览器内联显示)
# → Content-Type: image/png
# → HTTP 200, 517KB

# API F-tier 兼容
curl -s 'http://127.0.0.1:8000/api/files?tier=F1' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['workflow'], len(d['files']))"
# → library 202  (正确)
```

## 未解决项

- 数据目录名仍为 `L0_ingest`/`L1_enrichment` 等，未重命名为 F 前缀。当前代码直接硬编码旧目录名，如需统一需全量迁移 `data/` 目录结构
- intent_extractor 对无 H2 标题的文档走逐块回退模式，LLM 调用量可能偏高（n 个 block = n 次 LLM 调用）
- F3(Intent) / F4(Policy) / F7(Timeline) 三个层级尚未有对应 UI 视图和后端 workflow
