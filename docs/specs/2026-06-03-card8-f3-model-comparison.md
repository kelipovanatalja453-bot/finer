# Card #8 F3 real-model comparison

## Scope note

This is a qualitative selection aid, not a benchmark: N=4 real Feishu messages, no gold labels, and ticker checks are limited to obvious target hints in the source text.

## Run config

- run_id: `20260603T111933`
- trace_root: `data/card8_f3_model_comparison/20260603T111933`
- pipeline: card #7 Feishu importer -> F1 StandardizationRouter -> F3 LLMIntentExtractor
- golden_path only for the later selected-model F5 run; no orchestrator
- F3 prompt: existing `src/finer/prompts/f3_intent_extraction/{system,user}.j2`
- temperature: `0` for every model and every repeat
- repeats: `2` per model per message

## Objective table

| Model | Runs | Span grounding rate | Schema errors | Ticker issues | Determinism | Avg latency ms |
|---|---:|---:|---:|---:|---:|---:|
| qwen (`qwen-plus`) | 8 | 22.22% | 0 | 10 | 2/4 | 17877.39 |
| mimo (`mimo-v2.5-pro`) | 8 | 0.00% | 0 | 12 | 4/4 | 20317.65 |
| deepseek (`deepseek-chat`) | 8 | 89.47% | 0 | 18 | 0/4 | 10137.88 |

## Selection

Selected F3 model for card #7 real end-to-end completion: `deepseek-chat`.

Rationale: MiMo was not usable in this run because all 8 real API calls timed out. Qwen returned some valid intents, but it timed out on 3/8 runs, fell back to block-level evidence on most successful rows, and mis-normalized 腾讯音乐 as `1698.HK`. DeepSeek was the only model with 8/8 successful calls, the best span grounding rate, and the lowest average latency. It is not clean: it over-splits the 黄金股 message and invents pseudo/related tickers for sectors and themes. The decision is therefore "good enough to move card #7 real mode forward", not a benchmark win.

## Per-message side-by-side

### feishu_892649419e68b4b906717f27

- published_at: `2026-03-12T15:36:00+08:00`
- obvious target hint: `绿电`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | 绿电/GREEN_POWER bullish opinion none conv=0.75 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.8 evidence=block_level | no valid intent | no | Not selected: timeout on repeat 2 and pseudo ticker normalization. |
| mimo | no valid intent | no valid intent | yes | Not selected: both calls timed out. |
| deepseek | 绿电/GREEN_POWER bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.5 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.5 evidence=intent_keyword<br>绿电/GREEN_POWER bearish explicit_action reduce conv=0.6 evidence=intent_keyword | 绿电/GREEN_POWER bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.5 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.5 evidence=intent_keyword<br>绿电/GREEN_POWER bearish explicit_action reduce conv=0.6 evidence=intent_keyword | no | Best available: captures sell/reduce signal with exact keyword evidence, but over-generates theme tickers. |

### feishu_e02dc3c2554f6abe016d39f1

- published_at: `2026-03-12T16:43:00+08:00`
- obvious target hint: `阿特斯`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | 阿特斯/688472.SH bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能/CSIQ bullish opinion none conv=0.75 evidence=block_level | 阿特斯/688472.SH bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能/CSIQ bullish opinion none conv=0.75 evidence=block_level | no | Usable content, but evidence is block-level fallback and dual listing creates review burden. |
| mimo | no valid intent | no valid intent | yes | Not selected: both calls timed out. |
| deepseek | 阿特斯/688472.SH bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能/CSIQ bullish opinion none conv=0.8 evidence=block_level | 阿特斯/CSIQ bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能 CSIQ/CSIQ bullish opinion none conv=0.8 evidence=block_level | no | Slightly worse ticker stability than Qwen on this row, but no timeout and still valid intent. |

### feishu_70a96bcd4a33f9f6a7432204

