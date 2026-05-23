# Lab 02 Code Analyzer

Module 2 Lab 02 split into:
- `lab02-code-analyzer/`: Render-ready FastAPI backend
- `lab02-code-analyzer-frontend/`: Vercel-ready static frontend

## Backend Features

- `POST /api/analyze` accepts `{"code": "...", "language": "python", "analysis_type": "general"}`
- `GET /health` returns a health response
- `GET /` returns service metadata
- Pydantic request and response validation
- analyzer client abstraction with:
  - mock analysis for local development
  - Groq support through the OpenAI-compatible API
- prompt builder for general, security, and performance analysis

## Local Development

### 1. Run the backend

```bash
cd solutions/labs/lab02-code-analyzer
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
ANALYZER_PROVIDER=mock
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.1-8b-instant
CORS_ALLOW_ORIGINS=http://127.0.0.1:4173,https://your-frontend.vercel.app
```

Provider notes:
- `ANALYZER_PROVIDER=mock` uses the built-in heuristic analyzer
- `ANALYZER_PROVIDER=groq` uses `GROQ_API_KEY`
- Groq follows the course pattern: API root `https://api.groq.com/openai/v1`, then the app calls `/chat/completions`

### Local `.env` option

You can keep secrets out of your shell history by creating a local file at:

```text
solutions/labs/lab02-code-analyzer/.env
```

Example:

```text
ANALYZER_PROVIDER=groq
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.1-8b-instant
CORS_ALLOW_ORIGINS=http://127.0.0.1:4173
```

Notes:
- this project auto-loads `lab02-code-analyzer/.env` at startup
- `.env` is ignored by `solutions/labs/lab02-code-analyzer/.gitignore`
- committed examples should stay in `.env.example`
- to switch providers locally, change `ANALYZER_PROVIDER` and the matching API key env var

### 2. Point the frontend at the backend

Edit:

- [../lab02-code-analyzer-frontend/config.js](../lab02-code-analyzer-frontend/config.js)

Use:

```js
window.APP_CONFIG = {
  API_BASE_URL: "http://127.0.0.1:8000"
};
```

### 3. Open the frontend

Open this file in your browser:

- [../lab02-code-analyzer-frontend/index.html](../lab02-code-analyzer-frontend/index.html)

If your browser blocks local file fetches, use a tiny local static server instead:

```bash
cd solutions/labs/lab02-code-analyzer-frontend
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173
```

## Tests

```bash
cd solutions/labs/lab02-code-analyzer
python3 -m unittest test_main.py
```

## Render Deployment

### Render backend settings

- Repository: this repo
- Root directory:

```text
solutions/labs/lab02-code-analyzer
```

- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Render environment variables

Recommended:

```text
ANALYZER_PROVIDER=groq
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.1-8b-instant
CORS_ALLOW_ORIGINS=https://your-frontend.vercel.app
```

## Vercel Deployment

### Vercel frontend settings

- Import the same GitHub repo into Vercel
- Framework preset: `Other`
- Root directory:

```text
solutions/labs/lab02-code-analyzer-frontend
```

### Before deploying frontend

Update:

- [../lab02-code-analyzer-frontend/config.js](../lab02-code-analyzer-frontend/config.js)

Set:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://your-backend.onrender.com"
};
```

Then redeploy the frontend on Vercel.

## Example Request

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "analysis_type": "security",
    "code": "password = \"secret\"\nprint(password)\n"
  }'
```
