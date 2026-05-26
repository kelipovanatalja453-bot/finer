# Vibe Agent Operating Model

> Status: draft
> Scope: 通用 multi-agent / vibe-coding 工作流
> Reference case: Finer OS 的 F-stage、Line V、任务卡和架构锁实践

## 1. 核心结论

vibe-coding 不能按“最低成本优先”来调度 Agent。

更稳的通用策略是：

```text
能力强的模型先决定方向
中强模型拆解和审查
低成本模型在任务卡边界内批量执行
自动化测试和人工验收负责最终事实判断
```

换句话说：

```text
架构阶段能力优先
执行阶段成本优先
验收阶段可靠性优先
```

强模型不应该一上来写大量代码；它应该先完成高杠杆决策：项目目标、架构边界、风险点、任务拆解和禁止事项。低成本模型只有在边界清晰时才适合批量执行。

## 2. 适用范围

本文档适用于以下项目：

- 前端应用
- 后端服务
- 数据处理项目
- AI / LLM 应用
- 自动化脚本项目
- 科研或知识管理项目
- 多 Agent 并行开发项目

它不绑定某一个仓库。Finer OS 只是参考案例：Finer 的经验是用 `AGENTS.md`、架构契约、Line V 验证和任务卡把多个 Agent 收束在可审计边界内。

## 3. 基本原则

### 3.1 规则先行

任何项目在让 Agent 写代码前，必须先明确项目规则。

推荐最小文档集：

```text
AGENTS.md
docs/architecture_lock.md
docs/agent_task_template.md
docs/verification_plan.md
```

如果项目已经有自己的规范文件，可以复用现有文件，不必机械新增同名文档。关键是必须存在以下信息：

- 项目目标
- 技术栈
- 目录结构
- 架构边界
- 允许修改区域
- 禁止修改区域
- 验证命令
- 红线操作

### 3.2 架构先行

不要让低成本模型直接从开放式需求开始写代码。

错误流程：

```text
DeepSeek 直接开始写代码
↓
越写越偏
↓
Claude / GPT 后期救火
```

推荐流程：

```text
Claude / GPT 先锁定方向
↓
GPT 把架构拆成任务卡
↓
DeepSeek 在边界内执行
↓
Gemini / GPT 做审查
↓
Claude 处理高风险问题
```

### 3.3 任务卡驱动

低成本模型只适合执行边界清晰的任务卡，不适合处理开放式架构问题。

不要给低成本模型这种任务：

```text
帮我优化整个项目架构。
```

应该给：

```text
只修改 components/UserCard.tsx。
参考 components/Button.tsx 和 components/Avatar.tsx。
不得新增依赖。
不得修改 API。
完成后运行 npm test。
```

### 3.4 风险分级路由

模型选择应由任务风险决定，而不是由单价决定。

```text
高返工风险任务用强模型
低返工风险任务用低成本模型
可自动验证任务优先交给执行层
不可自动验证任务必须加强审查
```

### 3.5 验证优先

Agent 自述“完成”不算完成。完成必须由以下证据支持：

- 测试结果
- 构建结果
- 类型检查
- lint
- diff 审查
- 产物截图或快照
- schema / contract 验证

没有验证命令的任务卡是不完整的。

## 4. 推荐工作流

完整流程：

```text
0. 项目规则初始化
   ↓
1. 只读理解项目
   ↓
2. 架构方案 / 技术路线
   ↓
3. 反方审查 / 压缩方案
   ↓
4. 生成架构锁
   ↓
5. 拆成任务卡
   ↓
6. 低成本 Agent 执行
   ↓
7. 低成本初审
   ↓
8. 高可靠终审
   ↓
9. 高风险问题交给强模型
   ↓
10. 验证、提交、沉淀规则
```

精简流程：

```text
Claude / GPT 定架构
GPT 拆任务
DeepSeek 执行
Gemini 初审
GPT 终审
Claude 攻坚
测试 / CI 裁决
```

## 5. 项目规则文件

### 5.1 `AGENTS.md`

项目最高规则入口。

应包含：

- 项目定位
- 技术栈
- 架构边界
- 目录 ownership
- 禁止事项
- 验证命令
- 红线操作
- Agent 沟通和交付格式

所有 Agent 进入项目后必须先读 `AGENTS.md`。

### 5.2 `docs/architecture_lock.md`

记录当前已确认的架构决策。

应包含：

- 当前采用的架构
- 技术栈
- 目录结构
- 状态管理方式
- 数据流
- API / schema contract
- 不允许普通 Agent 修改的区域
- 需要强模型或人工确认的区域

注意：如果项目已有更权威的架构文件，`architecture_lock.md` 可以只做索引，不重复定义规则。

### 5.3 `docs/agent_task_template.md`

任务卡模板。

用于把开放式需求转成低成本模型可执行的小任务。

### 5.4 `docs/verification_plan.md`

记录不同类型任务的验证命令。

示例：

```text
前端 UI 修改:
- npm run lint
- npm run build
- Playwright screenshot

后端 API 修改:
- pytest tests/api -q
- mypy / pyright
- contract tests

schema 修改:
- backend schema tests
- frontend type sync
- serialization roundtrip tests
```