- published_at: `2026-03-12T19:51:00+08:00`
- obvious target hint: `腾讯音乐`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | 腾讯音乐/1698.HK bullish opinion none conv=0.7 evidence=block_level | 腾讯音乐/1698.HK bullish opinion none conv=0.7 evidence=block_level | yes | Not selected: wrong ticker for 腾讯音乐 and block-level fallback. |
| mimo | no valid intent | no valid intent | yes | Not selected: both calls timed out. |
| deepseek | 腾讯音乐/TME bullish opinion none conv=0.65 evidence=intent_keyword | 腾讯音乐/TME bullish opinion none conv=0.65 evidence=intent_keyword | no | Best row: correct `TME`, exact evidence, concise single intent. |

### feishu_dd24a98d73e6711b03660703

- published_at: `2026-03-13T18:14:00+08:00`
- obvious target hint: `黄金股`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | no valid intent | no valid intent | yes | Not selected: both calls produced no valid intent because of timeout. |
| mimo | no valid intent | no valid intent | yes | Not selected: both calls timed out. |
| deepseek | 泡泡玛特/9992.HK bullish opinion hold conv=0.75 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>吉利/0175.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.65 evidence=intent_keyword<br>阅文/0772.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>TCL/000100.SZ neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>名创/9896.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion none conv=0.5 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion none conv=0.5 evidence=intent_keyword | 泡泡玛特/9992.HK bullish opinion hold conv=0.75 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>吉利/0175.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.65 evidence=intent_keyword<br>阅文/0772.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>TCL/000100.SZ neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>名创/9896.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion none conv=0.5 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion none conv=0.5 evidence=intent_keyword | no | Selected with caveat: only successful model, but this row shows serious over-splitting and needs reviewer cleanup. |

## Evidence files

- Intent dumps and model-call logs: `data/card8_f3_model_comparison/20260603T111933/models`
- Shared F0/F1 inputs: `data/card8_f3_model_comparison/20260603T111933/inputs`
- Card #7 real selected-model F5 run: `data/card7_feishu_real_f5/card8_deepseek_real_f5`
- Selected-model manifest: `data/packs/maodaren/feishu_f0_real_card8_deepseek_real_f5/manifest.json`

## AS-8c selected-model real F5 evidence

- selected model config in run log: `model=deepseek-chat`, `base_url=https://api.deepseek.com`, `api_key_env=DEEPSEEK_API_KEY`
- runner mode: `--llm-mode real`; no fixture server and no monkey patch were used
- summary checks: `AS-3a any_f5_action=True`, `AS-3b proof_timestamp_preserved=True`, `AS-3c non_fallback_f1=True`
- four-clock screenshot: `data/card7_feishu_real_f5/card8_deepseek_real_f5/as8c_tme_four_clocks.png`
- real F3 sample: `data/card7_feishu_real_f5/card8_deepseek_real_f5/feishu_70a96bcd4a33f9f6a7432204/F3_intents/139dbf38-7bb9-4835-beb2-e8cfcf5f03b7.json`
  - `target_name=腾讯音乐`, `target_symbol=TME`, `direction=bullish`, `actionability=opinion`, `position_delta_hint=none`, `conviction=0.65`
- corresponding F5 action: `data/card7_feishu_real_f5/card8_deepseek_real_f5/feishu_70a96bcd4a33f9f6a7432204/F5_trade_action.json`
  - `target.ticker=TME`, `canonical_trace_status=canonical`, `intent_id=139dbf38-7bb9-4835-beb2-e8cfcf5f03b7`
  - four clocks: `intent_published_at=2026-03-12T19:51:00+08:00`, `intent_effective_at=null`, `action_decision_at=2026-03-12T19:51:00+08:00`, `action_executable_at=2026-03-13T09:30:00+08:00`

## Reviewer notes

- Selection rule should prioritize valid schema, exact keyword grounding over block-level fallback, no obvious ticker errors, deterministic repeats, then latency.
- The `Reviewer judgment` column is filled as the first annotation batch for these four messages.
- DeepSeek should move forward only as the current F3 real-mode default; it still needs post-selection cleanup work around over-splitting and pseudo ticker normalization.
