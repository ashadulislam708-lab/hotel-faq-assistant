"""OpenAI embedding calls for FAQ chunks and user queries."""

import logging
import time

import openai

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

MODEL = "text-embedding-3-small"
BATCH_SIZE = 128
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

_client = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _embed_with_retry(texts: list[str]) -> list[list[float]]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _get_client().embeddings.create(input=texts, model=MODEL)
            return [item.embedding for item in result.data]
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            delay = RETRY_BACKOFF_SECONDS * attempt
            logger.warning(
                "OpenAI embed call failed (attempt %d/%d), retrying in %ds",
                attempt,
                MAX_RETRIES,
                delay,
            )
            time.sleep(delay)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of FAQ chunk texts for storage."""
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        embeddings.extend(_embed_with_retry(batch))
    return embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single user question for retrieval."""
    return _embed_with_retry([text])[0]
