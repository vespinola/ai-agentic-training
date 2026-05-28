#!/usr/bin/env python3
"""Render-ready backend starter for the Lab 03 migration workflow agent."""

# Theory cheat sheet for Module 03:
# - Agent vs single prompt:
#   this file uses an explicit multi-step workflow instead of one "migrate this" call.
# - Agent loop:
#   observe -> reason -> act -> check
#   mapped here as analyze -> plan -> execute -> verify.
# - Memory:
#   MigrationState stores shared context across phases for one request.
# - Tools:
#   MigrationClient exposes the actions the workflow can use in each phase.
# - Planning pattern:
#   the app creates a plan before generating migrated code.
# - Verification pattern:
#   the app checks migrated output for remaining gaps before claiming success.

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


Framework = Literal["flask", "fastapi", "express", "hono"]
PhaseName = Literal["analysis", "planning", "execution", "verification"]
StepStatus = Literal["pending", "in_progress", "completed", "failed"]
Complexity = Literal["low", "medium", "high"]
IssueSeverity = Literal["high", "medium", "low"]

SUPPORTED_MIGRATIONS: dict[tuple[str, str], str] = {
    ("flask", "fastapi"): "Python API migration",
    ("express", "hono"): "JavaScript service migration",
}

BASE_DIR = Path(__file__).resolve().parent
LOGGER = logging.getLogger("lab03-migration-workflow")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


class SourceFile(BaseModel):
    path: str = Field(min_length=1, description="Relative file path")
    content: str = Field(min_length=1, description="Source file contents")


class MigrationRequest(BaseModel):
    source_files: list[SourceFile] = Field(min_length=1)
    source_framework: Framework
    target_framework: Framework


class AnalysisRisk(BaseModel):
    severity: IssueSeverity
    area: str
    description: str


class PlanStep(BaseModel):
    id: str
    description: str
    status: StepStatus = "pending"
    dependencies: list[str] = Field(default_factory=list)
    complexity: Complexity = "medium"


class MigratedFile(BaseModel):
    path: str
    content: str
    summary: str


class VerificationIssue(BaseModel):
    severity: IssueSeverity
    file_path: str | None = None
    description: str
    suggestion: str


class VerificationResult(BaseModel):
    passed: bool
    summary: str
    issues: list[VerificationIssue]
    human_review: list[str]


class MigrationResponse(BaseModel):
    success: bool
    phase: PhaseName
    source_framework: Framework
    target_framework: Framework
    analysis_summary: str
    detected_patterns: list[str]
    risks: list[AnalysisRisk]
    plan: list[PlanStep]
    migrated_files: list[MigratedFile]
    verification: VerificationResult
    errors: list[str]
    provider: str


class AnalysisResult(BaseModel):
    summary: str
    detected_patterns: list[str]
    risks: list[AnalysisRisk]


class ExecutionResult(BaseModel):
    migrated_files: list[MigratedFile]


class MigrationState(BaseModel):
    # Module 03 theory: agents keep state across iterations instead of treating
    # every step like a fresh prompt. This shared object is the app's memory.
    # In this lab, memory is short-lived and request-scoped: it exists for one
    # migration run, then is returned in the response instead of being stored long-term.
    phase: PhaseName = "analysis"
    source_framework: Framework
    target_framework: Framework
    source_files: list[SourceFile]
    analysis_summary: str = ""
    detected_patterns: list[str] = Field(default_factory=list)
    risks: list[AnalysisRisk] = Field(default_factory=list)
    plan: list[PlanStep] = Field(default_factory=list)
    migrated_files: list[MigratedFile] = Field(default_factory=list)
    verification: VerificationResult = Field(
        default_factory=lambda: VerificationResult(
            passed=False,
            summary="Verification has not run yet.",
            issues=[],
            human_review=[],
        )
    )
    errors: list[str] = Field(default_factory=list)


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


def normalize_framework(value: str) -> str:
    return value.strip().lower()


