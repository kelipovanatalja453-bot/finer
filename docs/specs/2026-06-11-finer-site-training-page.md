# 宣传站并入训练数据叙事（/training 页 + 主页标注训练板块）

## 概述

把 dashboard 最新的「人工标注 · RLHF · DPO 训练数据」前端叙事（commit 3998e721 的 `/training` 页 + landing 未提交修改）优化后并入独立宣传站 `src/finer_site/`（https://finer.t800.click）：新增宣传站 `/training` 静态页、主页 human-loop 板块升级为「标注训练」、提取共享 site chrome 组件、修正三处过时的「contract-only」口径。build / lint / 浏览器渲染全部验证通过。

## 变更清单（全部位于 src/finer_site/）

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/components/landing/site-chrome.tsx` | 新增 | 共享 `SiteHeader`（links 参数化）/ `SiteFooter` / `GitHubMark` / `GITHUB_URL` / `CONTACT_EMAIL`；footer 锚点改 `/#proof`、`/#capabilities` 跨页可用，产品列新增「训练数据 → /training」 |
| `src/app/training/page.tsx` | 新增 | 训练数据叙事页（约 870 行），内容主体移植自 dashboard 版，做宣传站适配（见关键决策） |
| `src/app/page.tsx` | 修改 | nav「AI · 人」→「标注训练」；human-loop 板块插入标注工作台截图 + 「标注台不是外包页面，是训练资产入口」卡（CTA → `/training`、`/demo`）；header/footer 替换为共享组件；删除本地 GitHubMark/常量；3 处「contract-only」过时口径更新；ROADMAP_PLANNED 模型微调描述更新为「地基就绪、待实跑」 |
| `src/app/sitemap.ts` | 修改 | 新增 `/training` 条目（lastModified 2026-06-11, priority 0.7） |
| `public/landing/annotation-workbench.png` | 新增 | 标注工作台截图（复制自 dashboard，**含真实 KOL 转写片段，见未解决项**） |
| `public/landing/training-loops.svg` | 新增 | 环 A / 环 B 双循环示意图（纯示意，无敏感信息） |
| `public/landing/training-metrics.svg` | 新增 | 三项评测指标示意图 |
| `public/landing/training-tracks.svg` | 新增 | 训练/验证双轨道示意图 |

dashboard 侧（`src/finer_dashboard/`）本次未改动；其工作区未提交修改（landing 标注板块、training 页迭代、AnnotationWorkbench lint 修复）保持原样待用户自行提交。

## 架构影响

- 宣传站维持纯静态导出（`output: 'export'`）、零后端依赖约定不变；`/training` 为纯静态叙事页，无 API 调用。
- 路由从 2 个增加到 3 个：`/`、`/demo`、`/training`，sitemap 同步。
- 新增共享组件层 `site-chrome.tsx`：主页与 training 页的 header/footer 单一来源，后续内容页可复用；`SiteHeader` 接受页面级锚点数组。
- 不触碰 `src/finer_dashboard/**`（Round 4 红线），仅从其 public/ 复制静态资产。

## 关键决策

1. **CTA 语境转换**：dashboard 版 CTA 指向内部工具 `/annotation`（宣传站不存在）。宣传站版改为：hero 主 CTA「在演示里体验 F6 复核」→ `/demo`（demo 含模拟 RLHF 提交，语义最贴近）；底部 CTA「在 GitHub 看实现」→ 开源仓库。`EVAL_TRACK` 中 `/annotation` 节点注释改为「标注工作台」。
2. **诚实口径升级而非复制**：主页原有 3 处「训练循环为 contract-only」已被 d91f7204（DPO 半真实数据流水线 + 三指标评测器）证伪，更新为「偏好对流水线与三指标评测器已建成，真实微调待实跑」；Roadmap「模型微调」节点保持未完成状态（真实微调确实未跑），仅描述升级为「地基就绪」。STAGES 表「仅用户可做」等内部协作措辞改为「待实跑」对外口径。
3. **快照数字保留并标注来源**：REAL WORKBENCH 卡的「30 / 9 / 2 / blocked」是内部工作台真实快照，新增一行说明「内部标注工作台真实快照——质量闸把 Formal 导出拦在 gold 不足时，正是我们想展示的工作方式」，把"被闸拦住"转化为工程诚实卖点。
4. **共享 chrome 提取**：避免 header/footer 在两页重复；footer 锚点链接由 `#proof` 改为 `/#proof`，使其从任何路由都能跳回主页板块（ESLint `no-html-link-for-pages` 要求用 `<Link>`，已遵守）。
5. **LCP 优化**：`/training` 首屏大图 `annotation-workbench.png` 的 `ProductFrame` 加 `priority`（Next.js console warning 驱动）。

## 验证结果

```bash
cd src/finer_site && npm run lint    # ✅ 0 errors 0 warnings（修复 2 处 no-html-link-for-pages 后）
cd src/finer_site && npm run build   # ✅ 静态导出 7 路由全 prerendered，含新增 ○ /training
```

浏览器验证（preview @ localhost:4311）：
- `/training`：title「训练数据 · Finer OS」（layout template 生效）；4 张图片资产全部 `naturalWidth > 0`；accessibility snapshot 确认 hero、三类标注任务卡、TRAIN ≠ EVAL、偏好矩阵、双环、指标、轨道、STATUS 表全部渲染；577px 窄屏与 1366px 桌面双栏布局均正常；console 无 error。
- `/`：nav 标签为「标注训练」；4 处 `/training` 链接（板块 CTA / 第三栏 / Roadmap 底注 / footer）；`contract-only` 字样全站清零；human-loop 板块截图 + 文案卡双栏渲染正常。
- 截图过程中遇到 preview 工具 resize 后视口宽度异常（3px）导致空白截图，与页面无关，重启 preview 后复现正常。

## 未解决项

1. **（部署前需用户决策）`annotation-workbench.png` 含真实数据痕迹**：截图原文区有真实 KOL 转写片段（提及「猫大」）及内部数据路径（`data/feishu/.../chat_history_...`）。与宣传站「全部演示数据、无真人」既定约定（docs/specs/2026-06-03-finer-marketing-site.md）存在张力。无密钥/token 泄露，风险为内容版权与 persona 约定一致性。可选处理：(a) 接受现状（片段短、口语化、无身份信息）；(b) 用 demo 数据重截一张；(c) 对原文区做模糊处理。**本次代码已并入但未部署**，部署到 Cloudflare Pages 由用户手动执行。
2. dashboard 工作区的未提交修改（landing/training/AnnotationWorkbench + scripts/tests）不属本任务范围，待用户决定提交时机。
3. README 双语版未同步新增 /training 页的介绍与截图（README 引用 `docs/assets/`，可后续补）。