## 6. Agent 身份卡

每个 Agent 开工前必须声明身份。

模板：

```text
Agent Identity

- Agent source: Claude Code / Codex / DeepSeek / Gemini / Cursor / Other
- Model:
- Role: Architect / Task Planner / Implementer / Reviewer / Auditor / Orchestrator
- Project area:
- Risk level: R0 / R1 / R2 / R3 / R4
- Input:
- Output:
- Allowed files:
- Forbidden files:
- Can edit code: yes/no
- Can edit tests: yes/no
- Can edit architecture: yes/no
- Can change contracts: yes/no
- Output payload type:
- Default handoff target:
- Quota source: user provided / framework reported / unknown
- Remaining quota:
- Quota reset time:
- Quota fallback:
- Required verification:
- Stop conditions:
```

最重要的问题：

```text
我是谁？
我负责什么？
我不能碰什么？
我完成后怎么证明？
失败时谁接手？
```

没有身份卡，不允许进入实现阶段。

## 7. 模型能力与 Agent 框架能力

模型和 Agent 框架是两个不同维度。

```text
模型能力 = 推理、代码理解、生成质量、上下文处理能力
Agent 框架能力 = 文件系统、终端、浏览器、插件、子代理、工作区隔离、审批机制
```

同一个模型放在不同框架中，适合承担的角色不同。例如：

- Claude 在 Claude Code 中可以作为架构师、审计员或实现者；但在普通聊天窗口中更适合输出方案和任务卡。
- GPT 在 Codex 中可以直接读写仓库、运行测试和验证；但在 API-only 环境里只能生成补丁或指令。
- DeepSeek 如果只是 API 调用，不能自己验证本地测试；如果被 Codex / CI wrapper 调用，则可以做低风险执行。
- Gemini 如果没有仓库写权限，更适合只读扫描、初审和对照检查。

因此，分工时必须同时声明：

```text
1. 用哪个模型
2. 运行在哪个 Agent 框架里
3. 这个框架能不能读写文件、跑测试、打开浏览器、调用外部服务
4. 它的输出是代码修改、patch、报告、任务卡，还是审查结论
```

## 8. Agent 框架角色矩阵

### 8.1 Codex

定位：

```text
本地工程执行控制台 + 验证运行器 + 任务编译器
```

Codex 适合承担：

- 实际修改本地仓库文件
- 使用 `apply_patch` 做可审计编辑
- 运行测试、构建、lint、typecheck
- 使用终端检查 git 状态和 diff
- 在前端项目中启动本地服务并做浏览器验证
- 把架构方案转成可执行任务卡
- 做最终交付前的本地验证汇总

Codex 不应默认承担：

- 没有项目规则时的大范围自由重构
- 同时和其他 Agent 修改同一批文件
- 绕过项目 `AGENTS.md` / `CLAUDE.md` 的私有规则
- 未经确认执行删除、迁移、push、rebase、reset、部署等红线操作

Codex 最适合的角色：

| 角色 | 是否适合 | 说明 |
|---|---|---|
| Task Planner | 高 | 能把方案转成文件级任务卡 |
| Implementer | 高 | 有本地文件和测试能力 |
| Verification Runner | 高 | 能运行命令并汇总结果 |
| Reviewer | 中高 | 能基于 diff 做审查 |
| Architect | 中 | 可以做，但复杂架构最好引入 Claude / GPT 反审 |
| Orchestrator | 中高 | 适合维护本地工作区和任务状态 |

Codex 交付物建议：

```text
- 修改文件清单
- 验证命令和结果
- 未解决风险
- 是否触及架构锁
- 是否存在未跟踪或无关变更
```

### 8.2 Claude Code

定位：

```text
架构推理器 + 高风险攻坚手 + 多 Agent 协调器
```

Claude Code 适合承担：

- 大代码库阅读和架构判断
- 跨文件重构设计
- 复杂 bug 定位
- 高风险实现或修复
- 独立架构审计
- 多 Agent 任务协调
- 生成 owner / conflict / merge order 报告

Claude Code 不应默认承担：

- 低风险机械任务的大量批处理
- 在没有任务卡和文件边界时直接大范围修改
- 假设自己能读取 Codex 私有 skill、插件状态或会话记忆
- 与 Codex 同时修改同一文件集合

Claude Code 最适合的角色：

| 角色 | 是否适合 | 说明 |
|---|---|---|
| Architect | 高 | 适合定方向和拆架构风险 |
| Auditor | 高 | 适合只读判断是否偏离架构 |
| High-risk Implementer | 高 | 适合 schema、pipeline、跨模块修复 |
| Orchestrator | 高 | 有子代理或 agent-team 能力时尤其适合 |
| Low-risk Implementer | 中 | 能做，但成本通常不划算 |
| Verification Runner | 中 | 可跑命令，但不应替代 CI / 本地事实层 |

Claude Code 交付物建议：

