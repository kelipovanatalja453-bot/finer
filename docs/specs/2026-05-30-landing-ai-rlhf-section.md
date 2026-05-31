# 宣传站：新增「AI · 人在回路」分区 + 管线条角色标识 — 审阅报告

> 日期：2026-05-30
> 范围：`src/finer_dashboard/src/app/landing/page.tsx`、`src/finer_dashboard/src/components/landing/pipeline-strip.tsx`、新增 `public/landing/review.png`
> 关联：[2026-05-29 前端打磨与宣传站](2026-05-29-frontend-redesign-and-landing.md)、[2026-05-30 后端评级与年化修正](2026-05-30-backend-rating-determinism-and-annualization-cap.md)
> 作者：Claude Code（frontend implementer）

## 1. 概述（Overview）

在宣传站补上 Finer 最具识别度的产品叙事——**AI 抽取 + 人类裁决 + 反馈成为训练数据**——之前的宣传站只在 engineering 卡片里以一行 "LLM 工程" 带过，过于轻描淡写，且没有把 RLHF 作为系统的可信度核心讲清楚。

同时给 F0-F8 管线条每个 stage 加上小角色徽章（AI / 人 / 规则），让读者一眼读出系统在哪儿是确定性的、哪儿是 LLM 的、哪儿是人类裁决的。

## 2. 变更清单（Changes）

| 文件 | 变更 |
|---|---|
| `src/finer_dashboard/src/components/landing/pipeline-strip.tsx` | 重写：为 9 个 stage 各加 `role: "AI" \| "人" \| "规则"` 字段，渲染 stage id 右侧小徽章；最小宽度 760→820；strip 底部追加 Role 图例（AI 红 / 人 金 / 规则 灰）。 |
| `src/finer_dashboard/src/app/landing/page.tsx` | 新增 `#human-loop` 分区（介于 capabilities 与 engineering 之间）；NAV_LINKS 加入 "AI · 人" 锚点；导入 `Sparkles` / `UserCheck` / `RotateCw` 图标；engineering section className 微调（撤销试做的 strong-band 包装，回到原 paper bg，避免与下游 gallery 两个 strong 撞色）。 |
| `src/finer_dashboard/public/landing/review.png`（新增） | 1440×900 截图：工作台 `?tier=F6` 真实 review queue，左栏 Review 选中、卡片带 F6 红色 NEEDS REVIEW 徽章、右栏 Inspector 显示 Current Stage F6。 |

净增前端代码约 +155 行（page.tsx），pipeline-strip.tsx 全文重写约 90 行。

## 3. 新分区结构（Architecture Impact）

`#human-loop` 分区由四块组成（自上而下）：

1. **Eyebrow + 标题 + 引言** — 一句话锁定叙事："AI 抽取，人类裁决，反馈成为训练数据"。
2. **三列概念卡**（同等权重，hard top-rule）
   - **AI 做什么**（top-rule = `--foreground`，AI 红徽章）：列出 F1 / F1.5 / F3 / F5 各阶段 LLM 的具体职责。
   - **人在哪儿介入**（top-rule = `--accent-gold`，人金徽章）：F6 RLHF 复核台，1-5 星评分、is_correct、字段级修正、reviewer 审计。
   - **反馈如何沉淀**（top-rule = `--foreground`，反馈灰徽章）：持久化为 RLHFFeedback 记录、`GET /api/rlhf/export` 导出 DPO 训练数据，**明确标注训练循环为 contract-only、模型微调尚未启动**。
3. **RLHF Loop 闭环条**（surface-strong 框）：四步流程 `AI 抽取 → 人工裁决 → RLHFFeedback → DPO 训练数据`，框头标 endpoint `POST /api/rlhf/submit → GET /api/rlhf/export`；底部脚注重申训练 contract-only。
4. **下半：schema 预览卡 + F6 真截图（2 列）**
   - 左：`RLHFFeedback` schema 字段表，monospace 字段名 + 示例值（rating=4/5、is_correct=true、corrected_direction=bearish→bullish、corrections、review_notes、reviewer_id、reviewed_at），脚注标明字段来源 `src/finer/schemas/trade_action.py:RLHFFeedback`。
   - 右：F6 工作台真截图（ProductFrame 框，地址栏 `finer.os / workbench?tier=F6`）。

