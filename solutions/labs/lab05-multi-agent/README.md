# Lab 05 Multi-Agent Orchestration

Module 5 Lab 05 split into:
- `lab05-multi-agent/`: Render-ready FastAPI backend
- `lab05-multi-agent-frontend/`: Vercel-ready static frontend

## Backend Features

- `POST /run` and `POST /api/run` execute the orchestration workflow
- `GET /health` returns service metadata
- `GET /` returns service metadata and available endpoints
- supervisor-worker orchestration with:
  - `Researcher`
  - `Writer`
  - `Reviewer`
- shared workflow state across iterations
- activity trace showing:
  - supervisor delegation decisions
  - worker outputs
  - revision loops
  - forced completion when the iteration cap is reached
- provider abstraction with:
  - `mock` provider for local development and tests
  - `groq` provider for real model-backed orchestration

## How This Maps To Module 5 Theory

This solution is built to reflect the main Lab 05 learning goals:

- **Supervisor pattern**: one controller routes work instead of one monolithic prompt doing everything
- **Worker specialization**: each agent has a narrow responsibility
- **Structured handoffs**: research, draft, and review outputs use explicit fields
- **Iteration limits**: the system always stops and returns the best available result
- **Observability**: the API and frontend make the workflow visible instead of hiding it behind a final answer

## Workflow Shape

```text
User Task
  ->
Supervisor
  ->
Researcher
  ->
Writer
  ->
Reviewer
  ->
Supervisor Final Output
```

If the reviewer requests changes and iterations remain, the supervisor loops the draft back to the writer with a focused revision brief.

## Provider Setup

The project includes a local `.env` template plus `.env.example`.

To use Groq:

1. Open `.env`
2. Change `ORCHESTRATOR_PROVIDER=mock` to `ORCHESTRATOR_PROVIDER=groq`
3. Set `GROQ_API_KEY`

For offline development or tests:

```text
ORCHESTRATOR_PROVIDER=mock
```

## Local Run

```bash
cd solutions/labs/lab05-multi-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd solutions/labs/lab05-multi-agent-frontend
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173
```

## API Contract

### Request

```json
{
  "task": "Research the pros and cons of vector databases for a junior backend developer.",
  "max_iterations": 5
}
```

### Response Highlights

- `status`
- `provider`
- `iteration_count`
- `workers_used`
- `research_result`
- `writer_result`
- `review_result`
- `final_output`
- `activity_log`

## Testing

```bash
cd solutions/labs/lab05-multi-agent
python3 -m unittest test_main.py
```

The tests use the default `mock` provider so they do not require API keys.

## Demo Assets

- [demo/lab05-demo.gif](./demo/lab05-demo.gif)
- [demo/lab05-demo.mov](./demo/lab05-demo.mov)
