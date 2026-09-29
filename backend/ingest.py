"""Ingestion pipeline: load FAQ content, chunk it, embed it, and store it in pgvector."""

import argparse
import logging
import sys
import time

from chunking import chunk_faq_content, load_faq_files
from config import require_config
from db import init_schema, replace_all_chunks
from embeddings import embed_documents

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load, chunk, and embed content without writing to the database.",
    )
    return parser.parse_args()


def main():
    """Run the full ingestion pipeline end to end."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    start = time.monotonic()

    if args.dry_run:
        require_config("OPENAI_API_KEY")
    else:
        require_config("OPENAI_API_KEY", "DATABASE_URL")

    documents = load_faq_files()
    logger.info("Loaded %d FAQ file(s)", len(documents))

    chunks = [chunk for doc in documents for chunk in chunk_faq_content(doc)]
    logger.info("Produced %d chunk(s)", len(chunks))

    embeddings = embed_documents([chunk["text"] for chunk in chunks])
    logger.info("Generated %d embedding(s)", len(embeddings))

    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding

    if args.dry_run:
        logger.info("Dry run: skipping database write")
    else:
        init_schema()
        replace_all_chunks(chunks)
        logger.info("Stored %d chunk(s) in faq_chunks", len(chunks))

    logger.info("Ingestion complete in %.1fs", time.monotonic() - start)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.getLogger(__name__).exception("Ingestion failed")
        sys.exit(1)
