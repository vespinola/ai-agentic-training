#!/usr/bin/env python3
"""Run Module 1 provider comparisons and generate a draft report."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
OFFLINE_DRAFT_MODE = os.getenv("OFFLINE_DRAFT_MODE", "").lower() in {"1", "true", "yes"}


def load_env_file() -> None:
    """Load a local .env file if present without overriding real env vars."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file()


SYSTEM_PROMPT = "You are a helpful programming assistant."

TEST_PROMPTS: list[dict[str, str]] = [
    {
        "name": "code_generation",
        "prompt": (
            "Write a function that finds the longest palindromic substring. "
            "Include type hints and a docstring."
        ),
    },
    {
        "name": "reasoning",
        "prompt": (
            "A farmer has 17 sheep. All but 9 die. "
            "How many sheep are left? Explain your reasoning step by step."
        ),
    },
    {
        "name": "refactoring",
        "prompt": (
            "Refactor this code to be more idiomatic:\n\n"
            "def get_evens(numbers):\n"
            "    result = []\n"
            "    for i in range(len(numbers)):\n"
            "        if numbers[i] % 2 == 0:\n"
            "            result.append(numbers[i])\n"
            "    return result\n"
        ),
    },
    {
        "name": "ambiguous_request",
        "prompt": (
            "I need to improve performance in my app. "
            "What should I do?"
        ),
    },
]


@dataclass
class ProviderConfig:
    name: str
    api_key_env: str
    model_env: str
    default_model: str

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env)

    @property
    def model(self) -> str:
        return os.getenv(self.model_env, self.default_model)


PROVIDERS = [
    ProviderConfig("openai", "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o"),
    ProviderConfig(
        "anthropic",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "claude-3-5-sonnet-latest",
    ),
    ProviderConfig("gemini", "GOOGLE_API_KEY", "GEMINI_MODEL", "gemini-1.5-pro"),
]


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def call_openai(config: ProviderConfig, user_prompt: str) -> str:
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    response = post_json(
        "https://api.openai.com/v1/chat/completions",
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
    )
    return response["choices"][0]["message"]["content"]


