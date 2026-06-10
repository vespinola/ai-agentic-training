#!/usr/bin/env python3
"""Final project backend for Option A: AI Code Review Bot.

This implementation intentionally combines ideas from Labs 02, 04, and 05:

- Lab 02: prompt-driven code review with structured JSON output
- Lab 04: retrieval of grounded review guidance plus a lightweight evaluation set
- Lab 05: explicit workflow phases, activity trace, and worker-style orchestration

The result is a portfolio-grade review service that still fits the final project
brief while clearly showing the progression across the course.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from openai import APIConnectionError as OpenAIAPIConnectionError
from openai import APIStatusError as OpenAIAPIStatusError
from pydantic import BaseModel, Field


ReviewMode = Literal["general", "security", "performance", "deep"]
Severity = Literal["critical", "high", "medium", "low"]
IssueCategory = Literal["bug", "security", "performance", "style", "maintainability"]
LanguageName = Literal[
    "python",
    "swift",
    "kotlin",
    "javascript",
    "typescript",
    "java",
    "go",
    "ruby",
    "csharp",
    "cpp",
]

SUPPORTED_LANGUAGES = {
    "python",
    "swift",
    "kotlin",
    "javascript",
    "typescript",
    "java",
    "go",
    "ruby",
    "csharp",
    "cpp",
}
ALLOWED_CATEGORIES = {"bug", "security", "performance", "style", "maintainability"}
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}
BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_BASE_PATH = BASE_DIR / "review_knowledge_base.json"
DATASET_PATH = BASE_DIR / "evaluation_dataset.json"
LOGGER = logging.getLogger("final-project-code-review-bot")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


class Issue(BaseModel):
    severity: Severity
    line: int | None = None
    category: IssueCategory
    description: str
    suggestion: str


class ReviewMetrics(BaseModel):
    overall_score: int = Field(ge=1, le=10)
    complexity: Literal["low", "medium", "high"]
    maintainability: Literal["poor", "fair", "good", "strong"]
    confidence: Literal["low", "medium", "high"]


class ReviewRequest(BaseModel):
    code: str = Field(min_length=1, description="Source code to review")
    language: str = Field(min_length=1, description="Programming language name")
    review_mode: ReviewMode = "general"
    focus: list[str] = Field(default_factory=list, description="Optional extra review focus areas")
    max_issues: int = Field(default=8, ge=1, le=12)


class KnowledgeDocument(BaseModel):
    id: str
    title: str
    category: str
    body: str
    languages: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class KnowledgeHit(BaseModel):
    id: str
    title: str
    category: str
    score: float
    excerpt: str


class TraceEntry(BaseModel):
    step: int
    actor: str
    event: str
    detail: str
    payload: dict[str, object] = Field(default_factory=dict)


class ReviewDraft(BaseModel):
    summary: str
    issues: list[Issue]
    suggestions: list[str]
    metrics: ReviewMetrics
    confidence_notes: list[str] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    success: bool
    status: str
    request_id: str
    provider: str
    language: str
    review_mode: ReviewMode
    workers_used: list[str]
    knowledge_hits: list[KnowledgeHit]
    summary: str
    issues: list[Issue]
    suggestions: list[str]
    metrics: ReviewMetrics
    activity_log: list[TraceEntry]
    warnings: list[str]
    duration_ms: int


class ReviewEvalExample(BaseModel):
    id: str
    language: str
    review_mode: ReviewMode
    code: str
    expected_categories: list[IssueCategory] = Field(min_length=1)
    expected_min_issue_count: int = Field(default=1, ge=1)


class EvaluateRequest(BaseModel):
    examples: list[ReviewEvalExample] = Field(default_factory=list)


class EvalExampleResult(BaseModel):
    id: str
    review_mode: ReviewMode
    language: str
    expected_categories: list[IssueCategory]
    returned_categories: list[IssueCategory]
    matched_categories: list[IssueCategory]
    expected_min_issue_count: int
    returned_issue_count: int
    category_recall: float
    issue_count_passed: bool


class EvaluationSummary(BaseModel):
    example_count: int
    avg_category_recall: float
    issue_count_pass_rate: float


class EvaluateResponse(BaseModel):
    provider: str
    dataset_name: str
    summary: EvaluationSummary
    examples: list[EvalExampleResult]


class WorkflowState(BaseModel):
    request_id: str
    language: str
    review_mode: ReviewMode
    max_issues: int
    focus: list[str]
    status: str = "running"
    knowledge_hits: list[KnowledgeHit] = Field(default_factory=list)
    draft: ReviewDraft | None = None
    final_review: ReviewDraft | None = None
    activity_log: list[TraceEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReviewBackend(ABC):
    @abstractmethod
    def review(
        self,
        payload: ReviewRequest,
        state: WorkflowState,
        guidance: list[KnowledgeHit],
    ) -> ReviewDraft:
        raise NotImplementedError

    @abstractmethod
    def validate(
        self,
        payload: ReviewRequest,
        state: WorkflowState,
        draft: ReviewDraft,
        guidance: list[KnowledgeHit],
    ) -> ReviewDraft:
        raise NotImplementedError


def load_local_env_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env_file()


def parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_provider_name(value: str) -> str:
    return value.strip().lower()


def line_of_match(code: str, pattern: str) -> int | None:
    for index, line in enumerate(code.splitlines(), start=1):
        if re.search(pattern, line):
            return index
    return None


def count_non_empty_lines(code: str) -> int:
    return sum(1 for line in code.splitlines() if line.strip())


def extract_json_object(text: str) -> dict[str, object]:
    cleaned = text.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("Model did not return valid JSON.")
        return json.loads(match.group(0))


def normalize_issue_category(raw_value: object, issue: dict[str, object]) -> str:
    value = str(raw_value or "").strip().lower().replace("_", "-")
    if value in ALLOWED_CATEGORIES:
        return value

    category_aliases = {
        "correctness": "bug",
        "logic": "bug",
        "logic-error": "bug",
        "error-handling": "bug",
        "thread-safety": "bug",
        "concurrency": "bug",
        "race-condition": "bug",
        "safety": "security",
        "auth": "security",
        "authentication": "security",
        "authorization": "security",
        "privacy": "security",
        "injection": "security",
        "validation": "security",
        "input-validation": "security",
        "speed": "performance",
        "efficiency": "performance",
        "optimization": "performance",
        "complexity": "performance",
        "readability": "style",
        "formatting": "style",
        "naming": "style",
        "logging": "style",
        "best-practices": "maintainability",
        "design": "maintainability",
        "architecture": "maintainability",
        "testability": "maintainability",
        "threading": "maintainability",
    }
    if value in category_aliases:
        return category_aliases[value]

    text = " ".join(
        str(issue.get(field, "") or "")
        for field in ("category", "description", "suggestion")
    ).lower()
    if any(token in text for token in {"secret", "token", "auth", "validate", "trust boundary", "sql", "injection"}):
        return "security"
    if any(token in text for token in {"loop", "hot path", "cache", "slow", "performance", "optimiz", "memory"}):
        return "performance"
    if any(token in text for token in {"print", "logging", "readability", "naming", "style"}):
        return "style"
    if any(token in text for token in {"refactor", "maintain", "coupling", "responsibility", "test"}):
        return "maintainability"
    return "bug"


def normalize_issue_severity(raw_value: object, issue: dict[str, object]) -> str:
    value = str(raw_value or "").strip().lower()
    if value in ALLOWED_SEVERITIES:
        return value

    severity_aliases = {
        "blocker": "critical",
        "severe": "high",
        "warning": "medium",
        "minor": "low",
        "info": "low",
        "informational": "low",
    }
    if value in severity_aliases:
        return severity_aliases[value]

    text = " ".join(
        str(issue.get(field, "") or "")
        for field in ("severity", "description", "suggestion")
    ).lower()
    if any(token in text for token in {"secret", "injection", "remote code", "arbitrary code", "credential"}):
        return "critical"
    if any(token in text for token in {"unsafe", "race condition", "data corruption", "security"}):
        return "high"
    if any(token in text for token in {"performance", "maintainability", "complexity"}):
        return "medium"
    return "low"


def normalize_review_payload(raw_payload: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    payload = dict(raw_payload)
    warnings: list[str] = []

    issues = payload.get("issues")
    if isinstance(issues, list):
        normalized_issues: list[dict[str, object]] = []
        for item in issues:
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            normalized_category = normalize_issue_category(normalized.get("category"), normalized)
            if normalized.get("category") != normalized_category:
                warnings.append(
                    f"Normalized model category '{normalized.get('category')}' to '{normalized_category}'."
                )
            normalized["category"] = normalized_category

            normalized_severity = normalize_issue_severity(normalized.get("severity"), normalized)
            if normalized.get("severity") != normalized_severity:
                warnings.append(
                    f"Normalized model severity '{normalized.get('severity')}' to '{normalized_severity}'."
                )
            normalized["severity"] = normalized_severity

            line = normalized.get("line")
            if line in {"", 0, "0"}:
                normalized["line"] = None
            normalized_issues.append(normalized)
        payload["issues"] = normalized_issues

    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        normalized_metrics = dict(metrics)
        try:
            score = int(normalized_metrics.get("overall_score", 7))
        except (TypeError, ValueError):
            score = 7
            warnings.append("Normalized invalid overall_score to default value 7.")
        normalized_metrics["overall_score"] = min(10, max(1, score))

        complexity = str(normalized_metrics.get("complexity", "medium")).strip().lower()
        if complexity not in {"low", "medium", "high"}:
            normalized_metrics["complexity"] = "medium"
            warnings.append(f"Normalized invalid complexity '{complexity}' to 'medium'.")

        maintainability = str(normalized_metrics.get("maintainability", "good")).strip().lower()
        maintainability_aliases = {
            "low": "poor",
            "medium": "fair",
            "high": "strong",
            "excellent": "strong",
            "average": "fair",
        }
        normalized_metrics["maintainability"] = maintainability_aliases.get(maintainability, maintainability)
        if normalized_metrics["maintainability"] not in {"poor", "fair", "good", "strong"}:
            normalized_metrics["maintainability"] = "good"
            warnings.append(f"Normalized invalid maintainability '{maintainability}' to 'good'.")

        confidence = str(normalized_metrics.get("confidence", "medium")).strip().lower()
        if confidence not in {"low", "medium", "high"}:
            normalized_metrics["confidence"] = "medium"
            warnings.append(f"Normalized invalid confidence '{confidence}' to 'medium'.")
        payload["metrics"] = normalized_metrics

    if not isinstance(payload.get("suggestions"), list):
        payload["suggestions"] = []
    if not isinstance(payload.get("confidence_notes"), list):
        payload["confidence_notes"] = []

    return payload, warnings


def build_review_prompt(payload: ReviewRequest, guidance: list[KnowledgeHit]) -> str:
    guidance_block = "\n".join(
        f"- {hit.title}: {hit.excerpt}"
        for hit in guidance
    ) or "- No external guidance retrieved."

    focus_text = ", ".join(payload.focus) if payload.focus else "no extra focus areas supplied"
    return (
        "Role: You are a senior software engineer performing a structured code review.\n"
        "Context: Your output will be parsed by an application and shown in a final project demo.\n"
        "Goal: Find concrete issues grounded in the actual code, prioritize the most important ones, "
        "and produce strict JSON only.\n"
        "Rules:\n"
        "- Use only severities critical, high, medium, low.\n"
        "- Use only categories bug, security, performance, style, maintainability.\n"
        "- Prefer fewer precise findings over many weak guesses.\n"
        "- If a line number is uncertain, use null instead of inventing one.\n"
        "- Include actionable suggestions, not generic advice.\n"
        "Returned JSON shape:\n"
        '{"summary":"...","issues":[{"severity":"high","line":1,"category":"bug","description":"...","suggestion":"..."}],'
        '"suggestions":["..."],"metrics":{"overall_score":7,"complexity":"medium","maintainability":"good","confidence":"high"},'
        '"confidence_notes":["..."]}\n\n'
        f"Language: {payload.language}\n"
        f"Review mode: {payload.review_mode}\n"
        f"Extra focus: {focus_text}\n"
        "Retrieved guidance:\n"
        f"{guidance_block}\n\n"
        "Code:\n"
        f"{payload.code}"
    )


def build_validation_prompt(
    payload: ReviewRequest,
    draft: ReviewDraft,
    guidance: list[KnowledgeHit],
) -> str:
    guidance_block = "\n".join(f"- {hit.title}: {hit.excerpt}" for hit in guidance)
    return (
        "You are a validation reviewer checking another code review for quality.\n"
        "Task: remove duplicate findings, downgrade uncertain claims, and strengthen actionable fixes.\n"
        "Return strict JSON only using the same schema as the original review.\n\n"
        f"Language: {payload.language}\n"
        f"Review mode: {payload.review_mode}\n"
        "Guidance reminder:\n"
        f"{guidance_block}\n\n"
        "Original draft review JSON:\n"
        f"{draft.model_dump_json(indent=2)}"
    )


def tokenize_for_search(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z_]{3,}", value.lower())
        if token not in {"the", "and", "with", "from", "into", "that", "this", "then"}
    }


def load_knowledge_documents() -> list[KnowledgeDocument]:
    if not KNOWLEDGE_BASE_PATH.exists():
        return []
    payload = json.loads(KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8"))
    return [KnowledgeDocument.model_validate(item) for item in payload]


def load_evaluation_dataset() -> list[ReviewEvalExample]:
    if not DATASET_PATH.exists():
        return []
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return [ReviewEvalExample.model_validate(item) for item in payload]


class KnowledgeBase:
    def __init__(self, documents: list[KnowledgeDocument]) -> None:
        self.documents = documents

    def search(self, payload: ReviewRequest, top_k: int = 3) -> list[KnowledgeHit]:
        query = " ".join([payload.language, payload.review_mode, " ".join(payload.focus), payload.code])
        query_tokens = tokenize_for_search(query)
        hits: list[KnowledgeHit] = []

        for document in self.documents:
            doc_tokens = tokenize_for_search(
                " ".join([document.title, document.category, document.body, " ".join(document.keywords)])
            )
            overlap = len(query_tokens & doc_tokens)
            language_bonus = 3 if payload.language in document.languages else 0
            mode_bonus = 2 if payload.review_mode in document.modes else 0
            focus_bonus = 1 if any(item in document.keywords for item in payload.focus) else 0
            score = overlap + language_bonus + mode_bonus + focus_bonus
            if score <= 0:
                continue

            excerpt = document.body.strip()
            if len(excerpt) > 180:
                excerpt = excerpt[:177].rstrip() + "..."

            hits.append(
                KnowledgeHit(
                    id=document.id,
                    title=document.title,
                    category=document.category,
                    score=round(float(score), 2),
                    excerpt=excerpt,
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]


class MockReviewBackend(ReviewBackend):
    """Heuristic review backend for local work, tests, and demos without API keys."""

    def review(
        self,
        payload: ReviewRequest,
        state: WorkflowState,
        guidance: list[KnowledgeHit],
    ) -> ReviewDraft:
        code = payload.code
        issues: list[Issue] = []

        def add_issue(issue: Issue) -> None:
            key = (issue.category, issue.line, issue.description)
            seen = {(item.category, item.line, item.description) for item in issues}
            if key not in seen:
                issues.append(issue)

        if re.search(r"(password|secret|api[_-]?key|token)\s*=\s*['\"]", code, re.IGNORECASE):
            add_issue(
                Issue(
                    severity="critical",
                    line=line_of_match(code, r"(password|secret|api[_-]?key|token)\s*=\s*['\"]"),
                    category="security",
                    description="Potential hard-coded secret detected in source code.",
                    suggestion="Move secrets to environment variables or a dedicated secret manager.",
                )
            )

        if re.search(r"\b(eval|exec)\s*\(", code):
            add_issue(
                Issue(
                    severity="high",
                    line=line_of_match(code, r"\b(eval|exec)\s*\("),
                    category="security",
                    description="Dynamic code execution creates a high-risk trust boundary.",
                    suggestion="Replace eval/exec with explicit parsing or a safe dispatch table.",
                )
            )

        if re.search(r"SELECT .*['\"].*\+.*", code, re.IGNORECASE):
            add_issue(
                Issue(
                    severity="high",
                    line=line_of_match(code, r"SELECT .*['\"].*\+.*"),
                    category="security",
                    description="SQL query appears to be built with string concatenation.",
                    suggestion="Use parameterized queries instead of interpolating untrusted values.",
                )
            )

        if re.search(r"except\s*:\s*$", code, re.MULTILINE):
            add_issue(
                Issue(
                    severity="medium",
                    line=line_of_match(code, r"except\s*:\s*$"),
                    category="maintainability",
                    description="Bare except hides the real failure mode and weakens debugging.",
                    suggestion="Catch specific exception types and log the failure context.",
                )
            )

        if re.search(r"\bconsole\.log\(", code) or re.search(r"\bprint\s*\(", code):
            add_issue(
                Issue(
                    severity="low",
                    line=line_of_match(code, r"\b(console\.log|print)\s*\("),
                    category="style",
                    description="Debug output is present in the normal execution path.",
                    suggestion="Replace ad hoc prints with structured logging or remove them before shipping.",
                )
            )

        if code.count("for ") >= 2 or code.count("while ") >= 2:
            add_issue(
                Issue(
                    severity="medium",
                    line=line_of_match(code, r"\b(for|while)\b"),
                    category="performance",
                    description="Repeated iteration patterns may create avoidable work on larger inputs.",
                    suggestion="Check whether loops can be combined, cached, or replaced with indexed lookups.",
                )
            )

        if payload.language == "python" and re.search(r"def\s+\w+\(.*=\[\]\)|def\s+\w+\(.*=\{\}\)", code):
            add_issue(
                Issue(
                    severity="high",
                    line=line_of_match(code, r"def\s+\w+\(.*=\[\]\)|def\s+\w+\(.*=\{\}\)"),
                    category="bug",
                    description="Mutable default arguments can leak state across function calls.",
                    suggestion="Use None as the default and initialize the list or dict inside the function.",
                )
            )

        if payload.review_mode in {"performance", "deep"} and count_non_empty_lines(code) > 45:
            add_issue(
                Issue(
                    severity="medium",
                    line=1,
                    category="maintainability",
                    description="The snippet is long enough that responsibilities are likely mixed together.",
                    suggestion="Split large routines into smaller units with single, testable responsibilities.",
                )
            )

        if payload.review_mode == "security" and not any(item.category == "security" for item in issues):
            add_issue(
                Issue(
                    severity="low",
                    line=None,
                    category="security",
                    description="No obvious security flaw was found heuristically, but trust boundaries remain unclear.",
                    suggestion="Document inputs, outputs, and any external systems that influence this code path.",
                )
            )

        if not issues:
            add_issue(
                Issue(
                    severity="low",
                    line=None,
                    category="maintainability",
                    description="No major issue was detected by the mock backend in this snippet.",
                    suggestion="Use the LLM-backed provider for deeper semantic reasoning and edge-case discovery.",
                )
            )

        issues = issues[: payload.max_issues]
        severity_penalty = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        score = max(1, 10 - sum(severity_penalty[item.severity] for item in issues[:4]))
        complexity = "high" if count_non_empty_lines(code) > 70 else "medium" if count_non_empty_lines(code) > 25 else "low"
        maintainability = "poor" if len(issues) >= 5 else "fair" if len(issues) >= 3 else "good"
        confidence = "high" if any(item.severity in {"critical", "high"} for item in issues) else "medium"

        focus_note = (
            f"Review mode {payload.review_mode} used {len(guidance)} retrieved guidance note(s)."
        )
        suggestions = [
            "Add automated tests that cover both happy-path behavior and failure handling.",
            "Tighten input validation near the boundary where untrusted data first enters the system.",
        ]
        if payload.review_mode in {"performance", "deep"}:
            suggestions.append("Profile or measure the hot path before optimizing so tradeoffs stay evidence-based.")
        if payload.review_mode in {"security", "deep"}:
            suggestions.append("Review secrets handling, trust boundaries, and logging so sensitive data is not exposed.")

        return ReviewDraft(
            summary=(
                f"This {payload.language} snippet was reviewed in {payload.review_mode} mode. "
                f"The workflow found {len(issues)} issue(s), with the most important risks prioritized first."
            ),
            issues=issues,
            suggestions=suggestions[:4],
            metrics=ReviewMetrics(
                overall_score=score,
                complexity=complexity,
                maintainability=maintainability,
                confidence=confidence,
            ),
            confidence_notes=[
                focus_note,
                "Mock backend findings come from deterministic heuristics plus retrieved review guidance.",
            ],
        )

    def validate(
        self,
        payload: ReviewRequest,
        state: WorkflowState,
        draft: ReviewDraft,
        guidance: list[KnowledgeHit],
    ) -> ReviewDraft:
        deduped: list[Issue] = []
        seen_descriptions: set[str] = set()
        for issue in draft.issues:
            if issue.description in seen_descriptions:
                continue
            seen_descriptions.add(issue.description)
            deduped.append(issue)

        confidence = draft.metrics.confidence
        if payload.review_mode == "deep":
            confidence = "high"

        metrics = draft.metrics.model_copy(update={"confidence": confidence})
        suggestions = list(dict.fromkeys(draft.suggestions + [
            "Triage the highest-severity issue first so the next review pass starts from a safer baseline."
        ]))

        notes = list(draft.confidence_notes)
        if payload.review_mode == "deep":
            notes.append("Deep mode adds a second validation pass before finalizing the review.")

        return draft.model_copy(
            update={
                "issues": deduped[: payload.max_issues],
                "suggestions": suggestions[:4],
                "metrics": metrics,
                "confidence_notes": notes,
            }
        )


class LLMReviewBackend(ReviewBackend):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        api_key = os.getenv("OPENAI_API_KEY") if provider == "openai" else os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(f"Missing API key for provider: {provider}")

        if provider == "groq":
            self.client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        else:
            self.client = OpenAI(api_key=api_key)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _run_prompt(self, prompt: str, state: WorkflowState | None = None) -> ReviewDraft:
        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=0.2,
            )
        except OpenAIAPIConnectionError as exc:
            raise RuntimeError("Could not reach the model provider.") from exc
        except OpenAIAPIStatusError as exc:
            raise RuntimeError(f"Provider returned an API error: {exc.status_code}") from exc

        text = response.output_text
        payload = extract_json_object(text)
        normalized_payload, warnings = normalize_review_payload(payload)
        if state is not None and warnings:
            for warning in warnings:
                if warning not in state.warnings:
                    state.warnings.append(warning)
        return ReviewDraft.model_validate(normalized_payload)

    def review(
        self,
        payload: ReviewRequest,
        state: WorkflowState,
        guidance: list[KnowledgeHit],
    ) -> ReviewDraft:
        return self._run_prompt(build_review_prompt(payload, guidance), state)

    def validate(
        self,
        payload: ReviewRequest,
        state: WorkflowState,
        draft: ReviewDraft,
        guidance: list[KnowledgeHit],
    ) -> ReviewDraft:
        return self._run_prompt(build_validation_prompt(payload, draft, guidance), state)


class SimpleRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        if self.max_requests <= 0:
            return

        now = time.time()
        queue = self.history[key]
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()
        if len(queue) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before reviewing again.")
        queue.append(now)


class ReviewOrchestrator:
    def __init__(self, provider_name: str, knowledge_base: KnowledgeBase, backend: ReviewBackend) -> None:
        self.provider_name = provider_name
        self.knowledge_base = knowledge_base
        self.backend = backend

    def _log(self, state: WorkflowState, actor: str, event: str, detail: str, payload: dict[str, object]) -> None:
        state.activity_log.append(
            TraceEntry(
                step=len(state.activity_log) + 1,
                actor=actor,
                event=event,
                detail=detail,
                payload=payload,
            )
        )

    def run(self, payload: ReviewRequest) -> ReviewResponse:
        started_at = time.perf_counter()
        state = WorkflowState(
            request_id=str(uuid.uuid4()),
            language=payload.language,
            review_mode=payload.review_mode,
            max_issues=payload.max_issues,
            focus=payload.focus,
        )

        self._log(
            state,
            actor="supervisor",
            event="intake",
            detail="Accepted review request and initialized workflow state.",
            payload={
                "language": payload.language,
                "review_mode": payload.review_mode,
                "focus": payload.focus,
            },
        )

        guidance = self.knowledge_base.search(payload)
        state.knowledge_hits = guidance
        self._log(
            state,
            actor="retriever",
            event="guidance",
            detail="Retrieved review guidance to ground the analysis.",
            payload={"knowledge_hit_ids": [item.id for item in guidance]},
        )

        draft = self.backend.review(payload, state, guidance)
        state.draft = draft
        self._log(
            state,
            actor="reviewer",
            event="draft_review",
            detail="Produced the first structured review draft.",
            payload={
                "issue_count": len(draft.issues),
                "overall_score": draft.metrics.overall_score,
            },
        )

        final_review = self.backend.validate(payload, state, draft, guidance)
        state.final_review = final_review
        self._log(
            state,
            actor="validator",
            event="validation",
            detail="Validated the draft review and finalized the response payload.",
            payload={
                "issue_count": len(final_review.issues),
                "confidence": final_review.metrics.confidence,
            },
        )

        state.status = "completed"
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        return ReviewResponse(
            success=True,
            status=state.status,
            request_id=state.request_id,
            provider=self.provider_name,
            language=payload.language,
            review_mode=payload.review_mode,
            workers_used=["retriever", "reviewer", "validator"],
            knowledge_hits=state.knowledge_hits,
            summary=final_review.summary,
            issues=final_review.issues,
            suggestions=final_review.suggestions,
            metrics=final_review.metrics,
            activity_log=state.activity_log,
            warnings=state.warnings,
            duration_ms=duration_ms,
        )


def build_backend() -> tuple[str, ReviewBackend]:
    provider = normalize_provider_name(os.getenv("FINAL_PROJECT_PROVIDER", "mock"))
    if provider == "mock":
        return provider, MockReviewBackend()
    if provider in {"openai", "groq"}:
        return provider, LLMReviewBackend(provider)
    raise ValueError("Unsupported FINAL_PROJECT_PROVIDER. Use mock, openai, or groq.")


def evaluate_examples(examples: list[ReviewEvalExample], orchestrator: ReviewOrchestrator) -> EvaluateResponse:
    results: list[EvalExampleResult] = []
    for example in examples:
        response = orchestrator.run(
            ReviewRequest(
                code=example.code,
                language=example.language,
                review_mode=example.review_mode,
                focus=[],
                max_issues=8,
            )
        )
        returned_categories = [item.category for item in response.issues]
        matched = sorted(set(returned_categories) & set(example.expected_categories))
        recall = len(matched) / len(example.expected_categories)
        results.append(
            EvalExampleResult(
                id=example.id,
                review_mode=example.review_mode,
                language=example.language,
                expected_categories=example.expected_categories,
                returned_categories=returned_categories,
                matched_categories=matched,
                expected_min_issue_count=example.expected_min_issue_count,
                returned_issue_count=len(response.issues),
                category_recall=round(recall, 2),
                issue_count_passed=len(response.issues) >= example.expected_min_issue_count,
            )
        )

    example_count = len(results)
    avg_recall = round(sum(item.category_recall for item in results) / example_count, 2) if results else 0.0
    issue_count_pass_rate = (
        round(sum(1 for item in results if item.issue_count_passed) / example_count, 2)
        if results
        else 0.0
    )

    return EvaluateResponse(
        provider=orchestrator.provider_name,
        dataset_name=DATASET_PATH.name,
        summary=EvaluationSummary(
            example_count=example_count,
            avg_category_recall=avg_recall,
            issue_count_pass_rate=issue_count_pass_rate,
        ),
        examples=results,
    )


PROVIDER_NAME, BACKEND = build_backend()
KNOWLEDGE_BASE = KnowledgeBase(load_knowledge_documents())
ORCHESTRATOR = ReviewOrchestrator(PROVIDER_NAME, KNOWLEDGE_BASE, BACKEND)
RATE_LIMITER = SimpleRateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
)
DEFAULT_EVAL_DATASET = load_evaluation_dataset()

app = FastAPI(title="Final Project - AI Code Review Bot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_supported_language(language: str) -> str:
    normalized = language.strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    return normalized


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "final-project-code-review-bot",
        "provider": PROVIDER_NAME,
        "endpoints": ["/health", "/api/review", "/api/evaluate"],
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "review_modes": ["general", "security", "performance", "deep"],
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "provider": PROVIDER_NAME,
        "knowledge_documents": len(KNOWLEDGE_BASE.documents),
        "default_eval_examples": len(DEFAULT_EVAL_DATASET),
    }


@app.post("/review", response_model=ReviewResponse)
@app.post("/api/review", response_model=ReviewResponse)
def review_code(payload: ReviewRequest, request: Request) -> ReviewResponse:
    payload = payload.model_copy(update={"language": ensure_supported_language(payload.language)})
    client_host = request.client.host if request.client else "unknown"
    RATE_LIMITER.check(client_host)

    try:
        response = ORCHESTRATOR.run(payload)
    except RuntimeError as exc:
        LOGGER.exception("Review workflow failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        LOGGER.exception("Provider response validation failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    LOGGER.info(
        "review_completed request_id=%s language=%s mode=%s issues=%s duration_ms=%s",
        response.request_id,
        response.language,
        response.review_mode,
        len(response.issues),
        response.duration_ms,
    )
    return response


@app.post("/evaluate", response_model=EvaluateResponse)
@app.post("/api/evaluate", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    examples = payload.examples or DEFAULT_EVAL_DATASET
    if not examples:
        raise HTTPException(status_code=400, detail="No evaluation examples were provided.")

    normalized_examples = [
        example.model_copy(update={"language": ensure_supported_language(example.language)})
        for example in examples
    ]
    return evaluate_examples(normalized_examples, ORCHESTRATOR)