def pair_label(source_framework: str, target_framework: str) -> str:
    return f"{source_framework} -> {target_framework}"


def build_phase_system_prompt(phase: PhaseName) -> str:
    phase_goals = {
        "analysis": (
            "understand the source application, identify framework-specific patterns, "
            "and call out migration risks"
        ),
        "planning": (
            "create an ordered migration plan with explicit dependencies and realistic step sizes"
        ),
        "execution": (
            "produce migrated code that preserves behavior while adopting the target framework"
        ),
        "verification": (
            "inspect the migrated output for gaps, unresolved old-framework patterns, and items needing review"
        ),
    }
    return (
        # Module 03 theory: the system prompt defines the agent's role and the
        # current phase. We keep phase behavior explicit so the model does not
        # collapse analysis, planning, execution, and verification into one step.
        "Role: You are a senior software engineer building a code migration workflow agent. "
        "Context: Your output will be rendered directly in a web UI that visualizes agent phases. "
        f"Goal: Perform the {phase} phase and {phase_goals[phase]}. "
        "Rules: Return strict JSON only. Be concrete, use explicit filenames when helpful, "
        "and never include markdown fences or extra prose outside the JSON."
    )


def build_analysis_user_prompt(payload: MigrationRequest) -> str:
    file_sections = "\n\n".join(
        f"File: {source_file.path}\n{source_file.content}" for source_file in payload.source_files
    )
    return (
        f"Phase: analysis\n"
        f"Source framework: {payload.source_framework}\n"
        f"Target framework: {payload.target_framework}\n"
        # Module 03 theory: the analysis phase is the "observe" step in the
        # agent loop. It focuses on understanding the input before planning.
        "Task: Summarize the source application, detect framework-specific patterns, and list migration risks.\n"
        'Output JSON shape: {"summary":"...","detected_patterns":["..."],"risks":[{"severity":"high|medium|low","area":"...","description":"..."}]}\n\n'
        f"Source files:\n{file_sections}"
    )


def build_plan_user_prompt(payload: MigrationRequest, analysis: AnalysisResult) -> str:
    return (
        f"Phase: planning\n"
        f"Source framework: {payload.source_framework}\n"
        f"Target framework: {payload.target_framework}\n"
        f"Analysis summary: {analysis.summary}\n"
        f"Detected patterns: {json.dumps(analysis.detected_patterns)}\n"
        f"Risks: {json.dumps([risk.model_dump() for risk in analysis.risks])}\n"
        # Module 03 theory: planning is the main pattern in this lab. We feed
        # analysis outputs back into the model so the plan is grounded in state.
        "Task: Create a small, explicit migration plan with dependencies and complexity ratings.\n"
        'Output JSON shape: {"plan":[{"id":"step-1","description":"...","status":"pending","dependencies":[],"complexity":"low|medium|high"}]}\n'
        "Use 3 to 6 steps. Do not use vague items like 'migrate everything'."
    )


def build_execution_user_prompt(
    payload: MigrationRequest,
    analysis: AnalysisResult,
    plan: list[PlanStep],
) -> str:
    file_sections = "\n\n".join(
        f"File: {source_file.path}\n{source_file.content}" for source_file in payload.source_files
    )
    return (
        f"Phase: execution\n"
        f"Source framework: {payload.source_framework}\n"
        f"Target framework: {payload.target_framework}\n"
        f"Analysis summary: {analysis.summary}\n"
        f"Plan: {json.dumps([step.model_dump() for step in plan])}\n"
        # Module 03 theory: execution should follow the plan instead of jumping
        # straight from input code to final output with no intermediate control.
        "Task: Produce migrated files that preserve behavior and match the target framework.\n"
        'Output JSON shape: {"migrated_files":[{"path":"...","content":"...","summary":"..."}]}\n'
        "Return full file contents for each migrated file.\n\n"
        f"Source files:\n{file_sections}"
    )


