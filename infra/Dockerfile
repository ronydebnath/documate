# DocuMate backend image. Multi-stage so the final layer doesn't ship uv
# or build deps. BGE weights are pre-downloaded at build time so the first
# request after Fly cold-start doesn't pay a 130MB download penalty.

# ---------- builder ----------
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.8 /uv /usr/local/bin/uv

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock backend/.python-version /app/backend/
COPY backend/app /app/backend/app
COPY backend/ingest /app/backend/ingest

WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-install-project

# Pre-download embedder + reranker weights into the venv's HF cache. Fly
# cold-starts then load from local disk instead of the network.
ENV HF_HOME=/app/backend/.hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/app/backend/.hf-cache
RUN mkdir -p $HF_HOME \
    && uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')" \
    && uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"

# ---------- runtime ----------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/backend/.hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/app/backend/.hf-cache \
    PATH=/app/backend/.venv/bin:$PATH \
    CHROMA_PERSIST_DIR=/data/chroma

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=builder --chown=app:app /app/backend/.venv /app/backend/.venv
COPY --from=builder --chown=app:app /app/backend/.hf-cache /app/backend/.hf-cache
COPY --chown=app:app backend/app /app/backend/app
COPY --chown=app:app backend/ingest /app/backend/ingest

# Bake the Chroma store into the image so the runtime is self-contained.
# Re-running ingest is a rebuild + redeploy.
COPY --chown=app:app data/chroma /data/chroma

RUN chown -R app:app /app/backend

USER app
WORKDIR /app/backend

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).getcode()==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
