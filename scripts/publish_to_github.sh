#!/usr/bin/env bash
# Finer OS GitHub publish helper.
# It validates the repo, commits the intended local changes, optionally pushes,
# and can wait for GitHub Actions when a push is performed.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/publish_to_github.sh --message "commit message" [options]

Options:
  --message, -m MSG       Required commit message.
  --push                  Push the current branch after committing.
  --watch                 After pushing, wait for the latest GitHub Actions runs.
  --dry-run               Show scope and validation commands without staging.
  --skip-tests            Skip local backend/frontend validation.
  --yes, -y               Do not prompt before commit/push.
  --help, -h              Show this help.

Examples:
  scripts/publish_to_github.sh -m "docs: update github publish workflow" --dry-run
  scripts/publish_to_github.sh -m "fix: stabilize f1 parser"
  scripts/publish_to_github.sh -m "ci: update workflow" --push --watch
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

confirm() {
  local prompt="$1"
  if [[ "$YES" == "1" ]]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

run_cmd() {
  echo "+ $*"
  "$@"
}

COMMIT_MSG=""
DO_PUSH=0
WATCH=0
DRY_RUN=0
SKIP_TESTS=0
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --message|-m)
      [[ $# -ge 2 ]] || die "--message requires a value"
      COMMIT_MSG="$2"
      shift 2
      ;;
    --push)
      DO_PUSH=1
      shift
      ;;
    --watch)
      WATCH=1
      DO_PUSH=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --skip-tests)
      SKIP_TESTS=1
      shift
      ;;
    --yes|-y)
      YES=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$COMMIT_MSG" ]] || {
  usage
  die "Commit message is required"
}

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "Not inside a git repository"
cd "$REPO_ROOT"

CURRENT_BRANCH="$(git branch --show-current)"
[[ -n "$CURRENT_BRANCH" ]] || die "Cannot determine current branch"

echo "Repository: $REPO_ROOT"
echo "Branch:     $CURRENT_BRANCH"
echo "Message:    $COMMIT_MSG"
echo

run_cmd git status --short --branch

if git diff --quiet && git diff --cached --quiet; then
  die "No local changes to publish"
fi

echo
echo "Change summary:"
git diff --stat
git diff --cached --stat

echo
echo "Files to be included after staging:"
git status --short

if [[ "$SKIP_TESTS" == "0" ]]; then
  echo
  echo "Running local validation..."
  run_cmd python -m pip install -e '.[dev]'
  run_cmd pytest tests/ -v
  if [[ -f src/finer_dashboard/package-lock.json ]]; then
    run_cmd bash -lc 'cd src/finer_dashboard && npm ci && npm run lint && npm run build'
  fi
else
  echo
  echo "Skipping local validation by request."
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "Dry run complete. Nothing was staged, committed, or pushed."
  exit 0
fi

echo
confirm "Stage all current local changes and commit?" || die "Canceled before staging"
run_cmd git add -A
run_cmd git diff --cached --stat
run_cmd git commit -m "$COMMIT_MSG"

if [[ "$DO_PUSH" == "1" ]]; then
  echo
  confirm "Push branch '$CURRENT_BRANCH' to origin?" || die "Canceled before push"
  run_cmd git push origin "$CURRENT_BRANCH"

  if [[ "$WATCH" == "1" ]]; then
    command -v gh >/dev/null 2>&1 || die "gh is required for --watch"
    echo
    echo "Waiting for latest GitHub Actions runs on $CURRENT_BRANCH..."
    sleep 8
    mapfile -t RUN_IDS < <(gh run list --branch "$CURRENT_BRANCH" --limit 2 --json databaseId --jq '.[].databaseId')
    for run_id in "${RUN_IDS[@]}"; do
      run_cmd gh run watch "$run_id" --exit-status
    done
  fi
fi

echo
run_cmd git status --short --branch
echo "Done."
