"""Scrape articles from a list of URLs using trafilatura.

Reads `data/articles/urls.txt` (one URL per line) and writes extracted
article text to `data/articles/scraped/<hash>.txt`.

Usage:
    python -m ingestion.scrape_urls
    python -m ingestion.scrape_urls --urls custom-urls.txt
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
from pathlib import Path

import httpx
import trafilatura

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scrape")

DEFAULT_URLS_FILE = Path("data/articles/urls.txt")
OUTPUT_DIR = Path("data/articles/scraped")


async def fetch_one(client: httpx.AsyncClient, url: str) -> tuple[str, str | None]:
    try:
        resp = await client.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        text = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
            target_language="he",
        )
        return url, text
    except Exception as e:
        logger.warning("Failed %s: %s", url, e)
        return url, None


async def scrape_all(urls_file: Path) -> None:
    if not urls_file.exists():
        logger.error("URLs file not found: %s", urls_file)
        return

    urls = [
        ln.strip()
        for ln in urls_file.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    if not urls:
        logger.info("No URLs to scrape.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; PTSD-Ai-Ingester/0.1; "
            "+https://github.com/your-org/ptsd-ai)"
        )
    }
    async with httpx.AsyncClient(headers=headers) as client:
        sem = asyncio.Semaphore(5)

        async def bounded(url: str):
            async with sem:
                return await fetch_one(client, url)

        results = await asyncio.gather(*[bounded(u) for u in urls])

    written = 0
    for url, text in results:
        if not text or len(text.strip()) < 200:
            continue
        h = hashlib.sha1(url.encode()).hexdigest()[:12]
        out = OUTPUT_DIR / f"{h}.txt"
        out.write_text(f"# Source: {url}\n\n{text}", encoding="utf-8")
        written += 1

    logger.info("Scraped %d/%d URLs successfully -> %s", written, len(urls), OUTPUT_DIR)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", type=Path, default=DEFAULT_URLS_FILE)
    args = parser.parse_args()
    asyncio.run(scrape_all(args.urls))


if __name__ == "__main__":
    main()