```text
- 架构判断
- 风险地图
- 禁止修改区域
- Agent ownership 分配
- DeepSeek / Codex 任务卡
- 高风险问题的修复建议或补丁
```

### 8.3 API-only DeepSeek

定位：

```text
低成本代码生成器
```

API-only DeepSeek 通常没有本地文件系统、测试环境和浏览器能力。它适合输出：

- 单文件实现草稿
- 小函数补丁
- 单元测试草稿
- 类型定义
- 文档段落
- mock 数据

API-only DeepSeek 不应被要求：

- 判断整体架构
- 自称已经运行测试
- 修改多个不相关文件
- 处理 schema、权限、数据库、pipeline 等高风险任务

推荐使用方式：

```text
GPT / Codex 生成任务卡
DeepSeek 生成 patch 或代码片段
Codex 应用 patch 并运行验证
GPT / Claude 审查 diff
```

### 8.4 Gemini

定位：

```text
大上下文只读审查员 + 低成本初筛员
```

Gemini 适合：

- 大范围文档扫描
- 明显不一致检查
- UI 截图初审
- 需求覆盖检查
- mock / TODO / deprecated 扫描
- 对 Claude / GPT 方案做低成本反审

Gemini 不应默认作为：

- 最终架构裁决者
- 高风险实现者
- 需要严格本地验证的唯一验收方

Gemini 交付物建议：

```text
- findings table
- risk summary
- questionable assumptions
- files needing stronger review
```

### 8.5 Cursor / IDE Agent

定位：

```text
交互式局部编辑助手
```

IDE Agent 适合：

- 当前文件或相邻文件的局部修改
- 快速补全
- 小范围重构
- UI 细节迭代
- 人类开发者在旁边实时监督的任务

IDE Agent 不适合：

- 无监督跨目录重构
- 多 Agent 并行 ownership 管理
- 复杂验证汇总
- 作为项目唯一规则源

使用原则：

```text
IDE Agent 可以提高局部速度，但项目边界仍以仓库文档为准。
```

### 8.6 CI / Scripts

定位：

```text
事实层和回归守门员
```

CI / scripts 适合：

- 自动测试
- 构建验证
- 类型检查
- lint
- schema validation
- snapshot / screenshot diff
- contract tests

CI / scripts 不负责：

- 解释产品目标
- 判断架构取舍
- 自动接受高风险变更

使用原则：

```text
Agent 提交的是主张，CI 给出事实证据。
```

## 9. 跨框架交接协议

不同 Agent 框架之间不能依赖私有记忆、插件状态或会话上下文。交接必须落到仓库文件、patch、diff 或报告里。

每次交接都必须显式回答：

```text
这份输出分发给哪个模型 / Agent 框架？
这次传递的是什么类型的内容？
接收方能不能直接执行？
接收方是否必须复核或验证？
```

### 9.1 Handoff Envelope

任何跨模型、跨框架、跨会话的输出，都必须包一层 handoff envelope。不要只输出一段自由文本。

模板：

```text
Agent Handoff

## Sender
- Source framework:
- Model:
- Role:

## Target
- Target framework: Codex / Claude Code / DeepSeek API / Gemini / Cursor / CI / Human
- Target model:
- Target role: Architect / Planner / Implementer / Reviewer / Auditor / Verification Runner

## Payload
- Payload type: Architecture Brief / Task Card / Patch / Review Plan / Verification Plan / Diff Review / Verification Report / Finding List / Quota Snapshot / Blocker / Decision Request / Approval Request
- Risk level: R0 / R1 / R2 / R3 / R4
- Can execute directly: yes/no
- Requires human approval: yes/no
- Requires verification: yes/no

## Quota
- Sender remaining quota:
- Target remaining quota:
- Quota source: user provided / framework reported / estimated / unknown
- Quota reset time:
- Fallback if target quota is insufficient:

## Context Pointers
- Required files:
- Related docs:
- Related commits / diffs:
- Prior reports:

## Instructions To Receiver
1. ...
2. ...
3. ...

## Acceptance / Response Expected
- Expected output type:
- Required verification:
- Stop conditions:
```

### 9.2 Payload Types

交接内容必须标注类型。不同类型有不同接收方和处理方式。

