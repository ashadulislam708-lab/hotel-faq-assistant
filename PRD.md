# PRD: Hotel FAQ Assistant (RAG)

## 1. Summary

The Hotel FAQ Assistant is a Retrieval-Augmented Generation (RAG) application that answers natural-language questions about a hotel (check-in times, amenities, policies, wifi, parking, pets, cancellations, etc.) by retrieving relevant information from a curated FAQ knowledge base and generating grounded answers with an LLM.

## 2. Problem Statement

Hotel guests and staff repeatedly ask the same small set of questions (check-out time, pet policy, wifi access, parking cost, cancellation window, etc.). A generic chatbot without grounding will either give generic answers or hallucinate hotel-specific details it doesn't actually know. This assistant answers only from the hotel's own FAQ content, and clearly indicates when a question is not covered rather than fabricating a response.

## 3. Objectives

- Answer natural-language hotel FAQ questions accurately.
- Ground every answer in the retrieved FAQ content (no hallucinated policies or facts).
- Explicitly indicate when the knowledge base does not contain an answer, rather than fabricating one.
- Provide a simple, responsive chat interface for asking questions.

## 4. Scope / Non-Goals

- No multi-hotel / multi-tenant support — a single hotel's FAQ knowledge base only.
- No user authentication or accounts.
- No booking, cancellation, or payment actions — read-only Q&A only.
- No long-term multi-turn conversation memory beyond the current chat session's visible history.
- No analytics/usage dashboard.
- No production deployment, scaling, or high-availability requirements in this release.

## 5. Target Users & Use Cases

- **Primary users:** hotel website visitors and front-desk staff seeking quick answers to common questions.
- **Use case:** a user types a question into a chat interface and receives an accurate, grounded answer sourced from the hotel's FAQ and policy documents.

## 6. User Stories

- As a guest, I want to ask "What time is check-out?" and receive the hotel's actual policy, not a generic guess.
- As a guest, I want to ask about pet policy, parking cost, or wifi and receive accurate, specific answers.
- As a guest, I want the assistant to tell me when it doesn't know an answer rather than inventing one.
- As an operator, I want visibility into which FAQ entries were used to generate an answer, to support quality review and debugging.

## 7. System Architecture / Data Flow

The system is implemented as a custom RAG pipeline (no third-party orchestration framework), with each stage explicitly controlled:

1. **Data source** — A curated set of hotel FAQ entries covering categories such as:
   - Booking & reservations
   - Check-in / check-out
   - Cancellation & refund policy
   - Amenities & facilities
   - Dining
   - Parking & transport
   - Pet policy
   - Wifi & tech support
   - Accessibility
   - Local area information

2. **Chunking** — FAQ content is split into small retrievable units (one chunk per Q&A pair), keeping each chunk focused and self-contained.

3. **Embedding** — Each chunk is embedded into a vector representation using the **OpenAI embeddings API** (`text-embedding-3-small`).

4. **Storage** — Chunk text and embedding vectors are stored in **PostgreSQL** using the **pgvector** extension.

5. **Retrieval** — The user's question is embedded (via OpenAI), and a vector similarity search (cosine similarity) is run against pgvector to fetch the top-k most relevant FAQ chunks.

6. **Augmentation** — A prompt is assembled containing the retrieved chunks as context, the user's question, and a system instruction constraining the model to answer only from the provided context and to state when the context does not cover the question.

7. **Generation** — The augmented prompt is sent to the **OpenAI API** (`gpt-4o-mini`) to produce the final answer.

8. **Interface** — A **Streamlit** chat-style web application: the user submits a question and receives an answer, with an optional view of the source FAQ chunks used to generate it.

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

## 8. Tech Stack

| Layer | Choice |
|---|---|
| Language | Python |
| Vector store | PostgreSQL + `pgvector` extension |
| Embeddings | OpenAI API |
| Generation (LLM) | OpenAI API |
| UI | Streamlit |
| DB access | psycopg2 or SQLAlchemy |

## 9. Functional Requirements

- An ingestion pipeline that loads FAQ source content, chunks it, generates embeddings, and stores chunks and embeddings in pgvector.
- A query pipeline: embed the user's question → retrieve top-k chunks → assemble augmented prompt → call OpenAI → return the answer.
- A Streamlit chat interface for submitting questions and viewing answers.
- A defined fallback response when no retrieved chunk is sufficiently relevant to the question.
- Support for re-running ingestion after FAQ content is added or updated.

## 10. Non-Functional Requirements

- **Maintainability** — code should be clear, modular, and easy to extend.
- **Latency** — end-to-end response time of a few seconds is acceptable.
- **Cost efficiency** — minimal embedding and generation calls for the given dataset size.
- **Deployment** — runs against a local PostgreSQL instance; no external infrastructure required for this release.

## 11. Success Metrics / Acceptance Criteria

- The assistant produces correct, grounded answers across a validation set of 15–20 sample questions spanning all FAQ categories.
- The assistant correctly declines to answer (rather than hallucinating) for questions outside the scope of the FAQ content.
- Retrieved source chunks are available for review to support quality validation.

## 12. Roadmap / Milestones

1. **Milestone 1 — Knowledge base preparation:** Author the hotel FAQ content set.
2. **Milestone 2 — Data layer:** Set up PostgreSQL with pgvector; define the chunk/embedding schema.
3. **Milestone 3 — Ingestion pipeline:** Implement chunking, embedding, and storage.
4. **Milestone 4 — Retrieval pipeline:** Implement query embedding and similarity search.
5. **Milestone 5 — Generation pipeline:** Implement prompt assembly and OpenAI API integration.
6. **Milestone 6 — User interface:** Build the Streamlit application and integrate the full pipeline.
7. **Milestone 7 — Validation:** Test against the sample question set and refine chunking/prompting to improve accuracy and reduce hallucination.

## 13. Risks

- **Hallucination risk** if retrieval misses the relevant chunk or the system prompt does not sufficiently constrain the model.
- **Chunking strategy** materially affects retrieval quality and may require iteration.
- **Secrets management** for the OpenAI API key must be handled securely (e.g., environment variables, excluded from version control).
- Embedding cost and rate limits are a minor concern at the target dataset size.

## 14. Future Enhancements (out of scope for this release)

- Multi-turn conversational memory across sessions.
- Source citation UI surfaced to end users.
- Administrative interface for managing FAQ content.
- Multi-hotel / multi-tenant support.
- Automated RAG evaluation framework (e.g., RAGAS-style metrics).
- Cloud deployment.
