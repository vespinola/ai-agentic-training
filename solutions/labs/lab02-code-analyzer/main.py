#!/usr/bin/env python3
"""Render-ready backend starter for the Lab 02 code analyzer."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Literal
from urllib import error, request

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


AnalysisType = Literal["general", "security", "performance"]
SUPPORTED_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "ruby",
    "csharp",
    "cpp",
}


class Issue(BaseModel):
    severity: Literal["high", "medium", "low"]
    line: int | None = None
    category: Literal["bug", "security", "performance", "style", "maintainability"]
    description: str
    suggestion: str


class Metrics(BaseModel):
    complexity: Literal["low", "medium", "high"]
    readability: Literal["low", "medium", "high"]
    test_coverage_estimate: Literal["low", "medium", "high"]


class AnalyzeRequest(BaseModel):
    code: str = Field(min_length=1, description="Source code to analyze")
    language: str = Field(min_length=1, description="Programming language name")
    analysis_type: AnalysisType = "general"


class AnalyzeResponse(BaseModel):
    summary: str
    issues: list[Issue]
    suggestions: list[str]
    metrics: Metrics
    analysis_type: AnalysisType
    provider: str


def parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_system_prompt(analysis_type: AnalysisType) -> str:
    focus_map = {
        "general": "correctness, maintainability, readability, and overall engineering quality",
        "security": "security vulnerabilities, unsafe patterns, secrets handling, and trust boundaries",
        "performance": "performance bottlenecks, unnecessary work, scalability, and resource usage",
    }
    return (
        "You are a senior software engineer performing structured code review. "
        f"Focus on {focus_map[analysis_type]}. "
        "Return strict JSON only with this exact shape: "
        '{"summary": "...", "issues": [{"severity": "high|medium|low", "line": 1, '
        '"category": "bug|security|performance|style|maintainability", '
        '"description": "...", "suggestion": "..."}], '
        '"suggestions": ["..."], '
        '"metrics": {"complexity": "low|medium|high", "readability": "low|medium|high", '
        '"test_coverage_estimate": "low|medium|high"}}. '
        "Keep the summary to 2-3 sentences."
    )


def build_user_prompt(payload: AnalyzeRequest) -> str:
    return (
        f"Language: {payload.language}\n"
        f"Analysis type: {payload.analysis_type}\n"
        "Review the following code and return only JSON.\n\n"
        f"{payload.code}"
    )


def line_of_match(code: str, pattern: str) -> int | None:
    for index, line in enumerate(code.splitlines(), start=1):
        if re.search(pattern, line):
            return index
    return None


class AnalyzerClient(ABC):
    @abstractmethod
    def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        raise NotImplementedError


class MockAnalyzerClient(AnalyzerClient):
    """Heuristic fallback so the app works before adding a real API key."""

    def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        code = payload.code
        issues: list[Issue] = []

        if "eval(" in code or "exec(" in code:
            issues.append(
                Issue(
                    severity="high",
                    line=line_of_match(code, r"\b(eval|exec)\s*\("),
                    category="security",
                    description="Dynamic code execution can allow arbitrary code to run.",
                    suggestion="Avoid eval/exec and use safer parsing or explicit dispatch.",
                )
            )

        if re.search(r"(password|secret|api_key)\s*=\s*['\"]", code, re.IGNORECASE):
            issues.append(
                Issue(
                    severity="high",
                    line=line_of_match(code, r"(password|secret|api_key)\s*=\s*['\"]"),
                    category="security",
                    description="Potential hard-coded secret detected in source code.",
                    suggestion="Move secrets to environment variables or a secure secret manager.",
                )
            )

        if re.search(r"except\s*:\s*$", code, re.MULTILINE):
            issues.append(
                Issue(
                    severity="medium",
                    line=line_of_match(code, r"except\s*:\s*$"),
                    category="maintainability",
                    description="Bare except blocks hide useful errors and make debugging harder.",
                    suggestion="Catch specific exception types and log useful failure context.",
                )
            )

        if "print(" in code:
            issues.append(
                Issue(
                    severity="low",
                    line=line_of_match(code, r"\bprint\s*\("),
                    category="style",
                    description="Debug printing is present in the code path.",
                    suggestion="Replace print statements with structured logging where appropriate.",
                )
            )

        if code.count("for ") >= 2:
            issues.append(
                Issue(
                    severity="medium",
                    line=line_of_match(code, r"\bfor\b"),
                    category="performance",
                    description="Multiple loops may indicate unnecessary repeated work.",
                    suggestion="Check whether loops can be combined or replaced with indexed lookups.",
                )
            )

        if not issues:
            issues.append(
                Issue(
                    severity="low",
                    line=None,
                    category="maintainability",
                    description="No obvious heuristic issue was found by the mock analyzer.",
                    suggestion="Add a real LLM provider to get deeper semantic feedback.",
                )
            )

        suggestions = [
            "Add automated tests that cover happy path, edge cases, and failures.",
            "Keep functions focused and name variables to reflect intent clearly.",
        ]

        if payload.analysis_type == "security":
            suggestions.append("Validate all untrusted input and document trust boundaries.")
        elif payload.analysis_type == "performance":
            suggestions.append("Measure hotspots before optimizing and compare before/after results.")
        else:
            suggestions.append("Use a structured system prompt so the JSON output stays consistent.")

        non_empty_lines = [line for line in code.splitlines() if line.strip()]
        complexity = "high" if len(non_empty_lines) > 80 or len(issues) >= 4 else "medium" if len(non_empty_lines) > 25 else "low"
        readability = "low" if len(code.splitlines()) > 120 else "medium" if len(issues) >= 3 else "high"
        coverage = "low" if "test" not in code.lower() else "medium"

        summary = (
            f"The {payload.language} snippet was reviewed with a {payload.analysis_type} focus. "
            f"The mock analyzer found {len(issues)} notable issue(s) and highlighted the main risks in structured form."
        )

        return AnalyzeResponse(
            summary=summary,
            issues=issues,
            suggestions=suggestions,
            metrics=Metrics(
                complexity=complexity,
                readability=readability,
                test_coverage_estimate=coverage,
            ),
            analysis_type=payload.analysis_type,
            provider="mock",
        )


class OpenAICompatibleAnalyzerClient(AnalyzerClient):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": build_system_prompt(payload.analysis_type)},
                {"role": "user", "content": build_user_prompt(payload)},
            ],
        }
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            self.base_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=45) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=502, detail=f"LLM provider error: {message}") from exc
        except error.URLError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach LLM provider: {exc.reason}") from exc

        content = raw["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="LLM response was not valid JSON.") from exc

        try:
            result = AnalyzeResponse(
                summary=parsed["summary"],
                issues=parsed["issues"],
                suggestions=parsed["suggestions"],
                metrics=parsed["metrics"],
                analysis_type=payload.analysis_type,
                provider=f"openai-compatible:{self.model}",
            )
        except KeyError as exc:
            raise HTTPException(status_code=502, detail=f"LLM response missed field: {exc.args[0]}") from exc

        return result


def get_analyzer_client() -> AnalyzerClient:
    provider = os.getenv("ANALYZER_PROVIDER", "").strip().lower()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if provider == "mock" or not api_key:
        return MockAnalyzerClient()

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions").strip()
    return OpenAICompatibleAnalyzerClient(api_key=api_key, model=model, base_url=base_url)


app = FastAPI(title="Lab 02 Code Analyzer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "lab02-code-analyzer-backend",
        "endpoints": ["/api/analyze", "/health"],
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
    }


@app.get("/health")
def health() -> dict[str, str]:
    provider = os.getenv("ANALYZER_PROVIDER", "mock") or "mock"
    return {"status": "ok", "provider": provider}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    language = payload.language.strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{payload.language}'. Supported values: {', '.join(sorted(SUPPORTED_LANGUAGES))}",
        )

    normalized = AnalyzeRequest(
        code=payload.code.strip(),
        language=language,
        analysis_type=payload.analysis_type,
    )
    client = get_analyzer_client()
    return client.analyze(normalized)
