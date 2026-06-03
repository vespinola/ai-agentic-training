# Lab 04 RAG System with Evaluation

Module 4 Lab 04 split into:
- `lab04-rag-system/`: Render-ready FastAPI backend
- `lab04-rag-system-frontend/`: Vercel-ready static frontend

## Backend Features

- `POST /index/files` and `POST /api/index/files` index uploaded code files
- `POST /query` and `POST /api/query` answer questions about indexed code
- `POST /evaluate` and `POST /api/evaluate` run retrieval and generation evaluation
- `GET /health` returns service metadata
- `GET /` returns service metadata and available endpoints
- code-aware chunking:
  - AST-based chunking for Python functions and classes
  - regex and fixed-block fallback for other languages
- persistent local vector store using `rag_index.json`
- evaluation framework implementing:
  - `Precision@K`
  - `Recall@K`
  - `MRR`
  - `LLM-as-judge` style scoring for relevance, faithfulness, and correctness
- bundled sample codebase plus `10` evaluation examples
- provider abstraction with:
  - mock answer and judge path for local development
  - optional OpenAI, Gemini, or Groq answer and judge providers
  - optional OpenAI embeddings provider

## How This Maps To Module 4 Theory

This solution is built to reflect the main theory requirements:

- **RAG pipeline**: files are chunked, embedded, stored, retrieved, and then used to answer
- **Chunking**: Python uses logical code units instead of whole-file embeddings
- **Grounding**: query responses return source snippets and metadata
- **Evaluation**: retrieval metrics and judge scores are part of the product, not an afterthought
- **Debuggability**: the frontend shows retrieved snippets and the evaluation endpoint returns per-example results

## Theory Walkthrough In This Project

If you are learning, the easiest way to understand this lab is to map each theory concept to one concrete part of the code.

### 1. RAG pipeline

Theory says:

- documents are chunked
- chunks are embedded
- embeddings are stored
- a question is embedded
- similar chunks are retrieved
- the model answers using retrieved context

In this project:

- indexing starts in `RAGService.index_files()`
- chunking happens in `chunk_source_file()`
- embeddings are created by `EmbeddingBackend`
- indexed chunks are stored in `VectorStore`
- query retrieval happens in `RAGService._rank_sources()`
- final answer generation happens in `RAGClient.answer_question()`

That means the theory is not abstract here. It is implemented as a visible flow in the backend.

### 2. Chunking strategy

Theory says bad chunking is one of the biggest reasons RAG fails.

In this project:

- Python files are parsed with the AST in `chunk_python_file()`
- functions and classes become separate chunks
- module-level code is also preserved as its own chunk
- non-Python files use a lighter structure-aware fallback in `chunk_generic_file()`

Why this matters:

- embedding an entire file would mix too many topics together
- chunking by function/class makes retrieval more precise
- the line numbers and symbol names make sources easier to inspect in the UI

This is the project’s version of “smart code-aware chunking.”

### 3. Embeddings

Theory says embeddings turn text into vectors so semantically related items can be compared.

In this project:

- `HashEmbeddingBackend` is the local mock embedding path
- `OpenAIEmbeddingBackend` is the real API embedding path
- both return vectors that are later compared with cosine similarity

Important learning note:

- the mock embedding is not a real semantic model
- it exists so you can run the whole lab locally without paying for an API
- the architecture is still the same as a real RAG system

So conceptually, the project is teaching the right pipeline even when the local provider is simplified.

### 4. Retrieval

Theory says retrieval quality should be measured separately from generation quality.

In this project:

- retrieval ranking is handled in `RAGService._rank_sources()`
- the current ranking combines:
  - vector similarity
  - keyword overlap
  - symbol-name overlap

That is useful for learning because it shows an important real-world idea:

- pure vector search is often not enough for code
- exact names like `create_token` or `hash_password` matter a lot
- mixing semantic and keyword-like signals is a small hybrid-search pattern

### 5. Grounded generation

Theory says the answer should come from retrieved context, not from guessing.

In this project:

- retrieved snippets are formatted in `build_answer_prompt()`
- the prompt explicitly tells the model to answer only from provided context
- the API returns the answer plus the exact retrieved source snippets

Why this is important:

- users can inspect where the answer came from
- you can debug whether the issue is retrieval or generation
- it reduces the “black box” feeling that many RAG demos have

### 6. Metadata

Theory often treats metadata as a detail, but in practice it is part of why RAG systems are usable.

In this project every chunk stores:

- file path
- language
- chunk type
- symbol name
- line range
- chunk index

This metadata helps with:

- source display in the frontend
- stable chunk IDs for evaluation
- debugging wrong retrieval results

### 7. Evaluation dataset

Theory says you need a test set with known expected behavior.

In this project:

- `evaluation_dataset.json` contains 10 examples
- each example has:
  - a question
  - an expected answer
  - relevant chunk IDs

Why that matters:

- the expected answer supports answer-quality evaluation
- the relevant chunk IDs support retrieval evaluation
- this makes the system measurable instead of just “seems okay”

### 8. Retrieval metrics

Theory requires:

- `Precision@K`
- `Recall@K`
- `MRR`

In this project these are computed in:

