"""CLI for asking the Hotel FAQ Assistant a single question."""

import argparse

from config import require_config
from rag import answer_question


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="The question to ask.")
    args = parser.parse_args()

    require_config("OPENAI_API_KEY", "DATABASE_URL")
    result = answer_question(args.question)

    print(result["answer"])
    if result["sources"]:
        print("\nSources:")
        for source in result["sources"]:
            print(f"  [{source['similarity']:.2f}] {source['category']} — {source['question']}")


if __name__ == "__main__":
    main()
