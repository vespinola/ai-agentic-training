# AI Agentic Training Solutions

This repository now contains my course work, working solutions, and companion notes.

## Included So Far

### Student Notes

- [student-notes/module-1-fast-track.md](./student-notes/module-1-fast-track.md)
- [student-notes/lab02-code-analyzer-fast-track.md](./student-notes/lab02-code-analyzer-fast-track.md)

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
- mock analyzer plus OpenAI-compatible provider hook
- student fast-track notes

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
