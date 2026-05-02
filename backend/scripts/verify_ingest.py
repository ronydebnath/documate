"""Smoke test the ingested Chroma collection.

Run after `make ingest`. Prints collection stats and the top-3 results for a
fixed test query about resignation notice — the top result MUST come from a
notice/termination/resignation document. If it does not, the most likely
cause is that the BGE retrieval prefix is missing on the query side.
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.services.embedder import embed_query
from ingest.chroma_store import ChromaStore

TEST_QUERY = "How much notice do I need to give when resigning?"
EXPECTED_KEYWORDS = ("notice", "resign", "termination", "ending-employment", "final-pay")


def main() -> int:
    s = get_settings()
    store = ChromaStore(s.chroma_persist_dir, s.chroma_collection)

    count = store.count()
    print(f"Collection: {s.chroma_collection!r}")
    print(f"Persist dir: {s.chroma_persist_dir}")
    print(f"Chunks: {count}")
    if count == 0:
        print("Collection is empty. Run `make ingest` first.", file=sys.stderr)
        return 1

    print()
    print(f"Test query: {TEST_QUERY!r}")
    print()

    qvec = embed_query(TEST_QUERY)
    res = store.query(qvec, top_k=3)

    ids = res["ids"][0]
    documents = res["documents"][0]
    metadatas = res["metadatas"][0]
    distances = res["distances"][0]

    for rank, (cid, doc, meta, dist) in enumerate(
        zip(ids, documents, metadatas, distances), start=1
    ):
        snippet = doc[:200].replace("\n", " ")
        print(f"#{rank}  distance={dist:.4f}  id={cid}")
        print(f"    title: {meta.get('title')}")
        print(f"    section: {meta.get('section')}")
        print(f"    snippet: {snippet}...")
        print()

    # Sanity check: top-1 should look like notice/termination content.
    top_meta = metadatas[0]
    top_slug = (top_meta.get("doc_slug") or "").lower()
    top_title = (top_meta.get("title") or "").lower()
    haystack = top_slug + " " + top_title
    if not any(kw in haystack for kw in EXPECTED_KEYWORDS):
        print(
            "WARNING: top-1 doesn't look like notice/termination content. "
            "The most common cause is a missing BGE query prefix. Check "
            "backend/app/services/embedder.py:embed_query.",
            file=sys.stderr,
        )
        return 2

    print("OK: top-1 looks like notice/termination content.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