| Payload type | 含义 | 推荐接收方 | 是否可直接执行 |
|---|---|---|---|
| Architecture Brief | 架构判断、技术路线、边界和风险 | GPT / Claude / Codex | 否，需要拆任务 |
| Task Card | 可执行任务卡，含 allowed files 和验收标准 | Codex / DeepSeek / IDE Agent | 是，若风险不超过接收方权限 |
| Patch | 代码补丁或局部实现片段 | Codex / IDE Agent | 否，必须应用后验证 |
| Review Plan | 审查角度、审查者、审查范围和阻断标准 | Human / Orchestrator / GPT / Claude | 否，需要确认后执行 |
| Verification Plan | 验证命令、验收标准、截图/快照/contract 检查和风险 | Human / Orchestrator / Codex / CI | 否，需要确认后执行 |
| Diff Review | 对现有 diff 的审查意见 | Codex / Claude Code / Human | 否，需要 owner 决策 |
| Verification Report | 测试、构建、扫描、截图结果 | GPT / Claude / Human | 否，作为证据输入 |
| Finding List | 初筛问题列表 | GPT / Claude / Codex | 否，需要复核 |
| Quota Snapshot | 各模型/框架的剩余额度、来源、重置时间和降级策略 | Orchestrator / Task Planner / Human | 否，作为调度输入 |
| Blocker | 阻断问题，继续执行会扩大风险 | Human / Orchestrator / Claude | 否，必须先决策 |
| Decision Request | 需要人工或强模型裁决的问题 | Human / Claude / GPT | 否，等待裁决 |
| Approval Request | 准备执行计划前向用户请求批准，说明收益、成本、风险和回退 | Human | 否，等待批准 |
| Merge Plan | 合并顺序、冲突文件和验证顺序 | Codex / Human / Orchestrator | 否，按计划执行 |
| Execution Result | 实现结果、修改文件、命令输出摘要 | Reviewer / Verification Runner | 否，进入审查 |

规则：

- `Architecture Brief` 不能直接分发给低成本实现模型，必须先转成 `Task Card`。
- `Finding List` 不能直接当作最终结论，高风险 finding 必须复核。
- `Patch` 不能等同于已完成，必须由具备本地文件和测试能力的 Agent 应用并验证。
- `Verification Report` 是事实证据，不自动代表可以合并。
- `Blocker` 和 `Decision Request` 不能被低成本实现 Agent 自行绕过。
- `Review Plan` 和 `Verification Plan` 不能自动执行；必须先得到用户确认，或由已有项目规则明确授权。

### 9.3 Receiver Routing

输出时必须明确“给谁”。推荐路由：

| Sender output | Target framework | Target role | 说明 |
|---|---|---|---|
| Claude 架构方案 | GPT / Codex | Task Planner | 压缩方案，拆成任务卡 |
| GPT 任务卡 | DeepSeek API / Codex / IDE Agent | Implementer | 低风险执行 |
| DeepSeek patch | Codex | Implementer + Verification Runner | 应用补丁并跑测试 |
| Codex 实现结果 | GPT / Claude Code | Reviewer | 审查 diff 和风险 |
| Gemini finding list | GPT / Claude / Codex | Reviewer / Auditor | 复核明显问题 |
| Line V 验证报告 | Orchestrator / GPT / Claude | Planner / Auditor | 决定下一轮是否开工 |
| Quota Snapshot | Orchestrator / GPT / Codex | Task Planner | 调整模型路由和任务粒度 |
| Review / Verification Plan | Human | Decision Maker | 批准后才执行审查或验证流程 |
| Blocker | Human / Claude / Orchestrator | Decision Maker | 暂停执行，先裁决 |

禁止：

- 把 `Architecture Brief` 直接交给 DeepSeek 自由实现。
- 把 `Patch` 直接当作“已验证完成”。
- 把 `Finding List` 直接当作“必须修改清单”。
- 把 `Decision Request` 伪装成普通任务卡。
- 在未获用户确认时执行新的多 Agent 审查计划、长流程验证计划或高额度验证计划。

### 9.4 Claude Code -> Codex

适合场景：

```text
Claude Code 做架构判断，Codex 负责本地落地和验证。
```

交接物：

- 架构方案
- allowed / forbidden files
- 任务卡
- 风险点
- 验收命令

Codex 接手后必须：

- 重新读取项目规则文件
- 检查工作区状态
- 不假设 Claude Code 的私有上下文完整
- 用本地测试验证实际结果

### 9.5 Codex -> Claude Code

适合场景：

```text
Codex 实现后，Claude Code 做高风险审查或复杂问题攻坚。
```

交接物：

- git diff 摘要
- 修改文件清单
- 运行过的命令
- 失败测试
- 未解决风险
- 需要判断的具体问题

Claude Code 接手后必须：

- 以 diff 和项目文档为证据
- 不重新发明架构规则
- 不直接修改 Codex 正在处理的同一文件，除非明确切换 ownership

### 9.6 GPT / Codex -> DeepSeek

适合场景：

```text
把低风险任务批量下发给 DeepSeek。
```

交接物必须是任务卡，不是开放式需求。

任务卡必须包含：

- 目标
- 上下文文件
- allowed files
- forbidden files
- 输入输出 contract
- 验收标准
- 禁止事项
- 失败停止条件

DeepSeek 输出后，必须由 Codex 或 CI 运行验证。

### 9.7 Gemini -> GPT / Claude / Codex

适合场景：

```text
Gemini 做初筛，强模型或本地执行器处理关键问题。
```

交接物：

- findings table
- 每个 finding 的文件证据
- 严重程度
- 建议 owner
- 是否需要复查

Gemini 的 finding 不应直接等同于最终结论；高风险问题需要 GPT / Claude / Codex 复核。

## 10. 框架选择决策表

