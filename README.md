# Hotel FAQ Assistant

A Retrieval-Augmented Generation (RAG) system that answers natural-language questions about a hotel — check-in/check-out, amenities, policies, wifi, parking, pets, cancellations, and more — using grounded retrieval over a curated FAQ knowledge base.

## Overview

The assistant answers guest and staff questions by retrieving the most relevant entries from the hotel's FAQ content and generating a response strictly grounded in that content. If a question isn't covered by the knowledge base, the assistant says so rather than fabricating an answer.

## Features

- Natural-language Q&A over hotel FAQ content
- Answers grounded in retrieved source content — no hallucinated policies or facts
- Explicit fallback response when a question isn't covered by the knowledge base
- Chat-style web interface

## Architecture

The pipeline is implemented directly (no third-party RAG orchestration framework), with each stage explicit:

```
User question
   │
   ▼
Embed query (OpenAI)
   │
   ▼
Vector similarity search (Postgres + pgvector)
   │
   ▼
Top-k FAQ chunks  ──► Prompt assembly (context + question + instructions)
   │
   ▼
OpenAI API (generation)
   │
   ▼
Answer shown in Streamlit chat UI
```

FAQ content is chunked (one chunk per Q&A pair), embedded with the OpenAI embeddings API, and stored in PostgreSQL via the `pgvector` extension. At query time, the user's question is embedded and matched against stored chunks via vector similarity search; the top matches are assembled into a prompt and sent to the OpenAI API to generate the final answer.

See [PRD.md](PRD.md) for full product requirements, scope, and architecture details.

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python |
| Vector store | PostgreSQL + `pgvector` extension |
| Embeddings | OpenAI API |
| Generation (LLM) | OpenAI API |
| UI | Streamlit |
| DB access | psycopg2 or SQLAlchemy |

## Prerequisites

- Python 3.10+
- PostgreSQL with the `pgvector` extension installed
- An OpenAI API key

## Getting Started

```bash
# Clone the repository
git clone <repository-url>
cd RAG/backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# then edit .env with your API keys and database URL

# Enable pgvector on your Postgres database
psql -d your_database -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Populate the knowledge base
python ingest.py
```

The frontend (and how the backend is served to it) is being designed separately and isn't part of this repo yet.

## Project Structure

```
RAG/
├── backend/
│   ├── data/               # Hotel FAQ source content
│   │   └── policies/
│   ├── config.py           # Environment/config loading
│   ├── db.py                # Postgres/pgvector connection and schema
│   ├── chunking.py          # FAQ markdown loading and chunking
│   ├── embeddings.py        # OpenAI embedding calls
│   ├── ingest.py            # Chunking, embedding, and storage pipeline
│   ├── retrieval.py         # Query embedding and similarity search
│   ├── generation.py        # Prompt assembly and OpenAI API integration
│   ├── requirements.txt
│   └── .env.example
├── PRD.md
└── README.md
```

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for OpenAI (embeddings and answer generation) |
| `DATABASE_URL` | PostgreSQL connection string (pgvector-enabled database) |

## Status

In active development, following the milestones defined in [PRD.md](PRD.md).

## Documentation

Full product requirements, scope, and design decisions are documented in [PRD.md](PRD.md).
