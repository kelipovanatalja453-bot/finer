# Card #9 F3 real-model comparison rerun

## Scope note

This is a qualitative selection aid, not a benchmark: N=4 real Feishu messages, no gold labels, and ticker checks are limited to obvious target hints in the source text.

## Run config

- run_id: `20260603T144235`
- trace_root: `data/card9_f3_model_comparison/20260603T144235`
- pipeline: card #7 Feishu importer -> F1 StandardizationRouter -> F3 LLMIntentExtractor
- golden_path only for the later selected-model F5 run; no orchestrator
- F3 prompt: existing `src/finer/prompts/f3_intent_extraction/{system,user}.j2`
- temperature: `0` for every model and every repeat
- repeats: `2` per model per message
- connectivity smoke: `data/card9_connectivity/20260603T144217/summary.json`, all three models returned non-empty content without timeout

## Objective table

| Model | Runs | Span grounding rate | Schema errors | Ticker issues | Determinism | Avg latency ms |
|---|---:|---:|---:|---:|---:|---:|
| qwen (`qwen-plus`) | 8 | 64.00% | 0 | 16 | 2/4 | 23708.41 |
| mimo (`mimo-v2.5-pro`) | 8 | 76.67% | 0 | 20 | 0/4 | 30549.28 |
| deepseek (`deepseek-chat`) | 8 | 89.74% | 0 | 22 | 0/4 | 8508.77 |

## Rerun conclusion

Card #9 fixed the access failure mode: Qwen, MiMo, and DeepSeek all completed 8/8 F3 calls under the same four-message setup, `temperature=0`, and two repeats. MiMo changed from 8/8 timeout in card #8 to 8/8 successful real responses after adding MiMo provider body and increasing the fair timeout. Qwen also no longer timed out, which supports the card #9 diagnosis that the prior 20s timeout was too tight.

This is still a qualitative selection aid, not a benchmark. DeepSeek remains the fastest and has the highest span grounding rate in this N=4 rerun. MiMo is now usable and has better grounding than Qwen, but it still mis-normalizes 腾讯音乐 as `01698.HK` and over-splits the 黄金股 message. Qwen improved availability but still has block-level fallback and ticker issues.

## Per-message side-by-side

### feishu_892649419e68b4b906717f27

- published_at: `2026-03-12T15:36:00+08:00`
- obvious target hint: `绿电`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | 绿电/GREEN_POWER bullish opinion none conv=0.75 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.8 evidence=block_level | 绿电/GREEN_POWER bullish opinion none conv=0.75 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.8 evidence=block_level | yes | Stable and usable, but misses the bearish reduce signal and emits pseudo theme tickers. |
| mimo | 绿电/GREEN_POWER bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.6 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.6 evidence=intent_keyword | 绿电/GREEN_POWER bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.6 evidence=block_level<br>储能/ENERGY_STORAGE bullish opinion none conv=0.6 evidence=block_level | no | Now available; cleaner than Qwen on run 1, but repeat 2 falls back for secondary themes and still misses reduce. |
| deepseek | 绿电/GREEN_POWER bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.5 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.5 evidence=intent_keyword<br>绿电/GREEN_POWER bearish explicit_action reduce conv=0.6 evidence=intent_keyword | 绿电/GREEN_POWER bullish opinion none conv=0.7 evidence=intent_keyword<br>算电协同/COMPUTE_POWER bullish opinion none conv=0.5 evidence=intent_keyword<br>储能/ENERGY_STORAGE bullish opinion none conv=0.5 evidence=intent_keyword<br>绿电/GREEN_POWER bearish explicit_action reduce conv=0.6 evidence=intent_keyword | no | Best for this row: captures both positive theme context and explicit reduce signal with exact evidence. |

### feishu_e02dc3c2554f6abe016d39f1

- published_at: `2026-03-12T16:43:00+08:00`
- obvious target hint: `阿特斯`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | 阿特斯/688472.SH bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能/CSIQ bullish opinion none conv=0.75 evidence=block_level<br>储能/ENERGY_STORAGE bullish opinion none conv=0.65 evidence=block_level | 阿特斯/688472.SH bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能/CSIQ bullish opinion none conv=0.75 evidence=block_level | no | Best ticker handling for A-share 阿特斯, but unstable extra 储能 intent and all evidence is block-level. |
| mimo | 阿特斯/CSIQ bullish opinion none conv=0.6 evidence=block_level<br>阿特斯太阳能CSIQ/CSIQ bullish opinion none conv=0.7 evidence=block_level<br>储能/ENERGY_STORAGE bullish opinion none conv=0.65 evidence=block_level | 阿特斯/CSIQ bullish opinion none conv=0.6 evidence=block_level<br>阿特斯太阳能CSIQ/CSIQ bullish opinion none conv=0.7 evidence=block_level | no | Usable but prefers CSIQ and has the same unstable extra 储能 intent as Qwen. |
| deepseek | 阿特斯/CSIQ bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能 CSIQ/CSIQ bullish opinion none conv=0.8 evidence=block_level | 阿特斯/CSIQ bullish opinion none conv=0.7 evidence=block_level<br>阿特斯太阳能 CSIQ/CSIQ bullish opinion none conv=0.85 evidence=block_level | no | Concise and fast, but misses the obvious `688472.SH` candidate and still uses block-level evidence. |

