"""End-to-end query pipeline: retrieve similar FAQ chunks, then generate a grounded answer."""

from generation import generate_answer
from retrieval import retrieve_top_k

FALLBACK_MESSAGE = (
    "I'm sorry, I don't have information on that topic. "
    "Please contact the hotel front desk for help."
)


def answer_question(question: str) -> dict:
    """Answer a question from the FAQ store.

    Returns {'answer': str, 'sources': list[dict]}. If no stored chunk is similar
    enough to the question, returns the fallback message without calling the LLM.
    """
    question = question.strip()
    if not question:
        return {"answer": FALLBACK_MESSAGE, "sources": []}

    chunks = retrieve_top_k(question)
    if not chunks:
        return {"answer": FALLBACK_MESSAGE, "sources": []}

    return {"answer": generate_answer(question, chunks), "sources": chunks}
