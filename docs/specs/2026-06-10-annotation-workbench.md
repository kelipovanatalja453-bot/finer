# 标注工作台（Annotation Workbench）— DPO 人工标注前端系统

> 最后更新: 2026-06-10
> 状态: 已实现并验证（后端 + 前端 + held-out 任务源已生成）
> 关联: [DPO 百炼训练线](2026-06-07-dpo-bailian-training-line.md)（本工作台解锁其 §13 第 2/5 步的人工环节）

## 1. 概述（Overview）

在 finer_dashboard 内自建轻量人工标注工作台（`/annotation`），支撑 DPO 训练线当前仅剩的两个人工环节：**held-out 评测集 gold 标注**（产出 `eval_set.jsonl` 供 `eval_compare.py` 消费）与 **DPO 偏好对 chosen 侧抽检**（产出 `pairs_cleaned.jsonl` 供 `to_bailian.py` 消费）。不引入外部标注平台（Label Studio/doccano 等），交互借鉴 doccano 键盘驱动单任务流 + Label Studio 任务队列模式。

## 2. 关键决策（Key Decisions）

1. **自建而非集成开源平台**。标注对象是「中文段落 → 结构化表单」，无图像框选/span 标注需求；Label Studio Frontend（React+MST）嵌入 Next.js 16 + React 19 有依赖冲突风险，doccano 需独立 Django 部署 + 数据桥。自建直接对齐 `TradeDirection`/`ActionType` 枚举真相源与 `eval_set.jsonl` 契约，零转换层，单人规模运维成本最低。
2. **文件即真相源，不加 SQLite 表**。标注落盘为 append-only JSONL（按 id last-wins 合并），可重建、可 diff、不触碰「新增 SQLite 表需用户确认」红线。
3. **eval 任务源不回退训练集**。`data/dpo/eval/passages.jsonl` 缺失时只给 fix_hint，**不**回退 `candidates.jsonl` —— 守护 spec §5.3「评测集独立来源」防自我循环红线。
4. **导出时做 train/eval 泄漏检查**。eval 导出对照 `pairs.jsonl` 的 `passage_id` 求交集，重叠 id 在 API 响应与前端黄色警告中点名。
5. **导出不写 `prompt` 字段**。`run_inference.py` 的 `prompt_of()` 优先读 `item['prompt']`、缺省走 canonical `format_dpo_prompt` —— 不写 prompt 强制评测推理与训练用同一模板，防 prompt 分叉（呼应 F6 映射 spec §7 的已知不一致）。
6. **held-out 来源的务实兜底**。9you 聊天记录几乎全图片消息（8 块、0 段达标）、`maodaren/transcripts` 与训练用 feishu 导出同内容（文件名一致，用之即泄漏）、wechat 为测试桩。故采用 spec Open Issues 预许的「不同种子的半真实」：同 feishu 源 `--min-signal 1` 放宽选段（399 段池）→ **排除训练集 150 个 id** → 取 30 段，段落级零重叠 + 导出泄漏检查双保险。待环 B 真实数据就绪后替换为真人精选。
7. **抽检语义：未审对子原样保留**。`pairs_cleaned.jsonl` 导出时 reject 剔除、edit 替换 chosen、accept/未审保留——抽样质检不要求全量过审；编辑后 chosen==rejected（丧失偏好信号）的对子自动剔除。
8. **标注质量防锚定**。eval 表单 direction/ticker 不给默认值（强制人工判断）；仅弃权快捷路径（A 键）预填 NONE/watchlist，可改。conviction 档位 0.3/0.45/0.6/0.8 对齐迭代 2 校准器分级。

