"""CLI entry: `cd backend && uv run python -m ingest`.

Args:
    --rebuild       Drop and recreate the Chroma collection before ingesting.
    --limit N       Only process the first N manifest entries (debugging).
    --verbose       DEBUG-level logs.
"""

from __future__ import annotations

import argparse
import logging
import sys

from ingest.pipeline import run_ingest


def main() -> int:
    parser = argparse.ArgumentParser(description="DocuMate ingestion pipeline")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Reset the Chroma collection before ingesting",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only ingest the first N documents from the manifest",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    stats = run_ingest(rebuild=args.rebuild, limit=args.limit)

    print()
    print("=" * 60)
    print("INGEST SUMMARY")
    print(f"  Documents processed:  {stats.docs_processed}")
    print(f"  Chunks created:       {stats.chunks_created}")
    print(f"  Total tokens:         {stats.total_tokens:,}")
    print(f"  Elapsed:              {stats.elapsed_seconds:.1f}s")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