def build_verification_user_prompt(
    payload: MigrationRequest,
    analysis: AnalysisResult,
    plan: list[PlanStep],
    migrated_files: list[MigratedFile],
) -> str:
    migrated_sections = "\n\n".join(
        f"File: {migrated_file.path}\n{migrated_file.content}" for migrated_file in migrated_files
    )
    return (
        f"Phase: verification\n"
        f"Source framework: {payload.source_framework}\n"
        f"Target framework: {payload.target_framework}\n"
        f"Analysis summary: {analysis.summary}\n"
        f"Plan: {json.dumps([step.model_dump() for step in plan])}\n"
        # Module 03 theory: verification keeps the agent honest. This phase is
        # asked to find gaps, not just to praise the generated migration.
        "Task: Verify whether the migrated code matches the target framework and identify missing pieces.\n"
        'Output JSON shape: {"passed":true,"summary":"...","issues":[{"severity":"high|medium|low","file_path":"...","description":"...","suggestion":"..."}],"human_review":["..."]}\n'
        "Call out unresolved imports, incomplete conversions, and assumptions that need human review.\n\n"
        f"Migrated files:\n{migrated_sections}"
    )


def detect_python_patterns(content: str) -> list[str]:
    patterns: list[str] = []
    checks = {
        "Flask app factory or app instance": r"Flask\s*\(",
        "Flask route decorators": r"@app\.route",
        "JSON response helper": r"\bjsonify\s*\(",
        "Request object usage": r"\brequest\.",
        "Run block": r"if __name__ == [\"']__main__[\"']",
    }
    for label, pattern in checks.items():
        if re.search(pattern, content):
            patterns.append(label)
    return patterns


def detect_javascript_patterns(content: str) -> list[str]:
    patterns: list[str] = []
    checks = {
        "Express app instance": r"\bexpress\s*\(",
        "Express route handlers": r"\bapp\.(get|post|put|delete|patch)\s*\(",
        "Express middleware": r"\bapp\.use\s*\(",
        "JSON response helper": r"\bres\.json\s*\(",
        "Server listen block": r"\bapp\.listen\s*\(",
    }
    for label, pattern in checks.items():
        if re.search(pattern, content):
            patterns.append(label)
    return patterns


def convert_flask_file(path: str, content: str) -> MigratedFile:
    updated = content
    updated = re.sub(
        r"from flask import Flask,\s*jsonify",
        "from fastapi import FastAPI",
        updated,
    )
    updated = re.sub(r"from flask import Flask", "from fastapi import FastAPI", updated)
    updated = re.sub(r"from flask import [^\n]*jsonify[^\n]*", "from fastapi import FastAPI", updated)
    updated = updated.replace("app = Flask(__name__)", "app = FastAPI()")
    updated = re.sub(r"@app\.route\(([^,\n]+)\)", r"@app.get(\1)", updated)
    updated = re.sub(r"return jsonify\((.+)\)", r"return \1", updated)
    updated = re.sub(
        r"\nif __name__ == [\"']__main__[\"']:\n(?:[ \t]+.+\n?)+",
        "\n",
        updated,
        flags=re.MULTILINE,
    )
    summary = "Converted Flask imports, app setup, route decorators, and JSON response handling to FastAPI."
    return MigratedFile(path=path, content=updated.strip() + "\n", summary=summary)


def convert_express_file(path: str, content: str) -> MigratedFile:
    updated = content
    updated = re.sub(
        r"const express = require\([\"']express[\"']\);?",
        "import { Hono } from \"hono\";",
        updated,
    )
    updated = re.sub(
        r"import express from [\"']express[\"'];?",
        "import { Hono } from \"hono\";",
        updated,
    )
    updated = updated.replace("const app = express();", "const app = new Hono();")
    updated = updated.replace("const app = express()", "const app = new Hono()")
    updated = re.sub(r"\bapp\.use\s*\(\s*express\.json\(\)\s*\);?\n?", "", updated)
    updated = re.sub(
        r"app\.(get|post|put|delete|patch)\(([^,]+),\s*\((req,\s*res)\)\s*=>\s*\{",
        r'app.\1(\2, (c) => {',
        updated,
    )
    updated = re.sub(r"res\.json\(", "return c.json(", updated)
    updated = re.sub(r"\breq\b", "c.req", updated)
    updated = re.sub(r"\napp\.listen\([^\n]+\);?\n?", "\n", updated)
    summary = "Converted Express app setup and route handlers to Hono patterns."
    return MigratedFile(path=path, content=updated.strip() + "\n", summary=summary)