def call_anthropic(config: ProviderConfig, user_prompt: str) -> str:
    payload = {
        "model": config.model,
        "max_tokens": 1200,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    response = post_json(
        "https://api.anthropic.com/v1/messages",
        payload,
        {
            "Content-Type": "application/json",
            "x-api-key": str(config.api_key),
            "anthropic-version": "2023-06-01",
        },
    )
    blocks = response.get("content", [])
    texts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
    return "\n".join(part for part in texts if part).strip()


def call_gemini(config: ProviderConfig, user_prompt: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.model}:generateContent?key={config.api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    response = post_json(url, payload, {"Content-Type": "application/json"})

    candidates = response.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part.get("text", "") for part in parts if "text" in part]
    return "\n".join(part for part in texts if part).strip()


CALLERS = {
    "openai": call_openai,
    "anthropic": call_anthropic,
    "gemini": call_gemini,
}


OFFLINE_SAMPLE_RESPONSES: dict[str, dict[str, str]] = {
    "openai": {
        "code_generation": (
            'def longest_palindromic_substring(s: str) -> str:\n'
            '    """Return the longest palindromic substring in s."""\n'
            "    if not s:\n"
            '        return ""\n'
            "    start = end = 0\n"
            "\n"
            "    def expand(left: int, right: int) -> tuple[int, int]:\n"
            "        while left >= 0 and right < len(s) and s[left] == s[right]:\n"
            "            left -= 1\n"
            "            right += 1\n"
            "        return left + 1, right - 1\n"
            "\n"
            "    for i in range(len(s)):\n"
            "        for l, r in (expand(i, i), expand(i, i + 1)):\n"
            "            if r - l > end - start:\n"
            "                start, end = l, r\n"
            "    return s[start:end + 1]\n"
        ),
        "reasoning": (
            "9 sheep are left. The phrase 'all but 9 die' means everything except 9 died, "
            "so the remaining number is 9."
        ),
        "refactoring": (
            "def get_evens(numbers):\n"
            "    return [number for number in numbers if number % 2 == 0]\n\n"
            "This is more idiomatic because it iterates directly over the values instead of "
            "indexing into the list."
        ),
        "ambiguous_request": (
            "It depends on where the bottleneck is. I would first profile the app, then check "
            "database queries, network calls, rendering hotspots, and caching opportunities."
        ),
    }
}


def safe_call(config: ProviderConfig, user_prompt: str) -> dict[str, Any]:
    if not config.api_key:
        return {
            "provider": config.name,
            "model": config.model,
            "error": f"Missing {config.api_key_env}",
        }

    started = time.perf_counter()
    try:
        response_text = CALLERS[config.name](config, user_prompt)
        elapsed = round(time.perf_counter() - started, 2)
        return {
            "provider": config.name,
            "model": config.model,
            "response": response_text,
            "latency_seconds": elapsed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "provider": config.name,
            "model": config.model,
            "error": f"HTTP {exc.code}: {body}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": config.name,
            "model": config.model,
            "error": str(exc),
        }


def maybe_build_offline_result(provider_name: str, test_name: str) -> dict[str, Any] | None:
    sample = OFFLINE_SAMPLE_RESPONSES.get(provider_name, {}).get(test_name)
    if not sample:
        return None
    return {
        "provider": provider_name,
        "model": "offline-draft",
        "response": sample,
        "latency_seconds": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "offline_draft": True,
    }


def count_markers(text: str, markers: list[str]) -> int:
    lower = text.lower()
    return sum(1 for marker in markers if marker in lower)


def bounded_score(value: int) -> int:
    return max(1, min(value, 10))


def score_code_generation(text: str) -> tuple[int, int, int, str]:
    lower = text.lower()
    correctness = 5
    if "def " in text or "function " in text:
        correctness += 2
    if "palindrome" in lower:
        correctness += 1
    if "return" in lower:
        correctness += 1
    if "expand" in lower or "center" in lower or "dynamic programming" in lower:
        correctness += 1

    code_quality = 5
    if ":" in text and "->" in text:
        code_quality += 2
    if "edge case" in lower or "complexity" in lower:
        code_quality += 2
    if count_markers(text, ["helper", "clean", "readable", "idiomatic"]) > 0:
        code_quality += 1

    documentation = 4
    if '"""' in text or "docstring" in lower or "/**" in text:
        documentation += 4
    if count_markers(text, ["args", "returns", "parameters"]) > 0:
        documentation += 2

    note = "Draft score based on structure, explanation, and documentation markers."
    return (
        bounded_score(correctness),
        bounded_score(code_quality),
        bounded_score(documentation),
        note,
    )


def score_reasoning(text: str) -> tuple[int, int, str]:
    lower = text.lower()
    correct_answer = 9 if re.search(r"\b9\b", text) else 4
    explanation = 5
    if count_markers(text, ["step", "because", "all but 9", "therefore"]) >= 2:
        explanation += 3
    if "\n" in text or count_markers(text, ["1.", "2.", "- "]) > 0:
        explanation += 1
    note = "Correct answer should be 9 because 'all but 9 die' means 9 remain."
    return bounded_score(correct_answer), bounded_score(explanation), note


def score_refactoring(text: str) -> tuple[int, int, str]:
    lower = text.lower()
    improvement = 5
    if "[" in text and "for" in lower and "if" in lower:
        improvement += 3
    if "list comprehension" in lower or "idiomatic" in lower:
        improvement += 1
    if "enumerate" in lower or "direct iteration" in lower:
        improvement += 1

    explanation = 5
    if count_markers(text, ["readable", "idiomatic", "simpler", "clearer"]) >= 2:
        explanation += 3
    if "\n" in text or count_markers(text, ["because", "instead of"]) > 0:
        explanation += 1

    note = "Higher score if the answer removes index-based iteration and explains why."
    return bounded_score(improvement), bounded_score(explanation), note


def score_ambiguous_request(text: str) -> tuple[int, int, str]:
    lower = text.lower()
    interpretation = 4
    if count_markers(
        text,
        ["depends", "clarify", "more context", "what kind", "assumption", "before"],
    ) >= 1:
        interpretation += 4
    if "frontend" in lower or "backend" in lower or "database" in lower:
        interpretation += 1

    suggestions = 4
    if count_markers(
        text,
        ["profile", "measure", "cache", "database", "query", "network", "latency"],
    ) >= 3:
        suggestions += 4
    if "\n" in text or count_markers(text, ["1.", "2.", "- "]) > 0:
        suggestions += 1

    note = "Higher score if the model asks for context and gives practical next steps."
    return bounded_score(interpretation), bounded_score(suggestions), note


def evaluate_prompt(prompt_name: str, provider_result: dict[str, Any]) -> dict[str, Any]:
    if "error" in provider_result:
        return {"error": provider_result["error"]}

    text = provider_result.get("response", "")
    if prompt_name == "code_generation":
        correctness, code_quality, documentation, note = score_code_generation(text)
        return {
            "Correctness": correctness,
            "Code Quality": code_quality,
            "Documentation": documentation,
            "Notes": note,
        }
    if prompt_name == "reasoning":
        correct_answer, explanation, note = score_reasoning(text)
        return {
            "Correct Answer": correct_answer,
            "Explanation": explanation,
            "Notes": note,
        }
    if prompt_name == "refactoring":
        improvement, explanation, note = score_refactoring(text)
        return {
            "Improvement": improvement,
            "Explanation": explanation,
            "Notes": note,
        }
    if prompt_name == "ambiguous_request":
        interpretation, suggestions, note = score_ambiguous_request(text)
        return {
            "Interpretation": interpretation,
            "Suggestions": suggestions,
            "Notes": note,
        }
    return {}


def build_results() -> dict[str, Any]:
    results: dict[str, Any] = {
        "tests": {},
        "providers_run": [],
        "generated_at": None,
        "offline_draft_mode": OFFLINE_DRAFT_MODE,
    }
    enabled = [provider for provider in PROVIDERS if provider.api_key]
    results["providers_run"] = [provider.name for provider in enabled]
    results["generated_at"] = datetime.now(timezone.utc).isoformat()

    for test in TEST_PROMPTS:
        print(f"\n{'=' * 60}")
        print(f"Test: {test['name']}")
        results["tests"][test["name"]] = {}

        for provider in PROVIDERS:
            print(f"- Running {provider.name}...")
            result = safe_call(provider, test["prompt"])
            if (
                OFFLINE_DRAFT_MODE
                and "error" in result
                and provider.name == "openai"
            ):
                offline_result = maybe_build_offline_result(provider.name, test["name"])
                if offline_result is not None:
                    result = offline_result
                    print("  Using offline draft response for OpenAI.")
            results["tests"][test["name"]][provider.name] = result

            if "error" in result:
                print(f"  Error: {result['error']}")
            else:
                preview = result["response"][:160].replace("\n", " ")
                print(f"  OK in {result['latency_seconds']}s: {preview}...")

    return results


def summarize_overall(results: dict[str, Any]) -> dict[str, Any]:
    scoreboard: dict[str, dict[str, list[int]]] = {
        "openai": {},
        "anthropic": {},
        "gemini": {},
    }
    latency: dict[str, list[float]] = {"openai": [], "anthropic": [], "gemini": []}

    for test_name, providers in results["tests"].items():
        for provider_name, provider_result in providers.items():
            evaluation = evaluate_prompt(test_name, provider_result)
            for key, value in evaluation.items():
                if isinstance(value, int):
                    scoreboard.setdefault(provider_name, {}).setdefault(key, []).append(value)
            if "latency_seconds" in provider_result:
                latency.setdefault(provider_name, []).append(provider_result["latency_seconds"])

    averages: dict[str, dict[str, float]] = {}
    for provider_name, categories in scoreboard.items():
        averages[provider_name] = {}
        for category, values in categories.items():
            if values:
                averages[provider_name][category] = round(sum(values) / len(values), 1)

    fastest = None
    fastest_value = None
    for provider_name, values in latency.items():
        if not values:
            continue
        avg = sum(values) / len(values)
        if fastest_value is None or avg < fastest_value:
            fastest = provider_name
            fastest_value = avg

    return {
        "averages": averages,
        "fastest_provider": fastest,
    }


def provider_metric(results: dict[str, Any], test_name: str, provider_name: str, metric: str) -> str:
    evaluation = evaluate_prompt(test_name, results["tests"][test_name][provider_name])
    value = evaluation.get(metric)
    return str(value) if value is not None else "N/A"


def provider_note(results: dict[str, Any], test_name: str) -> str:
    notes = []
    for provider_name in ["openai", "anthropic", "gemini"]:
        evaluation = evaluate_prompt(test_name, results["tests"][test_name][provider_name])
        if "error" in evaluation:
            notes.append(f"{provider_name}: unavailable")
        else:
            notes.append(f"{provider_name}: {evaluation.get('Notes', '')}")
    return " ".join(notes)


def find_best_provider(results: dict[str, Any], metric_names: list[str], test_name: str) -> str:
    best_provider = "N/A"
    best_score = -1.0
    for provider_name in ["openai", "anthropic", "gemini"]:
        evaluation = evaluate_prompt(test_name, results["tests"][test_name][provider_name])
        values = [evaluation.get(metric) for metric in metric_names if isinstance(evaluation.get(metric), int)]
        if not values:
            continue
        score = sum(values) / len(values)
        if score > best_score:
            best_score = score
            best_provider = provider_name
    return best_provider


def build_report(results: dict[str, Any]) -> str:
    overall = summarize_overall(results)
    best_code = find_best_provider(results, ["Correctness", "Code Quality", "Documentation"], "code_generation")
    best_reasoning = find_best_provider(results, ["Correct Answer", "Explanation"], "reasoning")
    best_refactoring = find_best_provider(results, ["Improvement", "Explanation"], "refactoring")
    best_ambiguity = find_best_provider(results, ["Interpretation", "Suggestions"], "ambiguous_request")

    lines = [
        "# Model Comparison Report",
        "",
        "Generated by `compare_models.py`. Review and edit before submitting.",
        (
            "This report includes offline draft content because live provider calls were not fully "
            "available."
            if results.get("offline_draft_mode")
            else ""
        ),
        "",
        "## Code Generation",
        "| Criteria | OpenAI | Anthropic | Gemini | Notes |",
        "|----------|--------|-----------|--------|-------|",
        (
            f"| Correctness | {provider_metric(results, 'code_generation', 'openai', 'Correctness')} "
            f"| {provider_metric(results, 'code_generation', 'anthropic', 'Correctness')} "
            f"| {provider_metric(results, 'code_generation', 'gemini', 'Correctness')} "
            f"| {provider_note(results, 'code_generation')} |"
        ),
        (
            f"| Code Quality | {provider_metric(results, 'code_generation', 'openai', 'Code Quality')} "
            f"| {provider_metric(results, 'code_generation', 'anthropic', 'Code Quality')} "
            f"| {provider_metric(results, 'code_generation', 'gemini', 'Code Quality')} "
            f"| Heuristic draft based on structure and explanation markers. |"
        ),
        (
            f"| Documentation | {provider_metric(results, 'code_generation', 'openai', 'Documentation')} "
            f"| {provider_metric(results, 'code_generation', 'anthropic', 'Documentation')} "
            f"| {provider_metric(results, 'code_generation', 'gemini', 'Documentation')} "
            f"| Looks for docstrings, parameter notes, and explanation quality. |"
        ),
        "",
        "## Reasoning",
        "| Criteria | OpenAI | Anthropic | Gemini | Notes |",
        "|----------|--------|-----------|--------|-------|",
        (
            f"| Correct Answer | {provider_metric(results, 'reasoning', 'openai', 'Correct Answer')} "
            f"| {provider_metric(results, 'reasoning', 'anthropic', 'Correct Answer')} "
            f"| {provider_metric(results, 'reasoning', 'gemini', 'Correct Answer')} "
            f"| Correct answer should be 9. |"
        ),
        (
            f"| Explanation | {provider_metric(results, 'reasoning', 'openai', 'Explanation')} "
            f"| {provider_metric(results, 'reasoning', 'anthropic', 'Explanation')} "
            f"| {provider_metric(results, 'reasoning', 'gemini', 'Explanation')} "
            f"| Higher score means clearer step-by-step reasoning. |"
        ),
        "",
        "## Refactoring",
        "| Criteria | OpenAI | Anthropic | Gemini | Notes |",
        "|----------|--------|-----------|--------|-------|",
        (
            f"| Improvement | {provider_metric(results, 'refactoring', 'openai', 'Improvement')} "
            f"| {provider_metric(results, 'refactoring', 'anthropic', 'Improvement')} "
            f"| {provider_metric(results, 'refactoring', 'gemini', 'Improvement')} "
            f"| Better scores usually remove index-based iteration. |"
        ),
        (
            f"| Explanation | {provider_metric(results, 'refactoring', 'openai', 'Explanation')} "
            f"| {provider_metric(results, 'refactoring', 'anthropic', 'Explanation')} "
            f"| {provider_metric(results, 'refactoring', 'gemini', 'Explanation')} "
            f"| Higher score means stronger rationale for the cleanup. |"
        ),
        "",
        "## Ambiguous Request Handling",
        "| Criteria | OpenAI | Anthropic | Gemini | Notes |",
        "|----------|--------|-----------|--------|-------|",
        (
            f"| Interpretation | {provider_metric(results, 'ambiguous_request', 'openai', 'Interpretation')} "
            f"| {provider_metric(results, 'ambiguous_request', 'anthropic', 'Interpretation')} "
            f"| {provider_metric(results, 'ambiguous_request', 'gemini', 'Interpretation')} "
            f"| Higher score means the model stated assumptions or asked for context. |"
        ),
        (
            f"| Suggestions | {provider_metric(results, 'ambiguous_request', 'openai', 'Suggestions')} "
            f"| {provider_metric(results, 'ambiguous_request', 'anthropic', 'Suggestions')} "
            f"| {provider_metric(results, 'ambiguous_request', 'gemini', 'Suggestions')} "
            f"| Higher score means more actionable performance advice. |"
        ),
        "",
        "## Overall Impressions",
        f"- Best for code generation: {best_code}",
        f"- Best for reasoning: {best_reasoning}",
        f"- Best for refactoring: {best_refactoring}",
        f"- Most helpful with ambiguous requests: {best_ambiguity}",
        f"- Fastest response time: {overall.get('fastest_provider', 'N/A')}",
        "- Personal preference and why: Update this line after reading the raw responses.",
        "",
        "## Three Interesting Differences",
        "1. Note which provider was most cautious about assumptions.",
        "2. Note which provider gave the clearest code or refactoring explanation.",
        "3. Note whether the fastest provider also gave the best answer quality.",
        "",
        "## Provider Averages",
        "```json",
        json.dumps(overall["averages"], indent=2),
        "```",
    ]
    return "\n".join(lines)


def main() -> None:
    results = build_results()

    results_path = OUTPUT_DIR / "model_comparison_results.json"
    results_path.write_text(json.dumps(results, indent=2))

    report = build_report(results)
    report_path = OUTPUT_DIR / "model_comparison_report.md"
    report_path.write_text(report)

    print("\nSaved:")
    print(f"- {results_path}")
    print(f"- {report_path}")


if __name__ == "__main__":
    main()