| 任务 | 推荐框架 | 推荐模型 | 原因 |
|---|---|---|---|
| 只读理解大项目 | Claude Code / Gemini | Claude / Gemini | 上下文和总结能力重要 |
| 架构设计 | Claude Code | Claude | 高返工风险 |
| 方案反审 | Codex / GPT | GPT | 压缩方案和找过度设计 |
| 任务卡生成 | Codex / GPT | GPT | 需要工程边界和可执行格式 |
| 单文件实现 | Codex wrapper / IDE | DeepSeek / GPT | 边界清楚，成本可控 |
| 多文件低风险实现 | Codex | GPT / DeepSeek | 需要本地验证 |
| 高风险跨模块修复 | Claude Code / Codex | Claude / GPT | 需要推理和验证 |
| UI 截图初审 | Gemini / Codex browser | Gemini / GPT | 视觉和低成本检查 |
| 最终 diff review | Codex / Claude Code | GPT / Claude | 需要证据和架构判断 |
| 测试与构建 | CI / Codex | scripts | 事实层验证 |

## 11. 额度感知调度

模型选择除了看能力、框架和风险，还必须看剩余额度。

```text
最终路由 = 任务风险 × 框架能力 × 模型能力 × 剩余额度 × 重置时间
```

额度不足时，不应让高价值模型消耗在低杠杆任务上；也不应因为低成本模型额度充足，就把高风险架构任务交给它。

### 11.1 额度信息来源

每轮调度前，Orchestrator 或 Task Planner 必须尽量获取额度信息。

优先级：

1. 框架可自动读取的真实额度。
2. 用户手动提供的剩余额度。
3. 最近一次调用后的估算额度。
4. `unknown`。

如果额度是 `unknown`，必须按保守策略调度：

```text
强模型只做高杠杆判断
低成本模型只做边界清晰任务
需要长上下文的任务先产出压缩摘要
禁止启动大范围无边界探索
```

### 11.2 向用户索要额度

当任务需要在多个付费模型之间调度，且框架无法自动读取额度时，应先向用户索要最小必要信息。

推荐问题：

```text
请提供当前可用额度或大致剩余情况：
- Claude / Claude Code:
- GPT / Codex:
- DeepSeek:
- Gemini:
- 是否有今日必须保留的高优先级任务:
- 额度重置时间:
```

如果用户不想提供精确额度，可以使用档位：

```text
high: 可以承担长上下文和多轮推理
medium: 可以承担少量关键判断
low: 只保留给最终审查或救火
exhausted: 不再调度
unknown: 按保守策略
```

### 11.3 模型自检额度

Agent 可以自检额度，但只有在宿主框架明确暴露额度信息时才可信。

规则：

- 如果框架提供 quota / usage / rate-limit 信息，Agent 应读取并记录。
- 如果框架不提供，Agent 不能声称知道真实剩余额度。
- 如果只能看到 API 报错或限流信息，只能记录为 `estimated` 或 `insufficient`。
- 自检结果必须写入 handoff envelope 的 `Quota` 字段。

不要写：

```text
我应该还有足够额度。
```

应该写：

```text
Quota source: unknown
Remaining quota: unknown
Fallback: reduce Claude to architecture review only; use DeepSeek for R1 task cards.
```

### 11.4 额度状态路由表

| 状态 | 强模型使用策略 | 低成本模型使用策略 | 审查策略 |
|---|---|---|---|
| high | 可做架构、审查、复杂修复 | 批量执行 R1/R2 | 正常双审 |
| medium | 只做架构锁、关键任务卡、终审 | 承担大部分实现 | 抽样初审 + 重点终审 |
| low | 只保留给 blocker、最终裁决、复杂 bug | 只执行边界清楚任务 | 优先自动化验证 |
| exhausted | 不调度 | 可执行低风险任务 | 等额度恢复或换模型 |
| unknown | 保守使用，先要求压缩上下文 | 只做小任务 | 必须记录假设 |

### 11.5 额度保护规则

强模型额度低时：

- 不让它读取全仓库重复上下文。
- 不让它做机械实现。
- 不让它跑多轮开放式讨论。
- 先让 Gemini / Codex / 脚本产出压缩报告。
- 只把高价值决策问题交给它。

低成本模型额度高时：

- 仍然不能让它改架构锁。
- 仍然不能让它处理 R3/R4 任务。
- 只能在任务卡和验证边界内扩展使用。

### 11.6 额度感知任务卡字段

任务卡必须包含额度信息：

```text
## Quota
- Recommended model quota status: high / medium / low / exhausted / unknown
- Quota source: user provided / framework reported / estimated / unknown
- Quota reset time:
- If quota is low:
- Fallback model:
- Fallback payload type:
```

当目标模型额度不足时，任务卡必须降级为以下之一：

- `Architecture Brief` -> 压缩为关键决策问题
- `Task Card` -> 拆成更小任务
- `Patch` -> 交给 Codex 应用和验证
- `Review` -> 改为 checklist + targeted diff review
- `Implementation` -> 延后或切换到低成本模型

## 12. 模型层默认分工

本节按模型能力给默认分工。实际执行时，必须再叠加第 8 到第 11 节的 Agent 框架能力和额度状态判断：同一个模型在 Codex、Claude Code、IDE、API-only 或 CI wrapper 中，权限、额度和责任边界不同。

