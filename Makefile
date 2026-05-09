.PHONY: install scrape re-extract ingest dev backend frontend eval eval-rerank test fmt lint clean deploy-api deploy-web deploy

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

# --- Deploy ---

# Backend deploys to Fly.io. Builds infra/Dockerfile from the repo root so
# data/chroma/ is in the build context. Requires a working `fly` CLI auth.
deploy-api:
	fly deploy --config infra/fly.toml --dockerfile infra/Dockerfile

# Frontend deploys to Vercel. Requires a working `vercel` CLI auth and
# the project linked to frontend/.
deploy-web:
	cd frontend && vercel --prod

deploy: deploy-api deploy-web

# --- Clean ---

clean:
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache
	rm -rf frontend/.next frontend/.turbo
