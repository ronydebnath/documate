"""HTML to markdown extraction via trafilatura.

Importable function `extract_to_markdown(html, url)` is used by scrape.py.
Runs standalone for re-extracting a previously-fetched page from data/raw/
without re-hitting the network:
    cd backend && uv run python -m scripts.extract --slug leave-parental-leave
"""

from __future__ import annotations

import argparse
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup


def extract_to_markdown(html: bytes, url: str) -> tuple[str, str, int] | None:
    """Extract main content as markdown plus a title.

    Returns (title, markdown_body, char_count) or None if extraction yields nothing.
    """
    try:
        markdown = trafilatura.extract(
            html,
            url=url or None,
            output_format="markdown",
            include_tables=True,
            include_links=False,
            include_comments=False,
            include_formatting=True,
            favor_recall=True,
        )
    except Exception:
        return None

    if not markdown:
        return None

    title = ""
    try:
        meta = trafilatura.extract_metadata(html, default_url=url or None)
        if meta is not None and getattr(meta, "title", None):
            title = (meta.title or "").strip()
    except Exception:
        pass

    if not title:
        soup = BeautifulSoup(html, "lxml")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

    body = markdown.strip()
    return title, body, len(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-extract a single page from data/raw/")
    parser.add_argument("--slug", required=True, help="Slug of an existing data/raw/{slug}.html")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    raw_path = repo_root / "data" / "raw" / f"{args.slug}.html"
    if not raw_path.exists():
        print(f"Not found: {raw_path}")
        return 1

    html = raw_path.read_bytes()
    result = extract_to_markdown(html, "")
    if result is None:
        print("Extraction returned no content.")
        return 1

    title, body, chars = result
    print(f"Title: {title}")
    print(f"Chars: {chars}")
    print()
    print(body[:600] + ("..." if chars > 600 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
