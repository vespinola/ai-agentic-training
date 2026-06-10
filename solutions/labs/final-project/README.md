# Final Project: AI Code Review Bot

Final project solution for `Option A` built in the same split-lab style as the rest of this repository:

- `final-project/`: Render-ready FastAPI backend
- `final-project-frontend/`: Vercel-ready static frontend

## What This Project Demonstrates

This implementation is intentionally built as a course recap:

- **Lab 01**: full-stack product shape with a clean backend/frontend split
- **Lab 02**: structured code review output and provider abstraction
- **Lab 03**: explicit workflow phases and validation pass
- **Lab 04**: retrieved review guidance plus bundled evaluation dataset
- **Lab 05**: activity trace and worker-style orchestration

## Backend Features

- `POST /review` and `POST /api/review`
- `POST /evaluate` and `POST /api/evaluate`
- `GET /health` and `GET /`
- structured review response with:
  - `summary`
  - `issues`
  - `suggestions`
  - `metrics`
- retrieval-backed guidance using `review_knowledge_base.json`
- workflow trace with:
  - `supervisor`
  - `retriever`
  - `reviewer`
  - `validator`
- in-memory rate limiting
- provider abstraction with:
  - `mock` for offline work and tests
  - `openai`
  - `groq`

## Workflow Shape

```text
Review Request
  ->
Supervisor Intake
  ->
Guidance Retrieval
  ->
Structured Review Draft
  ->
Validation Pass
  ->
Final Review Response
```

## Local Run

```bash
cd solutions/labs/final-project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd solutions/labs/final-project-frontend
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173
```

## Provider Setup

Copy `.env.example` to `.env` if you want to switch away from mock mode.

For offline work or tests:

```text
FINAL_PROJECT_PROVIDER=mock
```

For OpenAI:

```text
FINAL_PROJECT_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

For Groq:

```text
FINAL_PROJECT_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
```

## Testing

```bash
cd solutions/labs/final-project
python3 -m unittest test_main.py
```

The tests use the default `mock` provider, so no API key is required.

## Suggested Demo Flow

1. Run a `deep` review on the sample snippet
2. Show the retrieved guidance hits
3. Walk through the activity trace
4. Highlight the structured issues and metrics
5. Run `/api/evaluate` to show the bundled evaluation summary
