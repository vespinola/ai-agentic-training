# Lab 02 Code Analyzer Fast Track

This note is the shortest path through `02-prompting` plus the `lab02-code-analyzer-agent` exercise.

## What Matters From Theory

### 1. Use RCFG for every serious prompt

- `Role`: tell the model who it is
- `Context`: explain where the code lives and what matters
- `Format`: force strict JSON output
- `Goal`: state the exact analysis task

If your prompt misses one of these, results usually get weaker or harder to parse.

### 2. Be explicit, not polite

Weak:

```text
Review this code.
```

Better:

```text
You are a senior Python reviewer.
Focus on security risks.
Return strict JSON with summary, issues, suggestions, and metrics.
```

### 3. Break complex work into steps

For code analysis, good prompts usually ask the model to:

1. Understand what the code is doing
2. Identify concrete issues
3. Classify severity and category
4. Suggest fixes
5. Return structured output

### 4. Design the system prompt before the UI

The system prompt is the core of this lab. The frontend only displays the result. If the prompt is vague, the whole app feels unreliable.

### 5. Structured output is part of the product

Your app should not return raw paragraphs. It should return predictable JSON that the frontend can render cleanly.

## Lab 02 In Plain English

You are building a small app with:

- a backend API that accepts code
- an LLM prompt that analyzes that code
- structured JSON output
- a frontend that lets the user paste or upload code and view the results
- deployment using Render for backend and Vercel for frontend

## Minimum Implementation Plan

### Backend

- Create `POST /api/analyze`
- Accept `code`, `language`, and ideally `analysis_type`
- Validate input with Pydantic
- Build a strong system prompt
- Send prompt + code to the model
- Return normalized JSON
- Add `GET /health`

### Frontend

- Code textarea or file upload
- Language selector
- Analyze button with loading state
- Results view for summary, issues, suggestions, and metrics
- Responsive layout

## Prompt Checklist

Before you call the model, check that your prompt includes:

- the reviewer role
- the analysis focus
- the exact JSON schema
- severity levels
- allowed issue categories
- summary length
- instruction to return JSON only

## Suggested Prompt Shape

```text
Role: You are a senior software engineer performing code review.

Context: The user will submit one code snippet at a time. The result will be
rendered directly in a web UI, so the response must be consistent and parseable.

Goal: Analyze the code for general quality and [security or performance].
Identify concrete issues, classify severity, and recommend specific fixes.

Format: Return strict JSON with:
- summary
- issues: severity, line, category, description, suggestion
- suggestions
- metrics: complexity, readability, test_coverage_estimate
```

## Deliverables Checklist

Use this exact list before you submit:

- [ ] Working code analyzer API in Python or TypeScript
- [ ] Custom system prompt for analysis
- [ ] Structured JSON output
- [ ] At least 2 analysis types such as general + security or general + performance
- [ ] Deployed backend/frontend using Render and Vercel
- [ ] Tested with sample code
- [ ] Web frontend with code input and analysis results
- [ ] Final deployed URL to share

## What To Demo

Your demo should show:

1. A code snippet being pasted or uploaded
2. The user choosing language and analysis type
3. The API response rendered in the UI
4. At least one issue with severity and suggestion
5. The deployed frontend and deployed backend working together

## Easy Misses

- forgetting strict JSON output
- returning fields the frontend does not expect
- only supporting one analysis mode
- no health endpoint
- deploying frontend but not backend
- sharing code without the live URL

## Summary

Lab 02 is really about turning prompting into product behavior. If you get the prompt, schema, and deployment path right, the rest of the lab becomes straightforward.