## 4. 关键决策（Key Decisions）

1. **不说「模型已被你的反馈训练」**——这是 Finer 最容易被夸大但实际不属实的话术。三处反复点明 DPO 训练循环为 contract-only：概念卡里、Loop 条脚注里、Loop 条 endpoint 标记里。
2. **F2 标 "规则"，F5 标 "AI"，是有意识的简化**——F2 实体解析以 entity_registry 规则为主、LLM 为辅；F5 trade action 由 LLM 抽取 + 规则约束，但 LLM 是主动贡献者。单徽章必须二选一，按主导力量标。
3. **schema 卡用 `RLHFFeedback` 而不是 `ReviewPayload`（前端类型）**——前者是后端真实存盘字段，更有可信度；脚注里点明出处文件路径，读者可自己核对。
4. **F6 截图选 workbench tier=F6（review queue）而非 RLHFReviewPanel 模态**——modal 需要交互 + 客户端状态才能截，playwright CLI 不支持；queue 视图已经能传达"红色 NEEDS REVIEW 卡片"的语境，且不需要为截图改动应用代码（添加 `?studio=open` 这类 deep-link）。
5. **角色徽章只用三个值（AI / 人 / 规则），色阶克制**——更细的分类（"AI+规则" / "规则+人审" 等混合标）会让管线条视觉混乱；单一徽章配 Role 图例足够传达模式。
6. **新分区放 capabilities 与 engineering 之间**——位置上承接"四个不可约能力"（产品向）、下启"工程上认真对待『可信』"（招聘向）。AI/RLHF 章节既是产品叙事也是工程叙事，居中桥接。

## 5. 验证结果（Verification）

```bash
cd src/finer_dashboard
npx tsc --noEmit      # 干净
npm run lint          # 0 warning（修掉了一次试做时引入的 Database unused import）
npm run build         # 通过，/landing 仍为 ○ static 路由
```

视觉验证（playwright CLI，已留为 /tmp/landing-{full,mobile}-v2.png）：

- **桌面 1440×5200**：新分区在 capabilities 与 engineering 之间清晰展开，三列概念卡的 top-rule 色块（红/金/灰）成功传达三个角色；RLHF Loop 条四步带箭头；schema 卡与 F6 截图并排，schema 字段表读起来像真实记录。
- **移动端 390×8200**：新分区单列堆叠，三概念卡纵向；Loop 条 4 个 box 在 sm 断点变 2 列；schema + 截图也单列。无溢出。

## 6. 未解决项（Open Issues）

1. **F6 截图是 queue 视图，不是真正的 RLHFReviewPanel modal**。要展示 modal 必须给 `app/page.tsx` 加 `?studio=open&asset=...` deep link 才能 playwright 截图。可作为后续小迭代；当前 queue 截图已胜任。
2. **schema 卡用静态示例值**。如果以后要展示真实匿名化的 RLHF 记录，可以从 `data/review/{kol_id}/F6_review/` 选一条真实 feedback 渲染。当前静态值更克制。
3. **AI · 人在回路分区未在沿用 [2026-05-29 前端打磨 doc §6](2026-05-29-frontend-redesign-and-landing.md#6-未解决项open-issues) 列出的旧债（compare de-mock / kol-rating-card 配色 / inspector 软卡 / 工作台移动端）方面有任何推进**——这一轮只新增了 RLHF 叙事，那些遗留债仍在。
4. **管线条角色标识可读性**：在小屏（< 820px 横向滚动）边缘 stage 的 role chip 与下一个 stage 的箭头略挤。已设最小宽度 820 触发横向滚动，可读但不够舒展。如果将来 stage 数量再增加（如显式 F1.5）需重新设计紧凑布局。