### 12.1 Claude / Claude Code

定位：

```text
首席架构师 + 高难度攻坚手
```

适合：

- 项目架构设计
- 大代码库理解
- 跨文件重构
- 核心数据流设计
- 状态管理设计
- 权限系统设计
- 复杂 bug 定位
- 高风险合并前审查

不适合：

- 大量重复组件
- 机械改名
- 简单文档搬运
- 低风险批量测试补齐

使用原则：

```text
Claude 先定方向，少做体力活。
```

### 12.2 GPT / Codex

定位：

```text
技术总控 + 任务编译器 + 实现审查员
```

适合：

- 方案反方审查
- 压缩过度设计
- 任务拆解
- 任务卡生成
- diff review
- 测试设计
- 自动化验证
- 局部工程实现

不适合：

- 在没有架构锁时直接大范围开工
- 长时间无边界探索

使用原则：

```text
GPT 负责把“方向”编译成“可执行任务”。
```

### 12.3 DeepSeek

定位：

```text
低成本执行层
```

适合：

- 单文件实现
- 单个组件
- 类型定义
- mock 数据
- 文档补充
- 单元测试
- 样式微调
- 重复性重构
- 低风险 bug 修复

不适合：

- 架构设计
- schema / contract 变更
- 数据库设计
- 权限系统
- 跨模块状态流
- 核心业务 pipeline
- 高风险重构

使用原则：

```text
DeepSeek 只能在任务卡内执行，不应该自由探索架构。
```

### 12.4 Gemini

定位：

```text
低成本审计员 / 初筛员
```

适合：

- 大上下文只读扫描
- 文档一致性检查
- UI 截图初审
- 明显 bug 检查
- 规范符合度检查
- mock / deprecated / TODO 扫描

不适合：

- 高风险代码落地
- 核心业务逻辑重构
- 最终架构裁决

使用原则：

```text
Gemini 适合发现明显问题，不负责最终结构性决策。
```

### 12.5 本地脚本 / 测试 / CI

定位：

```text
事实层裁判
```

适合：

- lint
- typecheck
- unit test
- integration test
- build
- snapshot
- schema validation
- contract test

使用原则：

```text
Agent 说完成不算，验证产物说完成才算。
```

## 13. 风险分级

### R0: 只读任务

例子：

- 阅读项目
- 总结架构
- 找风险
- 跑测试
- 扫描 deprecated code
- 审查 diff

推荐模型：

```text
Gemini / GPT / Claude
```

规则：

- 不允许编辑文件
- 不允许删除文件
- 不允许 stage / commit / push
- 只能输出报告

### R1: 低风险任务

例子：

- 单个组件
- 单个工具函数
- 类型补充
- 文档补充
- mock 数据
- 单元测试
- 样式微调

推荐模型：

```text
DeepSeek 执行
Gemini 初审
GPT 终审
```

规则：

- 必须有明确 allowed files
- 必须有验证命令
- 不允许修改架构锁
- 不允许新增依赖

### R2: 中风险任务

例子：

- 2 到 5 个文件
- 一个 API route
- 一个页面
- 一个小模块
- 在已有模式下扩展功能

推荐模型：

```text
GPT 拆任务
DeepSeek 执行
GPT 审查
Claude 只处理异常
```

规则：

- 必须拆成子任务
- 必须声明共享文件
- 必须有回滚策略
- 必须跑 targeted tests

### R3: 高风险任务

例子：

- 架构调整
- schema 变更
- 数据流变更
- 状态管理变更
- 数据库设计
- 权限系统
- 跨模块重构
- 核心业务 pipeline
- 前后端 contract 变化

推荐模型：

```text
Claude / GPT 设计
GPT 生成任务卡
Claude 或 Codex 实现关键部分
DeepSeek 只做外围子任务
GPT / Claude 终审
```

规则：

- 先设计，后实现
- 先锁 contract，再并行
- 必须有审查 Agent
- 必须有完整验证计划

### R4: 红线任务

例子：

- 删除文件或目录
- 数据库 schema 变更
- 数据迁移
- 改 `.env`
- 改密钥、token、CI/CD
- `git push`
- `git rebase`
- `git reset --hard`
- 强制推送
- 生产部署
- 公开发布

规则：

```text
必须先获得人工确认。
```

## 14. 通用任务卡模板

```text
# Agent Task Card

## Identity
- Role:
- Recommended model:
- Recommended framework:
- Risk level:
- Project area:

## Handoff
- Sender:
- Target framework:
- Target model:
- Target role:
- Payload type: Task Card
- Can execute directly: yes/no
- Requires verification: yes/no
- Requires human approval: yes/no

## Quota
- Recommended model quota status: high / medium / low / exhausted / unknown
- Quota source: user provided / framework reported / estimated / unknown
- Quota reset time:
- If quota is low:
- Fallback model:
- Fallback payload type:

## Goal
一句话说明要完成什么。

## Context
必须阅读的文件：
- ...

## Allowed Files
只允许修改：
- ...

## Forbidden Files
禁止修改：
- ...

## Input Contract
输入是什么。

## Output Contract
输出是什么。

## Steps
1. ...
2. ...
3. ...

## Acceptance Criteria
- ...
- ...

## Verification Commands
```bash
...
```

## Stop Conditions
遇到以下情况立刻停止：
- 需要改架构
- 需要新增依赖
- 需要改数据库
- 需要修改 forbidden files
- 测试失败但原因不明
- 发现任务卡边界不够
```

