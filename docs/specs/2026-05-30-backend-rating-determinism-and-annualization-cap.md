# 后端：KOL 评级确定性 + 年化口径修正 — 审阅报告

> 日期：2026-05-30
> 范围：`src/finer/api/routes/kol.py`、`src/finer/backtest/engine.py`
> 触发：[docs/specs/2026-05-29-frontend-redesign-and-landing.md](2026-05-29-frontend-redesign-and-landing.md) §6 未解决项 #1、#2（宣传截图可信度前提）
> 作者：Claude Code（backend implementer）

## 1. 概述（Overview）

修复两个让宣传截图不可信的后端数据问题：

1. **评级端点非确定性** —— `GET /api/kol/rating/{kol_id}` 在缺少 F5/F6 action 数据时调用 `_generate_mock_rating()`，其中 6 处 `random.random()` 导致同一 KOL 每次调用返回不同评分、维度、观点数。
2. **年化收益外推夸张** —— `BacktestEngine._calculate_metrics()` 对任意周期套 `(1+r)^(1/years)`，把 67 天 17% 算成年化 +135%，把 67 天 21% 算成 +187%。数学正确、口径误导。

修复后：

- KOL 评级在缺 action 时改用**真实回测产物**（`data/review/{kol_id}/F8_backtest/backtest_result.json`）派生，全程确定性；都缺时返回**确定性空响应**，不再 random。
- `/api/kol/list/enriched` 同时扫描 review 目录，让仅有回测的 KOL（如 `trader_ji` / `kol_cat_lord_fire`）不再隐形。
- 回测周期 < 1 年时不外推年化（`annualized_return = cumulative_return`），下游 Sharpe/Sortino/Calmar 沿此保守值——更小但口径一致。
- 跑 e2e 重新生成两个 KOL 的回测产物，重新捕获宣传站三张主视觉截图。

## 2. 变更清单（Changes）

### 2.1 修改文件

| 文件 | 变更 | 行数变化 |
|---|---|---|
| `src/finer/api/routes/kol.py` | 新增 `_load_latest_backtest()` / `_rating_from_backtest()` / `_empty_rating()`；`_calculate_kol_rating()` 增加真实回测/空响应分派；删除 `_generate_mock_rating()`（含 `import random`）；`_discover_kol_ids()` 扫描 `data/review/` 目录 | 净增约 +110 行（删除 mock 54 行，新增 ~165 行） |
| `src/finer/backtest/engine.py` | `_calculate_metrics()` 年化计算加 `if days >= 365` 分支，短期窗口不外推（带注释说明） | +13 / −2 |

### 2.2 重生成产物（运行 `scripts/run_backtest_e2e.py`）

| 文件 | 旧值 | 新值 |
|---|---|---|
| `data/review/kol_cat_lord_fire/F8_backtest/backtest_result.json` | total=16.97%, annualized=**135.06%**, sharpe=**4.76** | total=16.97%, annualized=**16.97%**, sharpe=**0.60** |
| `data/review/trader_ji/F8_backtest/backtest_result.json` | total=21.40%, annualized=~187%, sharpe=~6.49 | total=21.40%, annualized=**21.40%**, sharpe=**0.74** |
| `data/review/{kol_id}/F8_backtest/trades.json` | trace 字段已含（Round 4） | 同上，仅 metrics 重算 |
| `data/review/{kol_id}/F8_backtest/equity_curve.csv` | — | 同上 |
| `src/finer_dashboard/public/landing/research.png` | 显示 Mock 平台 + 非确定性数字 | 显示 Backtest + 跨栏一致数字 |
| `src/finer_dashboard/public/landing/backtest.png` | 年化 +135.1% / 夏普 4.76 | 年化 +17.0% / 夏普 0.60 |
| `src/finer_dashboard/public/landing/workbench.png` | 无变化（与后端数据无关） | 同上（已刷新覆盖以保持时间戳一致） |

### 2.3 未触碰

- 前端代码（`src/finer_dashboard/src/**`）零改动。前端契约（`KOLRatingResponse`、`BacktestResult`）形状不变。
- Pydantic schema（`src/finer/schemas/**`）零改动。
- 并行 agent 正在动的文件（`extraction/`、`pipeline/`、`api/routes/extraction.py`、相关 tests/docs）零碰触。

## 3. 架构影响（Architecture Impact）

### 3.1 数据流（F-stage 视角）

- **F6 / F7 → KOL Rating** 现走两路：
  1. 优先：F5/F6 action records（`L5_candidate` / `L6_annotated`）—— 原有路径，无变化。
  2. 兜底：**F8 回测产物**（`data/review/{kol_id}/F8_backtest/backtest_result.json`）—— 新增。
  3. 两路都空：**确定性零响应**（`platform="Unknown"`，timeline=`[]`）—— 替换原 random fallback。

  这是一个**前向链路扩展**而非跨层调用：`api/routes/kol.py`（F6/F7 surface）读取 F8 产物作为评级的派生输入，与 AGENTS.md 的「禁止跨 stage 直接调用」不冲突（F8 → F6 是数据消费方向，符合下游 surface 读上游产物的惯例；F8 写、F6 只读）。

- **`_discover_kol_ids()` 扩展**：除 L5/L6 actions 外，额外扫描 `data/review/{kol_id}/F8_backtest/backtest_result.json`。完全确定性，按 (count desc, id asc) 排序。

### 3.2 字段语义

- `KOLRatingResponse.rating.platform` 从「`Internal` / `Mock`」二选一变为「`Internal` / `Backtest` / `Unknown`」三态，更精确反映数据来源。前端无需改动（字符串透传）。
- `BacktestResult.annualized_return` 在短期回测中**等于 `total_return`**，这是有意设计：宁可两个字段显示相同数字（视觉上提示「期间不足一年」），也不外推一个误导数。文档已用注释钉死语义。

