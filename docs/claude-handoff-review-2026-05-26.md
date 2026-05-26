# Claude Handoff Review - 2026-05-26

## Agent Handoff

### Sender
- Source framework: Codex desktop
- Model: GPT-5
- Role: local audit, cleanup, verification runner

### Target
- Target framework: Claude Code
- Target role: architect / high-risk implementer / reviewer
- Payload type: Diff Review + Handoff Report
- Risk level: R3
- Can execute directly: no
- Requires human approval: yes, before deleting files, migrating data, changing CI/CD, pushing, or publishing
- Requires verification: yes

### Context Pointers
- Project rules: `AGENTS.md`, `CLAUDE.md`
- Canonical architecture: `docs/ARCHITECTURE.md`, `docs/specs/f-stage-contracts.md`
- F1 contract: `docs/specs/f1-standardization-contract.md`
- Multi-agent model: `docs/specs/vibe-agent-operating-model.md`
- Current handoff report: this file

## Conclusion

结论：REVISE.

当前工作树可以交给 Claude Code 继续审查和收敛，但不要直接合并。主要原因是 F0 微信视频号接入把外部 downloader 源码作为半成品带入仓库，F8 存储改动和前端布局修正已通过 targeted validation，但外部 downloader 的授权、构建方式、运行时产物和安全边界还没有正式定稿。

## Worktree Snapshot

Base branch:
- `main...origin/main`

Tracked modified files:
- `docs/specs/vibe-agent-operating-model.md`
- `scripts/run_backtest_e2e.py`
- `src/finer/api/routes/backtest.py`
- `src/finer/api/routes/wechat.py`
- `src/finer/backtest/storage.py`
- `src/finer/ingestion/wechat_adapter.py`
- `src/finer_dashboard/src/app/globals.css`
- `src/finer_dashboard/src/app/page.tsx`
- `src/finer_dashboard/src/components/layout/main-board.tsx`
- `src/finer_dashboard/src/components/layout/source-filter.tsx`
- `src/finer_dashboard/src/components/layout/upload-button.tsx`
- `tests/test_backtest.py`

Untracked feature files:
- `scripts/generate_agent_task_card.py`
- `src/finer/task_cards.py`
- `tests/test_task_cards.py`
- `tests/test_wechat_channels_f0.py`
- `scripts/wx_channels_download/`

Cleanup already performed:
- Removed local `.DS_Store`, `.pytest_cache/`, `.playwright-cli/`, `__pycache__/`, and `*.pyc` outside `.venv`, `node_modules`, `.git`, and `scripts/wx_channels_download`.
- Removed untracked frontend Playwright screenshots matching `output/playwright/frontend-*.png`.
- Preserved existing tracked Playwright screenshots under `output/playwright/`.

## Change Summary

### F0 WeChat Channels Intake

Files:
- `src/finer/ingestion/wechat_adapter.py`
- `src/finer/api/routes/wechat.py`
- `tests/test_wechat_channels_f0.py`
- `scripts/wx_channels_download/`

What changed:
- Added `WeChatChannelsDownloadClient`.
- Added `WeChatChannelsF0Importer`.
- Added `POST /api/wechat/channels/import`.
- Writes raw video/profile artifacts, canonical `ContentRecord`, and import receipt under F0 paths.
- Keeps the endpoint intentionally F0-only; it does not call F1-F8.

Known risks:
- `scripts/wx_channels_download/` is an external Go project carried into the worktree as a half-finished dependency.
- Local runtime files are not part of the intended submission: `app.log`, `gopeed.db`, `*.key`, local binary `wx_video_download`, and other ignored build artifacts.
- A hardcoded Cloudflare API token was found in `scripts/wx_channels_download/pkg/cloudflare/pages/api.go` during handoff cleanup and replaced with `CLOUDFLARE_API_TOKEN` environment-variable loading.
- `ContentRecord.source_type` remains `"unclassified"` with metadata note `source_kind=wechat_channels_video` because the F0 core enum/contract has not been formally extended.
- The default downloader binary path points at `scripts/wx_channels_download/wx_video_download`; if the binary is ignored or absent, the receiver must build or configure it.

Claude next step:
1. Audit `scripts/wx_channels_download/` license, secrets, certificate files, and build process before staging it.
2. Decide whether the downloader should remain vendored, become a submodule, or be replaced by a documented external install path.
3. If vendored, add an explicit README section for how to build `wx_video_download` and how the local API is started.
4. Formalize F0 schema support for `wechat_channels_video` instead of keeping `source_type="unclassified"` indefinitely.

### F8 Backtest Artifact Store

Files:
- `src/finer/backtest/storage.py`
- `src/finer/api/routes/backtest.py`
- `scripts/run_backtest_e2e.py`
- `tests/test_backtest.py`

What changed:
- Added shared F8 artifact storage helpers.
- KOL-attributed runs save under `data/review/{kol_id}/F8_backtest/`.
- Legacy `data/F8_metrics` read path remains compatible.
- API list/detail/delete paths now read the shared F8 artifact layout.
- E2E script writes through the same storage helper as API.