## 15. 架构锁模板

```text
# Architecture Lock

## Project Goal
这个项目最终解决什么问题。

## Core Users
谁使用这个系统。

## MVP Scope
当前阶段必须做什么。

## Out Of Scope
当前阶段明确不做什么。

## Tech Stack
- Frontend:
- Backend:
- Storage:
- Runtime:
- External services:

## Directory Ownership
| Directory | Owner | Rule |
|---|---|---|
| ... | ... | ... |

## Data Flow
数据从哪里来，经过哪些层，最后到哪里。

## State Management
状态放在哪里，谁可以修改。

## API / Contract Rules
哪些 schema 或 API 是真相源。

## Component / Module Boundaries
哪些模块可以互相调用，哪些不可以。

## Forbidden Changes
1. 不允许普通执行 Agent 修改架构锁。
2. 不允许随意新增依赖。
3. 不允许绕过既有 API 封装。
4. 不允许跨模块直接调用内部实现。
5. 不允许为了测试通过删除或绕过错误。

## High Risk Areas
必须由强模型或人工确认的区域。

## Verification
每类修改需要运行什么命令。
```

## 16. 审查流程

### 16.1 初审

适合 Gemini 或低成本 GPT。

检查：

- 是否遵守任务卡
- 是否修改 forbidden files
- 是否存在明显 mock / hardcoded / TODO
- 文档和实现是否一致
- UI 是否明显错位
- 测试是否运行

### 16.2 终审

适合 GPT / Claude。

检查：

- 架构方向是否正确
- diff 是否过大
- contract 是否漂移
- 是否引入长期技术债
- 测试是否证明真实路径
- 是否需要拆分提交

### 16.3 独立审计

适合高风险项目或多 Agent 并行后。

检查：

- Agent 是否越界
- 架构锁是否被破坏
- 任务卡是否和结果一致
- 是否有局部成功但整体方向错误的问题
- 是否应该继续、修改、暂停或阻断

### 16.4 多角度审查

复杂任务不能只做单一 diff review。审查应至少覆盖以下角度：

| 角度 | 目的 | 推荐执行方 |
|---|---|---|
| 架构审查 | 判断是否破坏架构锁、模块边界、数据流和 contract | Claude / GPT |
| 实现审查 | 判断代码是否正确、可维护、没有绕过和硬编码 | GPT / Codex |
| 验证审查 | 判断测试是否覆盖真实路径，而不是只覆盖孤立函数 | GPT / Claude |
| 功能效果审查 | 判断最终用户目标是否真的实现 | Human / GPT / Gemini |
| UI / 产物审查 | 判断截图、页面、文档、导出物是否符合预期 | Gemini / Codex browser / Human |
| 回归审查 | 判断是否影响旧功能、已有 contract 或公共 API | CI / Codex / GPT |
| 安全与红线审查 | 判断是否触及密钥、迁移、删除、发布、push 等红线 | Human / Claude / Codex |

审查输出必须说明：

```text
审查角度:
审查者:
审查范围:
证据:
结论:
阻断项:
建议 owner:
是否需要复核:
```

### 16.5 验证计划先确认

验证和审查也会消耗时间、额度和本地状态，因此不能无边界自动执行。

以下情况必须先向用户提交 `Review Plan` 或 `Verification Plan`，得到确认后再执行：

- 多 Agent 并行审查。
- 长流程验证，如全量测试、端到端测试、浏览器截图矩阵、长时间构建。
- 高成本模型参与的终审或架构审计。
- 可能产生大量文件、缓存、截图、报告或外部调用的验证。
- 需要访问外部服务、浏览器登录态、付费 API 或额度敏感资源。
- 验证计划可能触及红线操作，例如删除、迁移、发布、push、rebase、reset。

计划必须包含：

```text
Review / Verification Plan

## Goal
要验证什么最终效果。

## Scope
覆盖哪些文件、功能、页面、API、schema 或数据流。

## Angles
- architecture
- implementation
- functional effect
- regression
- UI / artifact
- security / red-line

## Commands / Actions
准备运行的命令或操作。

## Cost
- Expected model quota:
- Expected runtime:
- External services:
- Generated artifacts:

## Risk
- 是否修改文件:
- 是否写入缓存或产物:
- 是否触及红线:

## Stop Conditions
遇到什么情况停止并回报。

## Approval Needed
等待用户确认后执行。
```

低成本只读检查可以在项目规则明确授权时执行，但最终审查结论仍必须说明证据和剩余风险。

### 16.6 最终效果验收

避免“代码改了但最终效果没实现”，必须把验收目标写成用户可观察结果。