def heuristic_analysis(payload: MigrationRequest) -> AnalysisResult:
    # This mock path mirrors the theory's analysis phase even without a real LLM.
    # It gives the rest of the workflow structured state to build on.
    detected_patterns: list[str] = []
    risks: list[AnalysisRisk] = []

    for source_file in payload.source_files:
        content = source_file.content
        if payload.source_framework in {"flask", "fastapi"}:
            detected_patterns.extend(detect_python_patterns(content))
            if "request." in content:
                risks.append(
                    AnalysisRisk(
                        severity="medium",
                        area="request-handling",
                        description="Request parsing may need manual updates for FastAPI parameter handling.",
                    )
                )
        if payload.source_framework in {"express", "hono"}:
            detected_patterns.extend(detect_javascript_patterns(content))
            if "app.use(" in content:
                risks.append(
                    AnalysisRisk(
                        severity="medium",
                        area="middleware",
                        description="Middleware behavior may need manual adaptation when moving to Hono.",
                    )
                )
        if re.search(r"async\s+def|async\s+\(", content):
            risks.append(
                AnalysisRisk(
                    severity="medium",
                    area="async-behavior",
                    description="Async behavior should be checked carefully during the migration.",
                )
            )

    if not risks:
        risks.append(
            AnalysisRisk(
                severity="low",
                area="review",
                description="No major structural risks were detected heuristically, but endpoint behavior still needs validation.",
            )
        )

    unique_patterns = sorted(set(detected_patterns))
    summary = (
        f"Reviewed {len(payload.source_files)} source file(s) for a {pair_label(payload.source_framework, payload.target_framework)} migration. "
        f"Detected {len(unique_patterns)} framework-specific pattern(s) and {len(risks)} migration risk(s) to account for."
    )
    return AnalysisResult(summary=summary, detected_patterns=unique_patterns, risks=risks)


def heuristic_plan(payload: MigrationRequest, analysis: AnalysisResult) -> list[PlanStep]:
    # Module 03 theory: plans should be small, ordered, and explicit about
    # dependencies. That is why each step has status and dependency fields.
    shared_steps = [
        PlanStep(
            id="step-1",
            description=f"Inspect {payload.source_framework} entry points, routes, and framework-specific helpers.",
            status="pending",
            dependencies=[],
            complexity="low",
        ),
        PlanStep(
            id="step-2",
            description=f"Replace {payload.source_framework} app setup and imports with {payload.target_framework} equivalents.",
            status="pending",
            dependencies=["step-1"],
            complexity="medium",
        ),
        PlanStep(
            id="step-3",
            description="Convert route handlers and response patterns while preserving behavior.",
            status="pending",
            dependencies=["step-2"],
            complexity="medium",
        ),
        PlanStep(
            id="step-4",
            description="Review migrated output for unresolved old-framework patterns and missing runtime assumptions.",
            status="pending",
            dependencies=["step-3"],
            complexity="medium" if analysis.risks else "low",
        ),
    ]
    return shared_steps


