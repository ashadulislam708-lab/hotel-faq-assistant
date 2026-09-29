"""Load hotel FAQ markdown source content and split it into retrievable chunks."""

import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "policies"


def load_faq_files(dir_path: Path = DATA_DIR) -> list[str]:
    """Read all FAQ markdown files from dir_path and return their raw text contents."""
    paths = sorted(dir_path.glob("*.md"))
    return [path.read_text(encoding="utf-8") for path in paths]


def chunk_faq_content(text: str) -> list[dict]:
    """Split a single FAQ markdown document into one chunk per Q&A pair."""
    lines = text.splitlines()
    category = lines[0].lstrip("#").strip() if lines and lines[0].startswith("# ") else ""
    body = "\n".join(lines[1:])

    sections = re.split(r"(?m)^## +", body)
    chunks = []
    for section in sections[1:]:
        question, _, answer = section.partition("\n")
        question = question.strip()
        answer = answer.strip()
        chunks.append(
            {
                "text": f"Q: {question}\nA: {answer}",
                "question": question,
                "answer": answer,
                "category": category,
            }
        )
    return chunks
