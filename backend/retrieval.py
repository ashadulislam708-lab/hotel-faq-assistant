"""Query embedding and vector similarity search over stored FAQ chunks."""

from config import SIMILARITY_THRESHOLD, TOP_K
from db import search_similar
from embeddings import embed_query


def retrieve_top_k(
    question: str, k: int = TOP_K, min_similarity: float = SIMILARITY_THRESHOLD
) -> list[dict]:
    """Embed the question and return the top-k FAQ chunks at or above min_similarity.

    An empty list means nothing in the store is relevant to the question.
    """
    results = search_similar(embed_query(question), k)
    return [chunk for chunk in results if chunk["similarity"] >= min_similarity]