- `precision_at_k()`
- `recall_at_k()`
- `mean_reciprocal_rank()`

How to read them:

- `Precision@K`: how many of the top results were actually relevant
- `Recall@K`: how many of the relevant chunks were successfully retrieved
- `MRR`: how early the first relevant result appeared

Why separate metrics help:

- good recall but weak precision means retrieval is noisy
- good precision but low recall means you are missing relevant chunks
- low MRR means the right answer may exist but it is buried too low

### 9. LLM-as-judge

Theory says answer quality should also be evaluated, not just retrieval.

In this project:

- `build_judge_prompt()` creates the evaluation prompt
- `RAGClient.judge_answer()` scores:
  - relevance
  - faithfulness
  - correctness

With `mock`, the scoring is heuristic.
With a real provider, the scoring comes from another model call.

This reflects the theory directly:

- relevance asks whether the answer addressed the question
- faithfulness asks whether it stayed grounded in retrieved code
- correctness asks whether it matched the expected answer

### 10. Observability and debugging

Theory says a RAG system should be inspectable.

In this project the frontend exposes:

- indexed file flow
- retrieved chunks
- answer output
- aggregate evaluation metrics
- per-example evaluation results

That means when something goes wrong, you can ask:

1. was the right chunk retrieved?
2. was the answer in that chunk?
3. did the answer generation stay faithful?

That debugging order is one of the most important habits from lab04.

## Local Development

### 1. Run the backend

```bash
cd solutions/labs/lab04-rag-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The backend will run on:

```text
http://127.0.0.1:8000
```

Optional environment variables:

```text
RAG_PROVIDER=mock
EMBEDDING_PROVIDER=mock

OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-2.5-flash

GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.1-8b-instant

CORS_ALLOW_ORIGINS=http://127.0.0.1:4173,https://your-frontend.vercel.app
```

Provider notes:

- `RAG_PROVIDER=mock` uses the built-in grounded answer and heuristic judge flow
- `RAG_PROVIDER=openai` uses OpenAI chat completions for answer generation and judge scoring
- `RAG_PROVIDER=gemini` uses Gemini for answer generation and judge scoring
- `RAG_PROVIDER=groq` uses the OpenAI-compatible Groq API for answer generation and judge scoring
- `EMBEDDING_PROVIDER=mock` uses deterministic local hashed embeddings for local development
- `EMBEDDING_PROVIDER=openai` uses OpenAI embeddings

### Local `.env` option

You can keep secrets out of your shell history by creating a local file at:

```text
solutions/labs/lab04-rag-system/.env
```

Example:

```text
RAG_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CORS_ALLOW_ORIGINS=http://127.0.0.1:4173
```

### 2. Point the frontend at the backend

Edit:

- [../lab04-rag-system-frontend/config.js](../lab04-rag-system-frontend/config.js)

Use:

```js
window.APP_CONFIG = {
  API_BASE_URL: "http://127.0.0.1:8000"
};
```

### 3. Open the frontend

Open this file in your browser:

- [../lab04-rag-system-frontend/index.html](../lab04-rag-system-frontend/index.html)

If your browser blocks local file fetches, use a tiny local static server instead:

```bash
cd solutions/labs/lab04-rag-system-frontend
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173
```

## Sample Files and Dataset

Bundled sample codebase:

- [sample_codebase/auth.py](./sample_codebase/auth.py)
- [sample_codebase/users.py](./sample_codebase/users.py)
- [sample_codebase/app.py](./sample_codebase/app.py)

Bundled evaluation dataset:

- [evaluation_dataset.json](./evaluation_dataset.json)

The frontend can load a matching sample flow automatically, which is the fastest way to demo:

1. load sample files
2. index them
3. ask a question
4. run evaluation

## Tests

If you already have the dependencies installed in a virtualenv:

```bash
cd solutions/labs/lab04-rag-system
python3 -m unittest test_main.py
```

## Render Deployment

### Render backend settings

- Repository: this repo
- Root directory:

```text
solutions/labs/lab04-rag-system
```

- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Vercel Deployment

### Vercel frontend settings

- Import the same GitHub repo into Vercel
- Framework preset: `Other`
- Root directory:

```text
solutions/labs/lab04-rag-system-frontend
```

### Before deploying frontend

Update:

- [../lab04-rag-system-frontend/config.js](../lab04-rag-system-frontend/config.js)

Set:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://your-backend.onrender.com"
};
```

Then redeploy the frontend on Vercel.

## Example Requests

### Index files

```bash
curl -X POST http://127.0.0.1:8000/api/index/files \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "path": "auth.py",
        "content": "def create_token(user_id):\n    return f\"token:{user_id}\"\n"
      }
    ]
  }'
```

### Query

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which function creates auth tokens?",
    "top_k": 4
  }'
```

### Evaluate

```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "top_k": 4
  }'
```

## Deliverables Coverage

This solution covers the lab04 deliverables with:

- working RAG system with code indexing
- smart code-aware chunking for Python plus fallback strategies for other languages
- evaluation framework with retrieval metrics
- `LLM-as-judge` style generation evaluation
- bundled evaluation dataset with `10` examples
- web frontend for indexing, querying, and metrics
- deployment-ready backend and frontend folders
