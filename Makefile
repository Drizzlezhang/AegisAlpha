.PHONY: sync lint typecheck test check clean

sync:
	cd backend && uv sync

lint:
	cd backend && ruff check .

format:
	cd backend && ruff format .

typecheck:
	cd backend && mypy backend/aegis

test:
	cd backend && pytest tests/ -v

test-foundation:
	cd backend && pytest tests/foundation/ -v

check: lint typecheck test-foundation

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