## 3. 变更清单（Changes）

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/finer/schemas/annotation.py` | 新增 | GoldActionStep/GoldExtraction/EvalGoldAnnotation/PairReviewAnnotation/AnnotationTaskSummary；枚举导入 `trade_action.py` 不重定义 |
| `src/finer/services/annotation_store.py` | 新增 | AnnotationStore：任务源读取、标注 append + last-wins 合并、两类导出、泄漏检查、任务摘要 |
| `src/finer/api/routes/annotation.py` | 新增 | `GET /tasks`、`GET /items`、`POST /submit`、`POST /export`；Line F canonical FinerError（stage="F+"） |
| `src/finer/api/server.py` | 修改 | 注册 `/api/annotation` 路由（2 行） |
| `tests/test_annotation_store.py` | 新增 | 13 项：summaries/upsert/契约/泄漏/verdict 导出 |
| `tests/test_annotation_api.py` | 新增 | 6 项：端点 roundtrip + 错误封装（request_id/stage/fix_hint） |
| `src/finer_dashboard/src/lib/contracts.ts` | 修改 | 追加 Annotation 类型组（snake_case 对齐 Pydantic） |
| `src/finer_dashboard/src/app/api/annotation/[...path]/route.ts` | 新增 | Next.js 纯代理（复制 rlhf 模式） |
| `src/finer_dashboard/src/components/annotation-workbench/AnnotationWorkbench.tsx` | 新增 | 主工作台：任务 tab/进度/导航/提交/导出/泄漏警告 |
| `src/finer_dashboard/src/components/annotation-workbench/EvidenceCard.tsx` | 新增 | 原文卡，数字自动高亮（价位溯源辅助） |
| `src/finer_dashboard/src/components/annotation-workbench/EvalGoldForm.tsx` | 新增 | gold 表单：A 弃权 / 1-5 方向 / conviction 档位 / action chain 编辑器 / Enter 提交 |
| `src/finer_dashboard/src/components/annotation-workbench/PairReviewCard.tsx` | 新增 | rejected vs chosen 对照；A/E/R verdict；edit 模式 JSON 校验 |
| `src/finer_dashboard/src/app/annotation/page.tsx` | 新增 | 页面入口 |
| `src/finer_dashboard/src/components/layout/header.tsx` | 修改 | 导航加「标注」入口 |
| `data/dpo/eval/passages.jsonl` | 生成 | 30 段 held-out 任务源（与训练集 id 零重叠；数据文件不入 git） |

## 4. 架构影响（Architecture Impact）

- **F-stage**：F+ Training Loop / F6 Review 支撑面；消费 `data/dpo/**`，不改 F0-F8 主链路、不触碰既有 schema。
- **数据流**：`passages.jsonl → /annotation 标注 → annotations.jsonl → export → eval_set.jsonl →（run_inference → eval_compare）`；`pairs.jsonl → 抽检 → pairs_review.jsonl → export → pairs_cleaned.jsonl →（to_bailian → 百炼）`。
- **API 契约**：`{ok, data}` 成功封装；错误走 Line F canonical envelope（`request_id/stage/operation/retryable/fix_hint`）。
- **与 RLHFReviewPanel 的边界**：环 B（真实 F5 抽取审核纠错）仍归 RLHFReviewPanel；本工作台只管环 A 的评测集 gold 与 pairs 抽检，不重复建审核台。

## 5. 验证结果（Verification）

| 命令/检查 | 结果 |
|---|---|
| `pytest tests/test_annotation_store.py tests/test_annotation_api.py -v` | **19 passed** |
| `pytest tests/ -q`（全量） | 2736 passed, 7 failed —— 7 个失败均为既有问题：`test_backtest_extended` 价格路由在 `git stash` 基线上同样失败；`test_mimo_vision_config` 3 项单独运行全过（测试间污染，项目已有 P4-POLLUTION 卡跟踪）；均与本次改动无关 |
| `npx tsc --noEmit` | 0 error |
| `npm run build` | 通过，`/annotation` 页面在产物中 |
| 浏览器验证（preview + 真实后端 :8000） | 两任务 tab 正确加载（eval 0/30、pairs 0/150 真实数据）；eval 未就绪态正确显示 fix_hint；pairs 卡 rejected/chosen 双栏渲染、原文数字高亮（15/18-20/73%/115%）；eval 表单全字段渲染；console 零错误 |
| held-out 任务源 | `data/dpo/eval/passages.jsonl` 30 段，与 `candidates.jsonl` 150 id 零重叠 |

## 6. 使用方式（Runbook 接入）

```bash
# 后端 + 前端
uvicorn finer.api.server:app --reload --port 8000
cd src/finer_dashboard && npm run dev
# 浏览器打开 http://localhost:3000/annotation
# 任务一「评测集 Gold 标注」：30 段，A=弃权 1-5=方向 Enter=保存下一条；标完点「导出 eval_set.jsonl」
# 任务二「DPO 偏好对抽检」：A=合格 E=修正 R=剔除；抽样审后点「导出 pairs_cleaned.jsonl」
```

导出产物直接接 DPO spec §13 Runbook 第 6-7 步（run_inference → eval_compare）。

## 7. 未解决项（Open Issues）

- held-out 任务源当前为「同源不同段」兜底（决策 6），分布与训练集同质；环 B 真实数据就绪后应换真人精选的独立来源评测集。
- 抽检任务无抽样器（当前顺序浏览 150 条）；如需随机抽样 n 条可后续加 `?sample=30` 参数。
- 标注无多人协作/标注者 id 字段（单人场景够用；多人需加 reviewer_id 与 IAA 统计）。
- preview 截图工具渲染异常（细长条），视觉回归仅靠 accessibility snapshot；不影响功能。
- `pairs_cleaned.jsonl` 的 `meta.review_verdict` 字段为追溯用，`to_bailian.py` 不消费（已验证其只读 prompt/chosen/rejected）。
