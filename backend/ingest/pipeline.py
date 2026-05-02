"""Ingestion orchestrator: load → chunk → embed → upsert.

Reads data/processed/manifest.json, processes every entry, and writes the
result to ChromaDB at the path from Settings.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import REPO_ROOT, get_settings
from app.services.embedder import embed_documents
from ingest.chroma_store import ChromaStore
from ingest.chunker import Chunk, chunk_text

log = logging.getLogger(__name__)

DATA_PROCESSED = REPO_ROOT / "data" / "processed"
MANIFEST_PATH = DATA_PROCESSED / "manifest.json"

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


@dataclass
class IngestStats:
    docs_processed: int
    chunks_created: int
    total_tokens: int
    elapsed_seconds: float


def _strip_frontmatter(md_text: str) -> str:
    """Drop the leading YAML frontmatter block. Returns the body."""
    m = _FRONTMATTER_RE.match(md_text)
    if not m:
        return md_text.lstrip()
    return md_text[m.end():].lstrip()


def _build_chunk_records(
    doc_entry: dict,
    body: str,
) -> tuple[list[str], list[str], list[dict], list[Chunk]]:
    """Chunk one doc; return (ids, documents, metadatas, chunks)."""
    chunks = chunk_text(body)
    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    slug = doc_entry["slug"]
    for i, c in enumerate(chunks):
        chunk_id = f"{slug}::{i:04d}"
        ids.append(chunk_id)
        docs.append(c.text)
        metas.append({
            "doc_slug": slug,
            "chunk_id": chunk_id,
            "source_url": doc_entry["url"],
            "title": doc_entry["title"],
            "section": doc_entry["section"],
            "char_start": c.char_start,
            "char_end": c.char_end,
            "token_count": c.token_count,
        })
    return ids, docs, metas, chunks


def run_ingest(rebuild: bool = False, limit: int | None = None) -> IngestStats:
    started = time.monotonic()
    s = get_settings()

    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest not found at {MANIFEST_PATH}. Run `make scrape` first."
        )

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if limit is not None:
        manifest = manifest[:limit]

    log.info("Manifest: %d documents", len(manifest))

    store = ChromaStore(s.chroma_persist_dir, s.chroma_collection)
    if rebuild:
        log.info("Resetting collection %r", s.chroma_collection)
        store.reset()

    all_ids: list[str] = []
    all_docs: list[str] = []
    all_metas: list[dict] = []
    total_tokens = 0
    docs_processed = 0

    for entry in manifest:
        md_path = DATA_PROCESSED / f"{entry['slug']}.md"
        if not md_path.exists():
            log.warning("Missing file for slug %s; skipping", entry["slug"])
            continue
        body = _strip_frontmatter(md_path.read_text(encoding="utf-8"))
        ids, docs, metas, chunks = _build_chunk_records(entry, body)
        if not ids:
            log.warning("No chunks produced for %s; skipping", entry["slug"])
            continue
        all_ids.extend(ids)
        all_docs.extend(docs)
        all_metas.extend(metas)
        total_tokens += sum(c.token_count for c in chunks)
        docs_processed += 1

    if not all_ids:
        log.warning("No chunks to upsert; nothing to do")
        return IngestStats(0, 0, 0, time.monotonic() - started)

    # Sanity: chunk_id uniqueness
    if len(set(all_ids)) != len(all_ids):
        dupes = {x for x in all_ids if all_ids.count(x) > 1}
        raise RuntimeError(f"Duplicate chunk_ids detected: {sorted(dupes)[:5]}")

    log.info(
        "Embedding %d chunks (%d tokens) with %s ...",
        len(all_ids), total_tokens, s.embedding_model,
    )
    embeddings = embed_documents(all_docs)

    log.info("Upserting %d chunks into %r ...", len(all_ids), s.chroma_collection)
    store.upsert(
        ids=all_ids,
        embeddings=embeddings,
        documents=all_docs,
        metadatas=all_metas,
    )

    elapsed = time.monotonic() - started
    log.info(
        "Done. docs=%d chunks=%d tokens=%d elapsed=%.1fs collection_count=%d",
        docs_processed, len(all_ids), total_tokens, elapsed, store.count(),
    )
    return IngestStats(
        docs_processed=docs_processed,
        chunks_created=len(all_ids),
        total_tokens=total_tokens,
        elapsed_seconds=elapsed,
    )
