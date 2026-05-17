# Module 1 Exercise: Model Comparison

This is a self-contained solution project for Module 1 Exercise 1.

It helps you:
- run the same prompts across multiple providers
- save the raw outputs
- generate a draft comparison report you can submit or edit

## What This Project Covers

The exercise asks you to:

1. run the same prompts with multiple LLM providers
2. compare code generation, reasoning, refactoring, and ambiguity handling
3. document a few interesting differences

This project automates most of that work.

## Supported Providers

- OpenAI via `OPENAI_API_KEY`
- Anthropic via `ANTHROPIC_API_KEY`
- Gemini via `GOOGLE_API_KEY`

You can run it with one, two, or all three providers.

## Files

- `compare_models.py`: main script
- `.env.example`: environment variable template
- `outputs/`: generated results and report drafts

## Setup

Create your environment variables. You can either export them in your shell or copy `.env.example` into a local `.env` file and edit it.

Example:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...
```

Optional model overrides:

```bash
export OPENAI_MODEL=gpt-4o
export ANTHROPIC_MODEL=claude-3-5-sonnet-latest
export GEMINI_MODEL=gemini-1.5-pro
```

## Run

```bash
cd solutions/labs/module1-exercise-model-comparison
python3 compare_models.py
```

If your provider is unavailable because of quota or missing billing, you can still generate a usable draft report:

```bash
OFFLINE_DRAFT_MODE=1 python3 compare_models.py
```

This will use a built-in sample OpenAI response set so you can complete the exercise structure and edit it manually afterward.

## Output

The script writes:

- `outputs/model_comparison_results.json`
- `outputs/model_comparison_report.md`

## Notes

- The generated report is a draft, not a perfect evaluator.
- The scoring is heuristic and meant to save time.
- You should still skim the raw responses before submitting.
