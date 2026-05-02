.PHONY: install scrape re-extract ingest dev backend frontend eval eval-rerank test fmt lint clean

# --- Setup ---

install:
	cd backend && uv sync
	cd frontend && pnpm install

# --- Data ---

scrape:
	cd backend && uv run python -m scripts.scrape

re-extract:
	cd backend && uv run python -m scripts.extract --slug $(SLUG)

ingest:
	cd backend && uv run python -m ingest --rebuild

verify-ingest:
	cd backend && uv run python -m scripts.verify_ingest

# --- Dev (run backend and frontend in two terminals) ---

dev:
	@echo "Run 'make backend' and 'make frontend' in separate terminals."

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && pnpm dev

# --- Evals ---

eval:
	cd backend && uv run python -m evals.run_eval --config baseline

eval-rerank:
	cd backend && uv run python -m evals.run_eval --config reranked --compare-to baseline

# --- Quality ---

test:
	cd backend && uv run pytest

fmt:
	cd backend && uv run ruff format .
	cd frontend && pnpm exec prettier --write .

lint:
	cd backend && uv run ruff check .
	cd frontend && pnpm exec eslint .

# --- Clean ---

clean:
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache
	rm -rf frontend/.next frontend/.turbo
