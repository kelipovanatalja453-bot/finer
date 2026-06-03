# Card #9 Qwen / MiMo 接入修正与公平重跑

## AS-9a 接入规范差异说明

### 凭证与日志边界

- 运行只引用环境变量名：`MIMO_API_KEY`、`DASHSCOPE_API_KEY`、`DEEPSEEK_API_KEY`。
- 不把任何 API key 字面值写入代码、配置、注释、日志、报告或 commit。
- `.env` 已被 `.gitignore` 覆盖，执行者不修改 `.env`，只检查运行环境是否配置所需变量。

### MiMo

| 项目 | 当前接入 | 规范要求 | 判断 |
|---|---|---|---|
| base URL | `https://token-plan-cn.xiaomimimo.com/v1` | Token Plan OpenAI-compatible 中国集群使用 `https://token-plan-cn.xiaomimimo.com/v1`；具体以订阅管理页为准 | 当前 base URL 符合 CN token-plan 规范 |
| auth | `api-key` header，无 Bearer | OpenAI API 兼容支持 `api-key: $MIMO_API_KEY`，Token Plan 快速接入示例也使用 `api-key` | 当前鉴权 header 符合规范 |
| model | `mimo-v2.5-pro` | Token Plan 示例和 OpenAI API 示例均可使用 `mimo-v2.5-pro` | 当前模型串符合 F3 文本/推理对比目标 |
| token field | `max_completion_tokens` | MiMo 示例使用 `max_completion_tokens` | 当前 token 字段符合规范 |
| body extras | 统一 client 只发 `model/messages/temperature/max_completion_tokens` | 官方 OpenAI API 示例包含 `stream:false` 和 `thinking: {"type":"disabled"}` | 需补齐 provider-specific extra body，避免默认深度思考或流式/兼容差异导致长等待 |
| timeout | card #8 harness 默认为 20s | live 模型连通和 F3 抽取不应因过短 timeout 造成非公平失败 | 需把公平比对默认 timeout 提高到 90s；connectivity smoke 使用 30s |

最可能根因：MiMo card #8 的 8/8 timeout 不像是 base URL/header/token 字段错误，因为 B1 报告证明 `MiMo v2.5 via token-plan-cn.xiaomimimo.com` 曾完成 F3→F5，且当前配置已使用 token-plan base URL、`api-key`、`max_completion_tokens`。更可能是缺少 MiMo 官方示例中的 `thinking.disabled` 导致响应路径/耗时不受控，再叠加 card #8 的 20s timeout。

相关代码位置：

- `src/finer/model_config.py`: `ReasoningModelRegistry` 定义 `mimo-v2.5-pro`、token-plan base URL、`api-key`、`max_completion_tokens`。
- `src/finer/llm/client.py`: `LLMClient.chat()` 统一构造 request body，目前只合并 caller `extra_body`，没有 registry-level provider extras。
- `scripts/card8_f3_model_comparison.py`: `ModelSpec` 定义 MiMo 参数，默认 timeout 为 20s。
- `docs/specs/2026-06-02-b1-diagnostic-run-report.md`: B1 trace 记录 MiMo token-plan provider 曾产出 F3 intents 和 F5 actions。

### Qwen

| 项目 | 当前接入 | 规范要求 | 判断 |
|---|---|---|---|
| base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` | DashScope Beijing OpenAI-compatible base URL 为 `https://dashscope.aliyuncs.com/compatible-mode/v1` | 当前 base URL 符合规范 |
| auth | `Authorization: Bearer $DASHSCOPE_API_KEY` | OpenAI Chat API 示例使用 Bearer token | 当前鉴权符合规范 |
| model | `qwen-plus` | Qwen OpenAI Chat 示例使用 `qwen-plus` | 当前模型串符合规范 |
| token field | `max_tokens` | OpenAI-compatible Chat API 支持 OpenAI 风格字段 | 当前 token 字段符合规范 |
| timeout | card #8 harness 默认为 20s | card #8 中 Qwen 有成功返回但也有 timeout | 超时更可能来自延迟/20s 偏紧，不是请求格式错误 |

