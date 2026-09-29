"""Prompt assembly and OpenAI API integration for grounded answer generation."""

import openai

from config import OPENAI_API_KEY

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are a hotel FAQ assistant. Answer the user's question using only the "
    "provided FAQ context. If the context does not contain the answer, say that "
    "you don't have information on that topic rather than guessing or inventing "
    "an answer."
)

_client = None


def _get_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=OPENAI_API_KEY)
    return _client


def build_prompt(question: str, chunks: list[dict]) -> str:
    """Assemble a prompt from retrieved FAQ chunks and the question."""
    context = "\n\n".join(chunk["text"] for chunk in chunks)
    return f"Context:\n{context}\n\nQuestion: {question}"


def generate_answer(question: str, chunks: list[dict]) -> str:
    """Call the OpenAI API with the assembled prompt and return the generated answer."""
    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(question, chunks)},
        ],
    )
    return response.choices[0].message.content