def heuristic_execution(payload: MigrationRequest) -> ExecutionResult:
    # In the theory, agents "act" after reasoning. Here the action is code
    # transformation, represented as migrated files produced from the plan.
    migrated_files: list[MigratedFile] = []
    for source_file in payload.source_files:
        if (payload.source_framework, payload.target_framework) == ("flask", "fastapi"):
            migrated_files.append(convert_flask_file(source_file.path, source_file.content))
        elif (payload.source_framework, payload.target_framework) == ("express", "hono"):
            migrated_files.append(convert_express_file(source_file.path, source_file.content))
        else:
            migrated_files.append(
                MigratedFile(
                    path=source_file.path,
                    content=source_file.content,
                    summary="No heuristic converter exists for this pair, so the source file was preserved.",
                )
            )
    return ExecutionResult(migrated_files=migrated_files)


def heuristic_verification(payload: MigrationRequest, migrated_files: list[MigratedFile]) -> VerificationResult:
    # Module 03 theory: a good verification phase looks for concrete migration
    # gaps such as leftover source-framework code and missing target-framework setup.
    issues: list[VerificationIssue] = []
    human_review: list[str] = []

    for migrated_file in migrated_files:
        content = migrated_file.content
        if payload.target_framework == "fastapi":
            if "FastAPI" not in content:
                issues.append(
                    VerificationIssue(
                        severity="high",
                        file_path=migrated_file.path,
                        description="The migrated file does not appear to instantiate a FastAPI app.",
                        suggestion="Ensure imports and app initialization were converted to FastAPI.",
                    )
                )
            if "from flask import" in content or "jsonify(" in content:
                issues.append(
                    VerificationIssue(
                        severity="high",
                        file_path=migrated_file.path,
                        description="Flask-specific imports or helpers remain in the migrated output.",
                        suggestion="Remove remaining Flask references and use plain dict responses or FastAPI helpers.",
                    )
                )
        if payload.target_framework == "hono":
            if "new Hono()" not in content:
                issues.append(
                    VerificationIssue(
                        severity="high",
                        file_path=migrated_file.path,
                        description="The migrated file does not appear to create a Hono app instance.",
                        suggestion="Replace the Express app constructor with Hono initialization.",
                    )
                )
            if "express" in content or "res.json(" in content:
                issues.append(
                    VerificationIssue(
                        severity="high",
                        file_path=migrated_file.path,
                        description="Express-specific patterns remain in the migrated output.",
                        suggestion="Replace remaining Express middleware or response helpers with Hono equivalents.",
                    )
                )
        if "TODO" in content:
            issues.append(
                VerificationIssue(
                    severity="medium",
                    file_path=migrated_file.path,
                    description="The migrated file still contains TODO markers.",
                    suggestion="Finish the incomplete sections before deploying the migration.",
                )
            )

    if payload.source_framework == "flask":
        human_review.append("Confirm request body parsing and dependency injection semantics in FastAPI handlers.")
    if payload.source_framework == "express":
        human_review.append("Validate middleware ordering and request parsing behavior after the Hono conversion.")
    human_review.append("Run the migrated app locally and add or update route-level tests before shipping.")

    passed = not any(issue.severity == "high" for issue in issues)
    summary = (
        "The migrated output structurally matches the target framework."
        if passed
        else "The migrated output still has framework-specific issues that need manual fixes."
    )
    return VerificationResult(passed=passed, summary=summary, issues=issues, human_review=human_review)


class MigrationClient(ABC):
    # Module 03 theory: tool-use can stay simple. This abstraction lets the
    # agent use different providers or a mock engine behind the same workflow.
    # A good study shortcut:
    # - analyze = observe the input
    # - plan = reason about next steps
    # - execute = act on the code
    # - verify = check whether the action actually worked
    # These methods are the "tools" used by the workflow, even though the model
    # is not choosing them dynamically through function-calling in this version.
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def analyze(self, payload: MigrationRequest) -> AnalysisResult:
        raise NotImplementedError

    @abstractmethod
    def plan(self, payload: MigrationRequest, analysis: AnalysisResult) -> list[PlanStep]:
        raise NotImplementedError

    @abstractmethod
    def execute(self, payload: MigrationRequest, analysis: AnalysisResult, plan: list[PlanStep]) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def verify(
        self,
        payload: MigrationRequest,
        analysis: AnalysisResult,
        plan: list[PlanStep],
        migrated_files: list[MigratedFile],
    ) -> VerificationResult:
        raise NotImplementedError


