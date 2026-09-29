"""Query embedding and vector similarity search over stored FAQ chunks."""

from db import search_similar
from embeddings import embed_query


def retrieve_top_k(question: str, k: int = 5) -> list[dict]:
    """Embed the question and return the top-k most relevant FAQ chunks."""
    raise NotImplementedError
