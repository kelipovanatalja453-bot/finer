# Forward Directory - 2026-04-15

本文件记录 2026-04-15 这批补充升级，重点聚焦两个点：

1. 为 `Forward Directory` 增加按日期批次归档方式
2. 将 `Review Workstation` 的保存动作接入真实接口，写回 canonical review store

---

## 1. Forward Directory 日期化补充

### 文件

- `docs/explanations/forward-directory.md`
- `docs/explanations/forward-directory-2026-04-15.md`

### 升级内容解释

- 保留总目录版 `Forward Directory`
- 新增日期批次版 `Forward Directory - 2026-04-15`
- 后续每一轮重要升级都可以按日期写一份批次文档，避免所有升级都堆在一个总文件里

### 后续可继续优化

- 增加固定模板：`新增文件 / 修改文件 / 删除文件 / 接口变更 / 风险点 / 下一步`
- 在总目录文件里加入“日期索引表”
- 对每次重大设计升级加入截图或交互说明链接

---

## 2. Canonical Review Store 接口补充

### 文件

- `src/finer/paths.py`
- `src/finer_dashboard/src/app/api/review/route.ts`

### 升级内容解释

- `src/finer/paths.py` 中补充了：
  - `data/processed/review_store`
- `src/finer_dashboard/src/app/api/review/route.ts` 新增真实 review 保存接口：
  - 接收 `assetId / contentId / status / reviewerNotes / payload`
  - 将 review 草稿写入 `data/processed/review_store/*.review.json`
  - 当状态为 `approved` 时，同时写入 `data/processed/approved_events/*.approved.json`

这意味着 review 已不再只是前端本地编辑状态，而是开始具备 canonical persistence。

### 后续可继续优化

- 将该接口正式迁移到 Python 后端
- 增加 reviewer identity、版本号、变更 diff
- 增加对同一 content 的多次 review versioning

---

## 3. Review Workstation 保存动作补充

### 文件

- `src/finer_dashboard/src/components/studio/annotation-workbench.tsx`

### 升级内容解释

- `save review draft` 按钮已接入真实 `/api/review`
- 新增保存状态：
  - `idle`
  - `saving`
  - `saved`
  - `error`
- 新增保存反馈文案：
  - draft 保存成功
  - approved 同步写入成功
  - 失败提示

这使得工作台现在具备“编辑 -> 保存 -> 落盘”的真实闭环雏形。

### 后续可继续优化

- 保存后自动刷新右侧 provenance rail
- 保存后自动切换资产状态
- 增加“Approve and Close”与“Save Draft”双按钮

---

## 4. 当前批次的实际意义

这批补充虽然范围不大，但意义很关键：

- `Forward Directory` 从一次性说明文档，开始演化成可持续维护的升级目录机制
- `Review Workstation` 从“能改”进一步变成“能保存”
- `finer` 的 canonical contract 现在第一次具备了 review 写回能力

---

## 5. 建议下一步

1. 让 `/api/files` 读取 `review_store` 与 `approved_events`，反映保存后的真实状态
2. 在 workbench 中区分 `Save Draft` 与 `Approve`
3. 增加 review history 面板，显示每次保存时间与变更摘要