class MockMigrationClient(MigrationClient):
    # Local fallback so the workflow still behaves like an agent even before
    # wiring a real model. Helpful for demos, testing, and UI development.
    # This also makes the tool pattern easier to study because each tool maps to
    # a plain Python function with deterministic output.
    @property
    def provider_name(self) -> str:
        return "mock"

    def analyze(self, payload: MigrationRequest) -> AnalysisResult:
        return heuristic_analysis(payload)

    def plan(self, payload: MigrationRequest, analysis: AnalysisResult) -> list[PlanStep]:
        return heuristic_plan(payload, analysis)

    def execute(self, payload: MigrationRequest, analysis: AnalysisResult, plan: list[PlanStep]) -> ExecutionResult:
        return heuristic_execution(payload)

    def verify(
        self,
        payload: MigrationRequest,
        analysis: AnalysisResult,
        plan: list[PlanStep],
        migrated_files: list[MigratedFile],
    ) -> VerificationResult:
        return heuristic_verification(payload, migrated_files)


class OpenAICompatibleMigrationClient(MigrationClient):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    @property
    def provider_name(self) -> str:
        return f"openai-compatible:{self.model}"

    def _complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        # Module 03 theory: structured outputs matter. We force JSON so each
        # phase can pass reliable state into the next phase and into the UI.
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
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
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="LLM response was not valid JSON.") from exc

    def analyze(self, payload: MigrationRequest) -> AnalysisResult:
        parsed = self._complete_json(
            build_phase_system_prompt("analysis"),
            build_analysis_user_prompt(payload),
        )
        return AnalysisResult(**parsed)

    def plan(self, payload: MigrationRequest, analysis: AnalysisResult) -> list[PlanStep]:
        parsed = self._complete_json(
            build_phase_system_prompt("planning"),
            build_plan_user_prompt(payload, analysis),
        )
        try:
            return [PlanStep(**step) for step in parsed["plan"]]
        except KeyError as exc:
            raise HTTPException(status_code=502, detail=f"LLM response missed field: {exc.args[0]}") from exc

    def execute(self, payload: MigrationRequest, analysis: AnalysisResult, plan: list[PlanStep]) -> ExecutionResult:
        parsed = self._complete_json(
            build_phase_system_prompt("execution"),
            build_execution_user_prompt(payload, analysis, plan),
        )
        try:
            migrated_files = [MigratedFile(**item) for item in parsed["migrated_files"]]
        except KeyError as exc:
            raise HTTPException(status_code=502, detail=f"LLM response missed field: {exc.args[0]}") from exc
        return ExecutionResult(migrated_files=migrated_files)

    def verify(
        self,
        payload: MigrationRequest,
        analysis: AnalysisResult,
        plan: list[PlanStep],
        migrated_files: list[MigratedFile],
    ) -> VerificationResult:
        parsed = self._complete_json(
            build_phase_system_prompt("verification"),
            build_verification_user_prompt(payload, analysis, plan, migrated_files),
        )
        return VerificationResult(**parsed)