验收时至少回答：

```text
用户原始目标是什么？
最终效果在哪里可见？
用什么命令、截图、API 响应、报告或测试证明？
是否只验证了局部实现，而没有验证端到端效果？
还有哪些未验证风险？
```

如果无法验证最终效果，不能写“已完成”，只能写：

```text
实现已完成，但最终效果未验证。
```

## 17. 成本和效果平衡

不要把成本理解成单次调用价格。

真实成本包括：

```text
模型成本 = token 单价 × 上下文长度 × 往返次数
返工成本 = 架构错误概率 × 修复复杂度 × 下游影响面
验证成本 = 发现问题所需的人力和机器时间
机会成本 = 强模型剩余额度 × 今日后续高风险任务需求
```

真正省钱的做法：

```text
高返工风险任务先用强模型
低返工风险任务交给低成本模型
可自动验证任务优先批量化
不可自动验证任务提高审查强度
```

推荐预算分配：

| 阶段 | 成本占比 | 推荐模型 |
|---|---:|---|
| 项目理解 | 10% | Gemini / Claude |
| 架构设计 | 15% | Claude |
| 反方审查 | 5% | GPT |
| 任务拆解 | 5% | GPT |
| 批量实现 | 45%-55% | DeepSeek |
| 初步审查 | 5%-10% | Gemini |
| 终审 / 攻坚 | 10%-15% | GPT / Claude |

这个比例不是固定配方。每轮开始前必须根据 `Quota Snapshot` 调整：

- Claude / GPT 额度 `low` 时，只保留架构锁、blocker 和终审。
- DeepSeek 额度 `high` 时，也只能扩展 R1/R2 任务，不得上探到 R3/R4。
- Gemini 额度 `high` 时，优先承担只读扫描、文档一致性和初筛。
- 所有强模型额度 `low` 时，先暂停大架构改动，转向测试、整理任务卡和低风险修复。

## 18. 多 Agent 并行规则

多 Agent 并行前必须满足：

- 架构锁存在
- 任务卡存在
- allowed files 不重叠，或已有串行顺序
- shared contract 已冻结
- 验证计划存在
- 审查计划和验证计划已经提交用户确认；若项目规则授权自动执行，必须写明授权来源
- 当前工作区状态清楚
- 已记录 `Quota Snapshot`，或明确标记额度 `unknown` 并采用保守路由

推荐并行前先跑只读 baseline：

```text
Line V / Verification Snapshot
```

只读 baseline 应报告：

- 当前分支
- 当前 HEAD
- dirty worktree
- 测试状态
- 构建状态
- 已知 legacy / mock / deprecated 缺口
- Agent ownership 冲突
- 模型/框架额度快照和额度来源

并行实现时：

- 一个实现 Agent 只拥有一个明确模块、一个 feature surface 或一个 stage。
- 共享文件必须串行修改。
- 实现 Agent 不得顺手修 unrelated bug。
- 审查 Agent 默认只读。
- 合并前必须跑回归验证。

## 19. 失败处理

如果低成本模型失败，不要继续加同类 prompt 硬冲。

失败分流：

| 失败类型 | 处理 |
|---|---|
| 任务卡边界不清 | GPT 重新拆任务 |
| 架构理解错误 | Claude / GPT 重新审查方案 |
| 测试失败但原因明确 | DeepSeek 可继续修 |
| 测试失败且原因不明 | GPT / Claude 接手 |
| 触及 forbidden files | 立即停止并审查 |
| 需要新增依赖 | 暂停，人工确认 |
| 需要迁移 / 删除 / 发布 | 暂停，人工确认 |

## 20. 从 Finer OS 泛化出的经验

Finer OS 的实践可以抽象成以下通用模式：

| Finer 实践 | 通用含义 |
|---|---|
| `AGENTS.md` | 项目级 Agent 宪法 |
| F0-F8 stage | 明确架构分层和 ownership |
| `docs/specs/*` | contract 和任务边界 |
| Line V | 只读 baseline / verification gate |
| Agent task cards | 把开放式需求变成可执行任务 |
| Forbidden files | 防止 Agent 越界 |
| Acceptance commands | 用验证产物定义完成 |
| Independent auditor | 防止局部进展偏离总体架构 |

这些实践可以迁移到任何项目。关键不是使用 F0-F8 这个名字，而是建立同样的约束：

```text
每个 Agent 都知道自己是谁
每个任务都有明确边界
每个架构决策都有锁
每个完成状态都有验证
每个高风险操作都需要人工确认
```

## 21. 最小可执行版本

如果项目很小，不需要完整体系，可以使用最小版：

```text
1. 写 AGENTS.md
2. 写 architecture_lock.md
3. 让 Claude / GPT 做只读架构判断
4. 让 GPT 生成 3 到 10 张任务卡
5. 让 DeepSeek 按任务卡执行
6. 让 Gemini 做初审
7. 让 GPT 做终审
8. 跑测试和构建
```

最小版也必须保留三条底线：

```text
没有规则不动手
没有任务卡不交给低成本模型
没有验证不算完成
```
