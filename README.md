# AI Agentic Training Solutions

This repository now contains my course work, working solutions, and companion notes.

## Included So Far

### Student Notes

- [student-notes/module-1-fast-track.md](./student-notes/module-1-fast-track.md)
- [student-notes/lab02-code-analyzer-fast-track.md](./student-notes/lab02-code-analyzer-fast-track.md)
- [student-notes/lab03-migration-workflow-fast-track.md](./student-notes/lab03-migration-workflow-fast-track.md)
- [student-notes/lab04-rag-system-fast-track.md](./student-notes/lab04-rag-system-fast-track.md)
- [student-notes/lab05-multi-agent-fast-track.md](./student-notes/lab05-multi-agent-fast-track.md)

### Module 1 Exercise

- [solutions/labs/module1-exercise-model-comparison](./solutions/labs/module1-exercise-model-comparison)

What is included:
- model comparison runner
- generated report output
- offline draft mode for cases where API access is unavailable

### Lab 01: Vibe Coding Introduction

- [solutions/labs/lab01-url-shortener](./solutions/labs/lab01-url-shortener)
- [solutions/labs/lab01-url-shortener-frontend](./solutions/labs/lab01-url-shortener-frontend)

What is included:
- Railway-ready backend
- Vercel-ready frontend
- SQLite storage
- unit tests
- demo recording

### Lab 02: Code Analyzer Agent

- [solutions/labs/lab02-code-analyzer](./solutions/labs/lab02-code-analyzer)
- [solutions/labs/lab02-code-analyzer-frontend](./solutions/labs/lab02-code-analyzer-frontend)

What is included:
- Render-ready FastAPI backend scaffold
- Vercel-ready frontend scaffold
- prompt-driven analysis flow
- mock analyzer plus Groq provider support
- student fast-track notes
- demo recording

### Lab 03: Migration Workflow Agent

- [solutions/labs/lab03-migration-workflow](./solutions/labs/lab03-migration-workflow)
- [solutions/labs/lab03-migration-workflow-frontend](./solutions/labs/lab03-migration-workflow-frontend)

What is included:
- Render-ready FastAPI backend scaffold
- Vercel-ready frontend scaffold
- four-phase migration workflow
- mock migration plus Groq/OpenAI/Gemini provider support
- student fast-track notes
- demo recording

### Lab 04: RAG System With Evaluation

- [solutions/labs/lab04-rag-system](./solutions/labs/lab04-rag-system)
- [solutions/labs/lab04-rag-system-frontend](./solutions/labs/lab04-rag-system-frontend)

What is included:
- Render-ready FastAPI backend scaffold
- Vercel-ready frontend scaffold
- code-aware chunking and grounded query flow
- retrieval metrics plus LLM-as-judge style evaluation
- bundled evaluation dataset and dataset guide
- Render/Vercel deployment-ready setup
- student fast-track notes
- demo recording

### Lab 05: Multi-Agent Orchestration

- [solutions/labs/lab05-multi-agent](./solutions/labs/lab05-multi-agent)
- [solutions/labs/lab05-multi-agent-frontend](./solutions/labs/lab05-multi-agent-frontend)

What is included:
- Render-ready FastAPI backend scaffold
- Vercel-ready frontend scaffold
- supervisor plus `Researcher`, `Writer`, and `Reviewer` workers
- shared workflow state and visible activity trace
- Groq-ready env setup plus mock mode for local testing
- student fast-track notes
- demo recording

### Final Project: AI Code Review Bot

- [solutions/labs/final-project](./solutions/labs/final-project)
- [solutions/labs/final-project-frontend](./solutions/labs/final-project-frontend)

What is included:
- Render-ready FastAPI backend scaffold
- Vercel-ready frontend scaffold
- retrieval-backed review guidance plus evaluation dataset
- Lab 05-style workflow trace with `retriever`, `reviewer`, and `validator`
- mock mode for offline testing plus OpenAI/Groq-ready provider setup
- demo recording

## Lab 01 Quick Start

```bash
cd solutions/labs/lab01-url-shortener
python3 app.py
```

Then open the frontend:

```text
/Users/vlezcano/Documents/ai-agentic-training/solutions/labs/lab01-url-shortener-frontend/index.html
```

Run tests:

```bash
cd solutions/labs/lab01-url-shortener
python3 -m unittest test_app.py
```

Lab 01 demo assets:
- [solutions/labs/lab01-url-shortener/demo/lab01-demo.gif](./solutions/labs/lab01-url-shortener/demo/lab01-demo.gif)
- [solutions/labs/lab01-url-shortener/demo/lab01-demo.mov](./solutions/labs/lab01-url-shortener/demo/lab01-demo.mov)

## Lab 02 Quick Start

Backend:

```bash
cd solutions/labs/lab02-code-analyzer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd solutions/labs/lab02-code-analyzer-frontend
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173
```

Lab 02 notes and setup:
- [student-notes/lab02-code-analyzer-fast-track.md](./student-notes/lab02-code-analyzer-fast-track.md)
- [solutions/labs/lab02-code-analyzer/README.md](./solutions/labs/lab02-code-analyzer/README.md)

Lab 02 demo assets:
- [solutions/labs/lab02-code-analyzer/demo/lab02-demo.gif](./solutions/labs/lab02-code-analyzer/demo/lab02-demo.gif)
- [solutions/labs/lab02-code-analyzer/demo/lab02-demo.mov](./solutions/labs/lab02-code-analyzer/demo/lab02-demo.mov)

## Lab 03 Quick Start

Backend:

```bash
cd solutions/labs/lab03-migration-workflow
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd solutions/labs/lab03-migration-workflow-frontend
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173
```

Lab 03 notes and setup:
- [student-notes/lab03-migration-workflow-fast-track.md](./student-notes/lab03-migration-workflow-fast-track.md)
- [solutions/labs/lab03-migration-workflow/README.md](./solutions/labs/lab03-migration-workflow/README.md)

Lab 03 demo assets:
- [solutions/labs/lab03-migration-workflow/demo/lab03-demo.gif](./solutions/labs/lab03-migration-workflow/demo/lab03-demo.gif)
- [solutions/labs/lab03-migration-workflow/demo/lab03-demo.mov](./solutions/labs/lab03-migration-workflow/demo/lab03-demo.mov)

## Lab 04 Quick Start

Backend:

```bash
cd solutions/labs/lab04-rag-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd solutions/labs/lab04-rag-system-frontend
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173
```

Lab 04 notes and setup:
- [student-notes/lab04-rag-system-fast-track.md](./student-notes/lab04-rag-system-fast-track.md)
- [solutions/labs/lab04-rag-system/README.md](./solutions/labs/lab04-rag-system/README.md)

Lab 04 demo assets:
- [solutions/labs/lab04-rag-system/demo/lab04-demo.gif](./solutions/labs/lab04-rag-system/demo/lab04-demo.gif)
- [solutions/labs/lab04-rag-system/demo/lab04-demo.mov](./solutions/labs/lab04-rag-system/demo/lab04-demo.mov)

## Lab 05 Quick Start

Backend:

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

Lab 05 notes and setup:
- [student-notes/lab05-multi-agent-fast-track.md](./student-notes/lab05-multi-agent-fast-track.md)
- [solutions/labs/lab05-multi-agent/README.md](./solutions/labs/lab05-multi-agent/README.md)

Lab 05 demo assets:
- [solutions/labs/lab05-multi-agent/demo/lab05-demo.gif](./solutions/labs/lab05-multi-agent/demo/lab05-demo.gif)
- [solutions/labs/lab05-multi-agent/demo/lab05-demo.mov](./solutions/labs/lab05-multi-agent/demo/lab05-demo.mov)

## Final Project Quick Start

Backend:

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

Final project notes and setup:
- [solutions/labs/final-project/README.md](./solutions/labs/final-project/README.md)

Final project demo assets:
- [solutions/labs/final-project/demo/final-project-demo.mov](./solutions/labs/final-project/demo/final-project-demo.mov)

## Repository Structure

```text
.
├── README.md
├── solutions/
│   └── labs/
└── student-notes/
```

## Current Progress

- Module 1 fast-track notes: done
- Module 1 model comparison exercise: done
- Lab 01 URL shortener: done
- Lab 02 code analyzer scaffold: done
- Lab 03 migration workflow agent: done
- Lab 04 RAG system with evaluation: done
- Lab 05 multi-agent orchestration: done
- Final project code review bot: done