最可能根因：Qwen card #8 的 3/8 timeout 不支持“格式错”判断，因为同一配置下已有多条成功结果。保持 endpoint/header/model 不变，仅在 card #9 smoke 与公平重跑中提高 timeout 并记录延迟。

相关代码位置：

- `src/finer/model_config.py`: `TextModelRegistry` 定义 `qwen-plus`、DashScope compatible base URL、Bearer 默认 header。
- `scripts/card8_f3_model_comparison.py`: `ModelSpec` 定义 Qwen 参数，默认 timeout 为 20s。
- `scripts/test_glm_api.py`: 既有 Qwen text probe 使用相同 base URL、Bearer、`qwen-plus`。

### DeepSeek control

DeepSeek 作为 card #9 control，不修改 endpoint、header、model 或 provider body。只参与相同 smoke 和 F3 重跑条件，用于对比接入修正后的 Qwen/MiMo。

## AS-9b 连通性验证

运行入口：

- `scripts/card9_connectivity_probe.py`
- run_id: `20260603T144217`
- summary: `data/card9_connectivity/20260603T144217/summary.json`
- timeout: `30s`
- temperature: `0`
- 日志字段只包含 alias、model、base_url、api_key_env、status、latency、content preview 长度；不输出 key、headers 或完整 response。

| Model | Base URL | Env var | Status | Latency ms | Content chars |
|---|---|---|---:|---:|---:|
| qwen (`qwen-plus`) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `DASHSCOPE_API_KEY` | ok | 1060.43 | 11 |
| mimo (`mimo-v2.5-pro`) | `https://token-plan-cn.xiaomimimo.com/v1` | `MIMO_API_KEY` | ok | 3492.32 | 11 |
| deepseek (`deepseek-chat`) | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | ok | 1075.60 | 11 |

结论：三模型最小 `chat/completions` 请求均成功返回非空 content，未超时。MiMo 使用 token-plan base URL、`api-key` header、`max_completion_tokens`，并带 `stream:false` 与 `thinking: {"type":"disabled"}` provider body。Qwen 保持 DashScope OpenAI-compatible endpoint、Bearer 和 `max_tokens`，只提升 timeout。

## AS-9c 公平 F3 重跑

运行入口：

- `scripts/card8_f3_model_comparison.py`
- run_id: `20260603T144235`
- trace root: `data/card9_f3_model_comparison/20260603T144235`
- report: `docs/specs/2026-06-03-card9-f3-model-comparison-rerun.md`
- 条件：同 4 条真实 Feishu `ContentRecord`、同 F1 chat blocks、同现有 F3 prompt、`temperature=0`、每模型 2 次、timeout `90s`。
- 产物：24 个 `F3_result.json`、24 个脱敏 `model_call.json`。`model_call.json` 不含 `raw_response` 或 `parsed_response`，只记录长度与 parsed intent 数量。

| Model | Runs | Span grounding rate | Schema errors | Ticker issues | Determinism | Avg latency ms |
|---|---:|---:|---:|---:|---:|---:|
| qwen (`qwen-plus`) | 8 | 64.00% | 0 | 16 | 2/4 | 23708.41 |
| mimo (`mimo-v2.5-pro`) | 8 | 76.67% | 0 | 20 | 0/4 | 30549.28 |
| deepseek (`deepseek-chat`) | 8 | 89.74% | 0 | 22 | 0/4 | 8508.77 |

结论：card #9 重跑中三模型均实际产出 F3 结果，无大面积 timeout。MiMo 从 card #8 的 8/8 timeout 变为 8/8 成功，支持“缺少 provider body + timeout 偏紧”是主要接入失败原因。Qwen 在格式不变、timeout 提升后 8/8 成功，支持“20s 偏紧”判断。该结果仍是 N=4、无 gold label 的定性选择参考，不是 benchmark。