Known risks:
- `delete_f8_backtest_result` deletes result artifacts and must remain behind explicit API intent; do not run destructive cleanup during handoff.
- Full regression was not run; only targeted backtest tests were run.

Claude next step:
1. Review F8 storage naming and whether `data/review/{kol_id}/F8_backtest` is the final canonical layout.
2. Check whether API response shape changed in a way the dashboard expects.
3. Run broader F8 and API regression before merge.

### Agent Task Cards

Files:
- `src/finer/task_cards.py`
- `scripts/generate_agent_task_card.py`
- `tests/test_task_cards.py`
- `docs/specs/vibe-agent-operating-model.md`

What changed:
- Added task-card generator from F-stage contracts and parallel line contracts.
- Expanded operating model with handoff envelope, framework routing, quota fields, review/verification plan rules, and final-effect validation language.

Known risks:
- The parser depends on current Markdown headings in docs/specs. A doc restructure may break task card generation.
- It is a helper, not a replacement for human/architectural review.

Claude next step:
1. Review whether this helper belongs in `src/finer/` or should live under `scripts/` only.
2. Check generated task cards against actual multi-agent workflow needs.

### Frontend Layout Fixes

Files:
- `src/finer_dashboard/src/app/globals.css`
- `src/finer_dashboard/src/app/page.tsx`
- `src/finer_dashboard/src/components/layout/main-board.tsx`
- `src/finer_dashboard/src/components/layout/source-filter.tsx`
- `src/finer_dashboard/src/components/layout/upload-button.tsx`

What changed:
- Removed negative global letter spacing.
- Added responsive wrapping/truncation and stable sizing to prevent header/card/button text overflow.

Known risks:
- Browser screenshot verification from the earlier work produced local frontend images, but those untracked screenshots were cleaned from handoff.
- Current validation is lint-only after cleanup.

Claude next step:
1. Run browser verification for dashboard desktop and mobile widths if UI changes are going to merge.
2. Confirm layout does not regress the F8 dashboard screenshots already tracked under `output/playwright/`.

## Validation Performed

Commands run:

```bash
pytest tests/test_wechat_channels_f0.py tests/test_task_cards.py tests/test_backtest.py -q
```

Result:
- 35 passed
- 10 warnings
- Warnings are deprecation warnings from existing Pydantic/FastAPI usage.

```bash
npm run lint
```

Working directory:
- `src/finer_dashboard`

Result:
- Passed.

```bash
git diff --check
```

Result:
- Passed.

```bash
rg -n "d1zCvKDV|CLOUDFLARE_API_TOKEN\s*:=\s*\"|Bearer [A-Za-z0-9_-]{20,}" scripts/wx_channels_download --glob '!internal/interceptor/inject/lib/**'
```

Result:
- No matches after replacing the hardcoded Cloudflare token.

## Blockers Before Merge

| Severity | Area | Issue | Evidence | Required Fix |
|---|---|---|---|---|
| P1 | F0 dependency | `scripts/wx_channels_download/` is vendored as half-finished source without a finalized dependency policy | F0 code defaults to `scripts/wx_channels_download/wx_video_download`; directory is untracked external Go source | Decide vendoring/submodule/external install; document build/start; exclude runtime and secret-like files |
| P1 | Security | External downloader tree contains `pkg/certificate/certs/private.key` locally; it is ignored and must not be staged | `git status --ignored scripts/wx_channels_download/pkg/certificate/certs/private.key` shows it ignored | Do not stage private keys; remove local file only after confirming upstream build expectations |
| P2 | F0 schema | WeChat Channels uses `source_type="unclassified"` | `wechat_adapter.py` metadata carries `schema_note` | Add canonical source type or documented migration path |
| P2 | Frontend verification | Layout fixes are linted but not screenshot-verified after cleanup | `npm run lint` passed; screenshots cleaned as local artifacts | Run browser smoke before merging UI changes |
| P2 | Docs drift | Historical V0/V1 docs remain in repo | README marks V0/V1 report historical; legacy docs still exist | Keep historical docs clearly labelled or move to archive in a separate approved cleanup |

## Recommended Claude Plan

1. Read `AGENTS.md`, `CLAUDE.md`, and this handoff report.
2. Run `git status --short --ignored scripts/wx_channels_download` and decide what belongs in version control.
3. Review F0 files first: `src/finer/ingestion/wechat_adapter.py`, `src/finer/api/routes/wechat.py`, `tests/test_wechat_channels_f0.py`.
4. Review F8 storage/API second: `src/finer/backtest/storage.py`, `src/finer/api/routes/backtest.py`, `scripts/run_backtest_e2e.py`, `tests/test_backtest.py`.
5. Run targeted validation again.
6. Only after F0 dependency policy is decided, stage files intentionally.

## Do Not Do

- Do not push from Claude without explicit user approval.
- Do not commit `.env`, logs, DB files, local binary artifacts, or private keys.
- Do not run destructive F8 delete flows as part of validation.
- Do not expand F0 import into F1/F2 processing inside the route.
- Do not introduce L0-L8 or V0-V6 naming into new canonical code.
