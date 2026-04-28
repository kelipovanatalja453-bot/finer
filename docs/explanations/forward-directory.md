# Forward Directory

本文件用于记录本轮对 `finer / Finer OS` 的升级内容。

记录方式包含三部分：

1. 升级涉及的文件名
2. 升级内容解释
3. 后续还可以继续优化的方向

---

## 1. 产品与架构文档升级

### 文件

- `docs/explanations/project-status-2026-04-14.md`

### 升级内容解释

- 新增项目状态快照，明确区分了：
  - 哪些部分已经真实落地
  - 哪些部分仍然是设计稿或骨架
  - 当前数据资产分布情况
  - 前端与后端契约不一致的问题
- 这份文档的作用是防止后续继续把“愿景层”和“实现层”混在一起。

### 后续可继续优化

- 增加按日期更新的 changelog 结构
- 增加 “已验证 / 待验证 / 已废弃” 三类状态标记
- 将关键路径拆成更细的里程碑追踪表

---

### 文件

- `docs/explanations/finer-os-design-optimization.md`

### 升级内容解释

- 新增 `Finer OS` 的系统化设计升级方案。
- 核心重构思路包括：
  - 从 `tier-first` 改成 `workflow-first`
  - 用 `Intake / Library / Parsing / Extraction / Review / Backtest` 替代主导航里的纯层级思维
  - 将 `L0-L8` 保留为 provenance / stage badge
  - 强化 evidence-first、queue-first、human-in-the-loop 的产品原则

### 后续可继续优化

- 继续补充每个 workflow screen 的交互流程图
- 为 review / backtest / library 增加更细的状态机定义
- 后续可继续沉淀成设计系统规范文档

---

## 2. 视觉系统与全局框架升级

### 文件

- `src/finer_dashboard/src/app/layout.tsx`

### 升级内容解释

- 替换了全局字体系统：
  - `Noto Serif SC`
  - `IBM Plex Sans`
  - `IBM Plex Mono`
- 调整了页面 metadata，使其更贴合 `Finer OS` 的真实产品定位。

### 后续可继续优化

- 继续补充不同语言环境下的字体 fallback
- 根据组件密度进一步细调字号层级
- 为不同工作流页面定义更明确的标题系统

---

### 文件

- `src/finer_dashboard/src/app/globals.css`

### 升级内容解释

- 重做了全局视觉底座：
  - 米白纸感背景
  - 细网格和轻微纹理层
  - 更克制的金融编辑台配色
  - 面板玻璃化和投影层次
  - 新的前景色、强调色和语义色逻辑
- 让 UI 从通用模板感，转向更像“投研证据操作系统”的气质。

### 后续可继续优化

- 抽出完整 design token 体系
- 为不同 workflow 页面定义局部色彩偏置
- 对 review 场景单独优化可读性与视觉噪音控制

---

## 3. Workflow-first 主界面升级

### 文件

- `src/finer_dashboard/src/components/layout/sidebar.tsx`

### 升级内容解释

- 侧边栏从旧的 `MEDALLION PIPELINE / PLUGINS` 模型，升级为真正的 workflow-first 导航：
  - `Intake`
  - `Library`
  - `Parsing`
  - `Extraction`
  - `Review`
  - `Backtest`
- 新增：
  - `Current workflow`
  - `Pipeline Pulse`
  - `Provenance` 提示卡
- 保留 `L0-L8`，但将其降级为 badge，而不是主心智模型。

### 后续可继续优化

- 将 `Pipeline Pulse` 由静态数字改为真实统计
- 增加 creator filter 和 saved views
- 增加 queue count、error count、needs review count 等 operational signal

---

### 文件

- `src/finer_dashboard/src/components/layout/main-board.tsx`

### 升级内容解释

- 主工作区头部升级为 workflow-aware：
  - 支持动态标题
  - 支持副标题
  - 支持 stage label
  - 支持搜索语义调整
  - 支持 import 按钮文案切换
- 把原来统一的“文件浏览板”改造成更接近任务面的工作区框架。

### 后续可继续优化

- 增加 `Queue / Grid / Table` 三种真实视图模式切换
- 把 toolbar 的按钮接入真实筛选器
- 支持 creator / content type / review state 多维过滤

---

### 文件

- `src/finer_dashboard/src/components/layout/upload-button.tsx`

### 升级内容解释

- 上传按钮不再暴露 `UPLOAD TO Lx` 这种实现细节。
- 改成由主工作区传入任务语义文案，例如：
  - `Import Asset`
  - `Add Research File`
  - `Attach Evidence`

### 后续可继续优化

- 增加拖拽上传
- 增加批量上传
- 上传完成后自动触发分类与 manifest 预览

---

### 文件

- `src/finer_dashboard/src/app/page.tsx`

### 升级内容解释

- 首页从直接围绕 tier 展示，改成先定义 workflow view，再映射到对应 stage badge。
- 统一接入新的资产对象 contract。
- 打通了：
  - `Sidebar`
  - `MainBoard`
  - `InspectorPanel`
  - `AnnotationWorkbench`
- 当前页面已经不是单纯展示文件夹内容，而是在围绕统一资产对象运行。