class GeminiMigrationClient(MigrationClient):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return f"gemini:{self.model}"

    def _complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        # Same theory as the OpenAI-compatible path: phase-specific prompting
        # plus strict JSON makes the agent workflow predictable and inspectable.
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
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
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
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
            LOGGER.error("Gemini provider URLError url=%s reason=%s", url, exc.reason)
            raise HTTPException(status_code=502, detail=f"Could not reach Gemini provider: {exc.reason}") from exc

        try:
            content = raw["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="Gemini response did not include text content.") from exc

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="Gemini response was not valid JSON.") from exc

    def analyze(self, payload: MigrationRequest) -> AnalysisResult:
        parsed = self._complete_json(
            build_phase_system_prompt("analysis"),
            build_analysis_user_prompt(payload),
        )
        return AnalysisResult(**parsed)

    def plan(self, payload: MigrationRequest, analysis: AnalysisResult) -> list[PlanStep]:
        parsed = self._complete_json(
            build_phase_system_prompt("planning"),
            build_plan_user_prompt(payload, analysis),
        )
        try:
            return [PlanStep(**step) for step in parsed["plan"]]
        except KeyError as exc:
            raise HTTPException(status_code=502, detail=f"Gemini response missed field: {exc.args[0]}") from exc

    def execute(self, payload: MigrationRequest, analysis: AnalysisResult, plan: list[PlanStep]) -> ExecutionResult:
        parsed = self._complete_json(
            build_phase_system_prompt("execution"),
            build_execution_user_prompt(payload, analysis, plan),
        )
        try:
            migrated_files = [MigratedFile(**item) for item in parsed["migrated_files"]]
        except KeyError as exc:
            raise HTTPException(status_code=502, detail=f"Gemini response missed field: {exc.args[0]}") from exc
        return ExecutionResult(migrated_files=migrated_files)

    def verify(
        self,
        payload: MigrationRequest,
        analysis: AnalysisResult,
        plan: list[PlanStep],
        migrated_files: list[MigratedFile],
    ) -> VerificationResult:
        parsed = self._complete_json(
            build_phase_system_prompt("verification"),
            build_verification_user_prompt(payload, analysis, plan, migrated_files),
        )
        return VerificationResult(**parsed)


def get_migration_client() -> MigrationClient:
    # The workflow asks for one tool provider up front, then uses the same tool
    # interface for every phase. This keeps orchestration separate from provider details.
    provider = os.getenv("MIGRATION_PROVIDER", "").strip().lower()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

    if provider == "openai":
        if not openai_api_key:
            raise HTTPException(
                status_code=500,
                detail="MIGRATION_PROVIDER is set to 'openai' but OPENAI_API_KEY is missing.",
            )
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        return OpenAICompatibleMigrationClient(api_key=openai_api_key, model=model, base_url=base_url)

    if provider == "gemini":
        if not gemini_api_key:
            raise HTTPException(
                status_code=500,
                detail="MIGRATION_PROVIDER is set to 'gemini' but GEMINI_API_KEY is missing.",
            )
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip()
        return GeminiMigrationClient(api_key=gemini_api_key, model=model, base_url=base_url)

    if provider == "groq":
        if not groq_api_key:
            raise HTTPException(
                status_code=500,
                detail="MIGRATION_PROVIDER is set to 'groq' but GROQ_API_KEY is missing.",
            )
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
        return OpenAICompatibleMigrationClient(api_key=groq_api_key, model=model, base_url=base_url)

    if provider in {"", "mock"}:
        return MockMigrationClient()

    raise HTTPException(
        status_code=500,
        detail="Unsupported MIGRATION_PROVIDER. Use 'mock', 'groq', 'gemini', or 'openai'.",
    )


def validate_request(payload: MigrationRequest) -> MigrationRequest:
    # Guardrails matter for agent systems too. Validating the migration pair up
    # front keeps the workflow constrained to supported, debuggable scenarios.
    source_framework = normalize_framework(payload.source_framework)
    target_framework = normalize_framework(payload.target_framework)

    if source_framework == target_framework:
        raise HTTPException(status_code=400, detail="Source and target frameworks must be different.")

    if (source_framework, target_framework) not in SUPPORTED_MIGRATIONS:
        supported_pairs = ", ".join(pair_label(source, target) for source, target in SUPPORTED_MIGRATIONS)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported migration pair '{pair_label(source_framework, target_framework)}'. Supported pairs: {supported_pairs}",
        )

    normalized_files = [
        SourceFile(path=source_file.path.strip(), content=source_file.content.strip())
        for source_file in payload.source_files
        if source_file.path.strip() and source_file.content.strip()
    ]
    if not normalized_files:
        raise HTTPException(status_code=400, detail="At least one non-empty source file is required.")

    return MigrationRequest(
        source_files=normalized_files,
        source_framework=source_framework,
        target_framework=target_framework,
    )


