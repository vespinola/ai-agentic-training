#!/usr/bin/env python3
"""Render-ready backend starter for the Lab 02 code analyzer."""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal
from urllib import error, request

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from openai import APIConnectionError as OpenAIAPIConnectionError
from openai import APIStatusError as OpenAIAPIStatusError
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

BASE_DIR = Path(__file__).resolve().parent
LOGGER = logging.getLogger("lab02-code-analyzer")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


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


def load_local_env_file() -> None:
    """Load simple KEY=VALUE pairs from a local .env without overriding real env vars."""
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


def build_system_prompt(analysis_type: AnalysisType) -> str:
    focus_map = {
        "general": "correctness, maintainability, readability, and overall engineering quality",
        "security": "security vulnerabilities, unsafe patterns, secrets handling, and trust boundaries",
        "performance": "performance bottlenecks, unnecessary work, scalability, and resource usage",
    }
    # Module 02 pattern: RCFG prompt design.
    # Role: senior software engineer reviewer
    # Context/Goal: analysis focus varies by analysis_type
    # Format: strict JSON schema for reliable frontend parsing
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
    # Module 02 pattern: explicit task framing with concrete input.
    # This keeps the code, language, and requested analysis type separate from the system prompt.
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
        self.base_url = base_url.rstrip("/")
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        LOGGER.info(
            "Calling OpenAI-compatible provider model=%s base_url=%s analysis_type=%s language=%s",
            self.model,
            self.base_url,
            payload.analysis_type,
            payload.language,
        )
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": build_system_prompt(payload.analysis_type)},
                {"role": "user", "content": build_user_prompt(payload)},
            ],
        }
        try:
            response = self.client.chat.completions.create(**body)
        except OpenAIAPIStatusError as exc:
            message = exc.response.text if exc.response is not None else str(exc)
            LOGGER.error(
                "OpenAI-compatible provider APIStatusError upstream_status=%s base_url=%s body=%s",
                exc.status_code,
                self.base_url,
                message,
            )
            raise HTTPException(
                status_code=502,
                detail=f"LLM provider error (upstream {exc.status_code}): {message}",
            ) from exc
        except OpenAIAPIConnectionError as exc:
            LOGGER.error(
                "OpenAI-compatible provider APIConnectionError base_url=%s reason=%s",
                self.base_url,
                exc,
            )
            raise HTTPException(status_code=502, detail=f"Could not reach LLM provider: {exc}") from exc

        content = response.choices[0].message.content
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


class GeminiAnalyzerClient(AnalyzerClient):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def analyze(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        LOGGER.info(
            "Calling Gemini provider model=%s base_url=%s analysis_type=%s language=%s",
            self.model,
            self.base_url,
            payload.analysis_type,
            payload.language,
        )
        body = {
            "system_instruction": {
                "parts": [{"text": build_system_prompt(payload.analysis_type)}]
            },
            "contents": [
                {
                    "parts": [{"text": build_user_prompt(payload)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        data = json.dumps(body).encode("utf-8")
        url = f"{self.base_url}/models/{self.model}:generateContent"
        req = request.Request(
            url,
            data=data,
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=45) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            LOGGER.error(
                "Gemini provider HTTPError upstream_status=%s url=%s body=%s",
                exc.code,
                url,
                message,
            )
            raise HTTPException(
                status_code=502,
                detail=f"Gemini provider error (upstream {exc.code}): {message}",
            ) from exc
        except error.URLError as exc:
            LOGGER.error(
                "Gemini provider URLError url=%s reason=%s",
                url,
                exc.reason,
            )
            raise HTTPException(status_code=502, detail=f"Could not reach Gemini provider: {exc.reason}") from exc

        try:
            content = raw["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="Gemini response did not include text content.") from exc

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="Gemini response was not valid JSON.") from exc

        try:
            result = AnalyzeResponse(
                summary=parsed["summary"],
                issues=parsed["issues"],
                suggestions=parsed["suggestions"],
                metrics=parsed["metrics"],
                analysis_type=payload.analysis_type,
                provider=f"gemini:{self.model}",
            )
        except KeyError as exc:
            raise HTTPException(status_code=502, detail=f"Gemini response missed field: {exc.args[0]}") from exc

        return result


def get_analyzer_client() -> AnalyzerClient:
    provider = os.getenv("ANALYZER_PROVIDER", "").strip().lower()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

    if provider == "gemini":
        if not gemini_api_key:
            raise HTTPException(
                status_code=500,
                detail="ANALYZER_PROVIDER is set to 'gemini' but GEMINI_API_KEY is missing.",
            )
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip()
        return GeminiAnalyzerClient(api_key=gemini_api_key, model=model, base_url=base_url)

    if provider == "groq":
        if not groq_api_key:
            raise HTTPException(
                status_code=500,
                detail="ANALYZER_PROVIDER is set to 'groq' but GROQ_API_KEY is missing.",
            )
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
        return OpenAICompatibleAnalyzerClient(api_key=groq_api_key, model=model, base_url=base_url)

    if provider in {"", "mock"}:
        return MockAnalyzerClient()

    raise HTTPException(
        status_code=500,
        detail="Unsupported ANALYZER_PROVIDER. Use 'mock', 'groq', or 'gemini'.",
    )


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
    model_env_map = {
        "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "groq": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        "mock": "mock",
    }
    return {"status": "ok", "provider": provider, "model": model_env_map.get(provider, "unknown")}


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