### feishu_70a96bcd4a33f9f6a7432204

- published_at: `2026-03-12T19:51:00+08:00`
- obvious target hint: `腾讯音乐`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | 腾讯音乐/1698.HK bullish opinion none conv=0.7 evidence=block_level | 腾讯音乐/1698.HK bullish opinion none conv=0.7 evidence=block_level | yes | Not acceptable without F2 cleanup: wrong ticker and block-level fallback. |
| mimo | 腾讯音乐/01698.HK bullish opinion none conv=0.6 evidence=intent_keyword | 腾讯音乐/01698.HK bullish opinion none conv=0.6 evidence=intent_keyword | no | Better evidence than Qwen but still wrong ticker for 腾讯音乐. |
| deepseek | 腾讯音乐/TME bullish opinion none conv=0.65 evidence=intent_keyword<br>腾讯音乐/TME bullish opinion none conv=0.4 evidence=intent_keyword | 腾讯音乐/TME bullish opinion none conv=0.65 evidence=intent_keyword | no | Best row-level choice: correct `TME` and exact evidence, though run 1 over-splits into a duplicate lower-conviction intent. |

### feishu_dd24a98d73e6711b03660703

- published_at: `2026-03-13T18:14:00+08:00`
- obvious target hint: `黄金股`

| Model | Run 1 | Run 2 | Deterministic | Reviewer judgment |
|---|---|---|---:|---|
| qwen | 泡泡玛特/9992.HK bullish opinion none conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion none conv=0.75 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion none conv=0.65 evidence=intent_keyword<br>阅文/0772.HK neutral opinion none conv=0.4 evidence=intent_keyword<br>TCL/000100.SZ neutral opinion none conv=0.4 evidence=intent_keyword<br>名创优品/9991.HK neutral opinion none conv=0.4 evidence=intent_keyword | 泡泡玛特/9992.HK bullish opinion none conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion none conv=0.75 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion none conv=0.65 evidence=intent_keyword<br>阅文/0772.HK neutral opinion none conv=0.4 evidence=intent_keyword<br>TCL/000100.SZ neutral opinion none conv=0.4 evidence=intent_keyword<br>名创优品/9991.HK neutral opinion none conv=0.4 evidence=intent_keyword | no | Stable shape but broad and over-split; misses the 黄金股 abstraction. |
| mimo | 泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.65 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.6 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.6 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.55 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion reduce conv=0.6 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion reduce conv=0.55 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.5 evidence=intent_keyword | 泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.65 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.65 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.6 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion none conv=0.6 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion reduce conv=0.65 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.6 evidence=intent_keyword<br>泡泡玛特/9992.HK mixed opinion none conv=0.5 evidence=intent_keyword | no | Most focused on 泡泡玛特 and exact evidence, but duplicate/contradictory intents need F2/F3 cleanup. |
| deepseek | 泡泡玛特/9992.HK bullish opinion hold conv=0.75 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>吉利/0175.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.65 evidence=intent_keyword<br>阅文/0772.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>名创/9896.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion none conv=0.5 evidence=intent_keyword<br>泡泡玛特/9992.HK mixed opinion none conv=0.5 evidence=intent_keyword | 泡泡玛特/9992.HK bullish opinion hold conv=0.75 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>吉利/0175.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.7 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion hold conv=0.65 evidence=intent_keyword<br>阅文/0772.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>TCL/000100.SZ neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>名创/9896.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK neutral opinion hold conv=0.3 evidence=intent_keyword<br>泡泡玛特/9992.HK bearish opinion none conv=0.5 evidence=intent_keyword<br>泡泡玛特/9992.HK bullish opinion none conv=0.5 evidence=intent_keyword | no | Highest coverage but serious over-splitting; usable only with downstream dedupe/review. |

## Evidence files

- Intent dumps and model-call logs: `data/card9_f3_model_comparison/20260603T144235/models`
- Shared F0/F1 inputs: `data/card9_f3_model_comparison/20260603T144235/inputs`
- Connectivity logs: `data/card9_connectivity/20260603T144217`

## Reviewer notes

- Selection rule should prioritize valid schema, exact keyword grounding over block-level fallback, no obvious ticker errors, deterministic repeats, then latency.
- The `Reviewer judgment` column is filled as the first card #9 annotation pass.
- Ticker mistakes and over-splitting remain out of scope for card #9; they should be handled by F2/F3 cleanup work, not by changing the F3 prompt or schema here.