### 3.3 后续延伸点（未做但相关）

- `_rating_from_actions()` 与 `_rating_from_backtest()` 的输出 schema 完全一致；未来可考虑当两路都有数据时合并（actions 权重 × 0.6 + backtest 权重 × 0.4），但本轮按「actions 优先，缺则 backtest」处理，避免引入合并逻辑歧义。
- `BacktestResult` 未新增 `period_too_short_to_annualize: bool` 字段。考虑过但不做：会污染契约，且数字相等本身已是足够信号；前端如需显式提示可派生（`annualized_return == total_return && days < 365`）。

## 4. 关键决策（Key Decisions）

1. **删除而非禁用 mock fallback**。`_generate_mock_rating()` 整体删除，连同 `import random`。半弃用状态会让下次有人误用——一刀切更彻底。
2. **优先 actions，回测兜底**。当前 F5/F6 普遍为空，所以回测路径会是主要触发；但保留 actions 优先意味着未来 canonical F3→F4→F5 闭环完成后无需再改这里。
3. **空响应是 200 而非 404**。`platform="Unknown"` + 全零 + 空 timeline 让前端用统一渲染路径处理，避免「未知 KOL」与「真实 KOL 暂无数据」两种 4xx 的歧义。
4. **年化阈值固定为 365 天**而非「2 倍最大持仓期」或可配置。简单、可解释、与行业惯例一致（Morningstar / Bloomberg 对 inception<1y 的基金都显示 cumulative-to-date，不年化）。
5. **Sharpe/Sortino/Calmar 沿用保守 annualized_return**，而不是单独打 NaN。沿用使指标仍可比较（同一组短期回测之间相对优劣有意义），单独打 NaN 会让前端图表/表格断档。代价是这些比率在短期窗口里**口径混合**（保守 return + 年化 vol），数字小但**单调正确**（越好的 KOL 还是越大）。
6. **必须重跑 e2e**。旧 backtest_result.json 是用旧 engine 算的、留在磁盘上。`_rating_from_backtest()` 读什么就用什么，所以必须重跑才能让评级和宣传截图反映新口径。

## 5. 验证结果（Verification）

### 5.1 单元测试

```bash
.venv/bin/python -m pytest tests/test_backtest.py tests/test_backtest_canonical.py \
  tests/test_backtest_extended.py tests/test_backtest_materializer.py \
  tests/test_kol_profile.py tests/test_kol_scorer.py -q
# 149 passed, 8 warnings in 1.69s
```

### 5.2 API 端点行为

```bash
# 确定性（两次调用返回相同 payload）
curl -s /api/kol/rating/kol_cat_lord_fire == curl -s /api/kol/rating/kol_cat_lord_fire  ✓ 字节级相同

# KOL 列表不再空
curl -s /api/kol/list/enriched
# → 2 KOLs: kol_cat_lord_fire(score=1.8, opinions=5), trader_ji(score=3.3, opinions=3)

# 未知 KOL 返回确定性空响应
curl -s /api/kol/rating/no_such_kol
# → platform=Unknown, overall=0.0, opinions=0, timeline=[]
```

### 5.3 年化口径

| KOL | period_days | total_return | 旧 annualized | 新 annualized | 旧 sharpe | 新 sharpe |
|---|---|---|---|---|---|---|
| kol_cat_lord_fire | 67 | +16.97% | **+135.06%** | **+16.97%** | **4.76** | **0.60** |
| trader_ji | 67 | +21.40% | ~+187% | **+21.40%** | ~6.49 | **0.74** |

### 5.4 前端构建（无前端改动，回归确认）

```bash
cd src/finer_dashboard && npx tsc --noEmit  # 干净
npm run lint                                 # 0 warning
npm run build                                # 通过
```

### 5.5 视觉验证（已落地为 PNG）

- `public/landing/backtest.png` 显示 累计 +17.0% / 年化 +17.0% / 夏普 0.60 / 回撤 −2.8% / 胜率 20%——内部一致
- `public/landing/research.png` 显示 trader_ji 综合 3.3（左栏 = 中栏 = 右栏），平台 `Backtest`（非 `Mock`），真实 ticker tags（159915/510300/600519），跨栏数字无漂移

## 6. 未解决项（Open Issues）

### 后端
1. **真实 timestamp 字段缺失**：`trades` 数组里的 `entry_date` / `exit_date` 在 Round 4 trace 改动里被保留，但 `_rating_from_backtest()` 派生 `recentOpinions[].timestamp` 时已正确读取。无需进一步动。
2. **基准 / 同类组仍为空（"暂无"）**：审计页 `基准 (暂无)` / `同类均值=0` 是因为前端 adapter 给 `benchmark` 和 `peer` 设的 placeholder。要让宣传截图更有说服力需要真接基准（如 SPX）。这是独立工作，未做。

### 前端遗留（与本轮无关，从 [2026-05-29 doc](2026-05-29-frontend-redesign-and-landing.md) §6 沿用）
3. `/kol/compare` 仍硬编码 mock；`kol-rating-card/*` 仍西方反向配色；InspectorPanel 软卡未收紧；工作台移动端不折叠。
4. 宣传站 `/landing` 站点位置（是否提升为公开门面）未决。

### 工作树卫生
5. 并行 agent 仍持有 `src/finer/extraction/**`、`src/finer/pipeline/**`、相关 tests 的未提交改动。本轮**未触碰**这些文件，提交时按 ownership 分离即可。
