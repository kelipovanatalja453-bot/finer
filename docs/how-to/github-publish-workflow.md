# GitHub Publish Workflow

本文档固化 Finer OS 后续推送到 GitHub 的标准流程。目标是避免漏提交 fixture、漏跑验证、把本地生成物混进 commit，或推送后才发现 GitHub Actions 失败。

## 默认路径

1. 确认目录与分支。

   ```bash
   pwd
   git status --short --branch
   git branch --show-current
   ```

2. 先做 dry run，看本次会发布什么。

   ```bash
   scripts/publish_to_github.sh --message "docs: update publish workflow" --dry-run
   make publish-dry-run MSG="docs: update publish workflow"
   ```

3. 正式提交到本地。

   ```bash
   scripts/publish_to_github.sh --message "docs: update publish workflow"
   make publish MSG="docs: update publish workflow"
   ```

4. 需要推送时，显式加 `--push --watch`。

   ```bash
   scripts/publish_to_github.sh --message "docs: update publish workflow" --push --watch
   make publish MSG="docs: update publish workflow" ARGS="--push --watch"
   ```

`--watch` 会等待最新 GitHub Actions。若 GitHub 返回失败，先读取失败日志，修复根因后再提交和推送下一轮。

## 本地验证

脚本默认会运行：

```bash
python -m pip install -e '.[dev]'
pytest tests/ -v
cd src/finer_dashboard && npm ci && npm run lint && npm run build
```

只有在明确知道本次改动不需要验证时才使用：

```bash
scripts/publish_to_github.sh --message "docs: typo fix" --skip-tests
make publish MSG="docs: typo fix" ARGS="--skip-tests"
```

## 提交范围

脚本会在提交前展示：

```bash
git status --short --branch
git diff --stat
git diff --cached --stat
```

如果工作区混有无关改动，不要继续。先拆分改动或手动暂存目标文件。

## 推送规则

- `git push` 是红线操作，必须显式传 `--push`，并在交互确认后才执行。
- 默认推送当前分支到 `origin`，不会自动切分支。
- `main` 可用于用户明确要求直接推主线的场景；普通功能开发优先使用 `codex/<description>` 分支和 PR。
- GitHub Actions 失败时，不用绕过测试。读取日志，补依赖、补 fixture 或修代码，再推下一轮。

## 常见失败处理

缺 Python 依赖：

```bash
gh run view <run-id> --log-failed
```

把运行时代码直接 import 的依赖放进 `[project].dependencies`；只在测试中使用的依赖放进 `[project.optional-dependencies].dev`。

缺前端 lockfile：

确认 `src/finer_dashboard/package-lock.json` 没有被 `.gitignore` 拦住，并使用 `npm ci` 复现。

缺 fixture：

确认 fixture 文件未被全局 `*.json` 等规则忽略：

```bash
git check-ignore -v tests/fixtures/path/to/file.json
```

Docs workflow 权限问题：

默认只验证 docs artifact。只有仓库变量 `ENABLE_PAGES_DEPLOY=true` 时才启用 GitHub Pages 部署。