### 后续可继续优化

- 增加 URL 状态同步，让 workflow 可分享
- 增加真实筛选条件和排序逻辑
- 区分 library 浏览模式与 review 工作模式

---

## 4. 数据契约统一升级

### 文件

- `src/finer_dashboard/src/lib/contracts.ts`
- `src/finer/paths.py`

### 升级内容解释

- 新增统一前端 contract 定义。
- 抽出了：
  - `WorkflowStage`
  - `AssetFile`
  - `ReviewPayload`
  - `ReviewAction`
  - `ReviewDirection`
- 这一步的意义是：前端各组件开始围绕统一资产对象工作，而不再各自猜字段。

### 后续可继续优化

- 与 Python 侧 schema 做更严格的一一对应
- 后续将这份 contract 迁移为共享 schema 生成产物
- 增加 review 保存、approved event、backtest artifact 的更细对象层

---

### 文件

- `src/finer_dashboard/src/app/api/files/route.ts`
- `src/finer_dashboard/src/app/api/review/route.ts`

### 升级内容解释

- 这是本轮最关键的升级之一。
- 原先 API 是：
  - 根据 `L0-L8` 找一个目录
  - 直接把文件当成 UI 数据返回
- 现在改成：
  - 建立 canonical asset view
  - 统一吸收 `data/raw`、`data/processed`、`data/backtests`
  - 同时兼容仓库里已有的 `L0_ingest`、`L3_aligned`、`L4_parsed` 等遗留实验结构
  - 自动拼出 `AssetFile`
  - 对 extraction / review 阶段生成 `ReviewPayload`
- POST 上传也改成落入 canonical intake inbox，而不是伪 tier 目录。
- review 保存接口已补充，可写入：
  - `data/processed/review_store`
  - `data/processed/approved_events`

### 后续可继续优化

- 最好把这部分逻辑下沉到 Python 后端，避免 Next.js 直接承担数据兼容层
- 将当前 review save / update 接口迁移到 Python 后端
- 增加 approved event 和 backtest result 的写回通道

---

## 5. Provenance Rail 升级

### 文件

- `src/finer_dashboard/src/components/layout/inspector-panel.tsx`

### 升级内容解释

- 右侧面板从旧的静态 metadata mock，升级成了真正的 provenance rail。
- 现在展示内容包括：
  - 资产身份
  - creator / content type
  - stage badge
  - provenance timeline
  - evidence readiness
  - machine summary
  - semantic anchors
- 它现在是统一资产对象的消费方，而不是写死示例文本。

### 后续可继续优化

- 增加 manifest / evidence / candidate event 的真实路径跳转
- 增加 reviewer history
- 增加 parser version / extraction version 信息

---

## 6. Review Workstation 升级

### 文件

- `src/finer_dashboard/src/components/studio/annotation-workbench.tsx`

### 升级内容解释

- 这是本轮第二个核心升级。
- 该组件已从静态样机，重写为真正的 review workstation。
- 当前支持：
  - `ticker` 修正
  - `direction` 修正
  - `time horizon` 修正
  - `rationale` 编辑
  - `action chain` 编辑
  - `action` 新增
  - `action` 删除
- `action_type / instrument_type / trigger_condition / target prices` 编辑
- reviewer notes
- approve / reject 本地状态切换
- 保存动作已接入真实 review API，并能写回 canonical review store
- 左侧证据区也已经接入统一资产对象的 `evidenceText / summary / provenance clues`。

### 后续可继续优化

- 增加 evidence span 与字段的双向高亮绑定
- 增加 field diff 和 change history
- 将 save 动作进一步拆成 `Save Draft` 与 `Approve`
- 支持多候选 action chain 对比与偏好选择

---

## 7. 本轮升级的整体价值

### 已完成的核心推进

- `Finer OS` 从 tier-first 改成 workflow-first
- 前端 contract 从“目录文件”改成“统一资产对象”
- `Review Workstation` 从展示样机变成可编辑的真实工作台
- `Inspector` 从 metadata mock 变成 provenance rail
- 统一了 UI 层与 Python 侧 canonical contract 的方向

### 当前仍未完全完成的部分

- Next.js 目前还承担了数据兼容层，后续最好由 Python 后端提供正式 canonical API
- action chain 编辑虽然已经能用，但还没有 review version history

---

## 8. 建议的下一步顺序

1. 为 `Review Workstation` 增加真实保存接口
2. 在 Python 侧补正式 canonical asset API
3. 增加 approved events 与 review history 的写回
4. 将 backtest artifacts 接入同一套 contract
5. 把 queue、filter、search 真正做成 workflow 级别的操作能力

---

## 9. 建议命名约定

如果后续还继续做这一类升级，建议统一使用以下命名习惯：

- `Forward Directory`: 记录本轮系统升级
- `Forward Directory - YYYY-MM-DD`: 记录阶段性升级批次
- 在每次大改动后追加：
  - 新增文件
  - 修改文件
  - 升级目的
  - 后续可继续优化项

这样你后续回看时，会非常清楚每轮升级到底推进了什么，而不是只看到零散 diff。
