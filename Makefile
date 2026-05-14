.PHONY: dev-backend dev-frontend dev-all test test-frontend lint build clean install typecheck init-storage feishu-sync publish-dry-run publish

# Development
dev-backend:
	uvicorn finer.api.server:app --reload --port 8000

dev-frontend:
	cd src/finer_dashboard && npm run dev

dev-all:
	@echo "Starting backend (port 8000) and frontend (port 3000)..."
	@make -j2 dev-backend dev-frontend

# Testing
test:
	pytest tests/ -v

test-frontend:
	cd src/finer_dashboard && npx playwright test

# Linting
lint:
	python -m ruff check src/finer
	cd src/finer_dashboard && npm run lint

# Type checking
typecheck:
	cd src/finer_dashboard && npx tsc --noEmit

# Build
build:
	python -m build
	cd src/finer_dashboard && npm run build

# Install dependencies
install:
	pip install -e .
	cd src/finer_dashboard && npm install

# CLI
init-storage:
	python -m finer.cli init-storage

feishu-sync:
	python -m finer.cli feishu-sync

# GitHub publishing
publish-dry-run:
	@test -n "$(MSG)" || (echo "Usage: make publish-dry-run MSG='commit message'" && exit 1)
	scripts/publish_to_github.sh --message "$(MSG)" --dry-run $(ARGS)

publish:
	@test -n "$(MSG)" || (echo "Usage: make publish MSG='commit message'" && exit 1)
	scripts/publish_to_github.sh --message "$(MSG)" $(ARGS)

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf src/finer_dashboard/.next