def mark_all_steps(plan: list[PlanStep], status: StepStatus) -> list[PlanStep]:
    return [step.model_copy(update={"status": status}) for step in plan]


app = FastAPI(title="Lab 03 Migration Workflow", version="0.1.0")
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
        "service": "lab03-migration-workflow-backend",
        "endpoints": ["/api/migrate", "/health"],
        "supported_pairs": [pair_label(source, target) for source, target in SUPPORTED_MIGRATIONS],
    }


@app.get("/health")
def health() -> dict[str, object]:
    provider = os.getenv("MIGRATION_PROVIDER", "mock") or "mock"
    model_env_map = {
        "openai": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "groq": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        "mock": "mock",
    }
    return {
        "status": "ok",
        "provider": provider,
        "model": model_env_map.get(provider, "unknown"),
        "supported_pairs": [pair_label(source, target) for source, target in SUPPORTED_MIGRATIONS],
    }


@app.post("/api/migrate", response_model=MigrationResponse)
def migrate(payload: MigrationRequest) -> MigrationResponse:
    # Module 03 theory in one function: this is the explicit agent loop for the
    # lab. We move through analysis -> planning -> execution -> verification
    # while updating shared state after each phase.
    normalized = validate_request(payload)
    state = MigrationState(
        source_framework=normalized.source_framework,
        target_framework=normalized.target_framework,
        source_files=normalized.source_files,
    )
    client = get_migration_client()

    try:
        state.phase = "analysis"
        analysis = client.analyze(normalized)
        # Memory handoff: analysis results are stored in state so the next phases
        # do not need to rediscover the same context from scratch.
        state.analysis_summary = analysis.summary
        state.detected_patterns = analysis.detected_patterns
        state.risks = analysis.risks

        state.phase = "planning"
        # Tool use: the planning tool reads the remembered analysis context and
        # turns it into ordered executable steps.
        state.plan = client.plan(normalized, analysis)

        state.phase = "execution"
        # Step statuses make the plan visible to both the frontend and the user,
        # which is one of the key lab requirements from the theory.
        state.plan = mark_all_steps(state.plan, "in_progress")
        # Tool use: the execution tool acts on the code while following the plan.
        execution = client.execute(normalized, analysis, state.plan)
        # Memory handoff again: generated files are saved so verification can
        # inspect the exact output that execution produced.
        state.migrated_files = execution.migrated_files
        state.plan = mark_all_steps(state.plan, "completed")

        state.phase = "verification"
        # Final tool: verification checks the generated output against the target
        # framework and records issues instead of blindly declaring success.
        state.verification = client.verify(normalized, analysis, state.plan, state.migrated_files)
    except HTTPException as exc:
        LOGGER.warning("Migration workflow failed during phase=%s detail=%s", state.phase, exc.detail)
        state.errors.append(str(exc.detail))
        if state.phase == "execution" and state.plan:
            state.plan = mark_all_steps(state.plan, "failed")
    except Exception as exc:  # pragma: no cover - defensive fallback
        LOGGER.exception("Unexpected migration workflow failure")
        state.errors.append(str(exc))
        if state.phase == "execution" and state.plan:
            state.plan = mark_all_steps(state.plan, "failed")

    success = not state.errors and state.verification.passed
    if not success and not state.errors and not state.verification.passed:
        state.errors.append("Verification found issues that still require manual fixes.")

    return MigrationResponse(
        success=success,
        phase=state.phase,
        source_framework=state.source_framework,
        target_framework=state.target_framework,
        analysis_summary=state.analysis_summary,
        detected_patterns=state.detected_patterns,
        risks=state.risks,
        plan=state.plan,
        migrated_files=state.migrated_files,
        verification=state.verification,
        errors=state.errors,
        provider=client.provider_name,
    )
