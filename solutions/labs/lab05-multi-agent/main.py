#!/usr/bin/env python3
"""Render-ready backend for the Lab 05 multi-agent orchestration lab.

This file implements the backend for the Lab 05 exercise from Module 5, where
the goal is to build a small but complete multi-agent system using the
supervisor pattern.

What the app does:
- accepts a user task through `POST /run`
- creates a request-scoped workflow state object
- routes the task through a team of specialized workers
- records an activity trace of every delegation and result
- returns both the final answer and the intermediate artifacts

The worker team in this implementation:
- `Researcher`: gathers and structures the core points for the task
- `Writer`: turns research into a polished user-facing answer
- `Reviewer`: checks quality, clarity, and completeness, then either approves
  the draft or asks for a focused revision

How this maps to the Module 5 theory:

1. Supervisor Pattern
   The supervisor does not try to do all the work itself. Instead, it reads the
   current workflow state and decides which specialist should act next. This is
   the core orchestration idea of the lab.

2. Worker Specialization
   Each worker has a narrow responsibility. The point is not to create many
   agents for show, but to make handoffs clearer and outputs more reliable than
   one monolithic prompt would be.

3. Structured Handoffs
   Workers return explicit JSON shapes such as research summaries, drafts, and
   review feedback. This mirrors the theory idea that multi-agent systems work
   better when communication contracts are predictable.

4. Shared State
   The `WorkflowState` model is the short-term memory of the orchestration. It
   stores the task, iteration count, worker outputs, final answer, trace, and
   errors so the supervisor can make informed next-step decisions.

5. Iteration Limits
   The workflow always respects `max_iterations`. This is an important
   production concern from Module 5: the system must have a stopping rule so it
   does not loop forever or spend tokens on low-value refinements.

6. Review Loop
   The reviewer acts as a lightweight quality gate. If the draft is not good
   enough, the supervisor turns the review feedback into a focused revision pass
   for the writer. That demonstrates how orchestration can improve quality
   without making the architecture overly complex.

7. Observability
   The API intentionally returns `activity_log`, worker outputs, and final
   output together. In the theory, inspectability is part of a production-ready
   AI system because it helps with demos, debugging, and trust.

8. Provider Abstraction
   The orchestration logic is separated from the model provider. This file
   supports:
   - `mock` mode for local development and tests
   - `groq` mode for real model-backed worker execution

What this file is meant to teach:
- how to coordinate multiple agents without overengineering
- how to keep orchestration logic explicit and easy to inspect
- how to connect theory concepts like supervisor routing, state, limits, and
  traceability to working code

If you come back to this file later, read it in this order:
1. `RunRequest`, `WorkflowState`, and `RunResponse`
2. prompt builders for each worker
3. `AgentBackend` plus `MockAgentBackend` and `GroqAgentBackend`
4. `MultiAgentService.run()` which contains the actual supervisor loop
5. FastAPI routes at the bottom
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from openai import APIConnectionError as OpenAIAPIConnectionError
from openai import APIStatusError as OpenAIAPIStatusError
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
LOGGER = logging.getLogger("lab05-multi-agent")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


class RunRequest(BaseModel):
    task: str = Field(min_length=8, description="The user task for the multi-agent system")
    max_iterations: int = Field(default=5, ge=3, le=8)


class ResearchResult(BaseModel):
    summary: str
    key_points: list[str]
    sources: list[str]
    open_questions: list[str]


class WriterResult(BaseModel):
    title: str
    draft: str
    format_notes: list[str]


class ReviewResult(BaseModel):
    approved: bool
    score: int = Field(ge=1, le=10)
    strengths: list[str]
    issues: list[str]
    revision_brief: str


class TraceEntry(BaseModel):
    step: int
    actor: str
    event: str
    detail: str
    payload: dict[str, object] = Field(default_factory=dict)


class WorkflowState(BaseModel):
    # Module 05 theory: orchestration only feels reliable when the supervisor
    # has explicit shared state instead of reconstructing context from scratch
    # on every worker call.
    task: str
    max_iterations: int
    iteration_count: int = 0
    status: str = "running"
    research_result: ResearchResult | None = None
    writer_result: WriterResult | None = None
    review_result: ReviewResult | None = None
    final_output: str | None = None
    activity_log: list[TraceEntry] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class RunResponse(BaseModel):
    # The response intentionally exposes intermediate artifacts so the system is
    # inspectable. In Module 05, observability is part of the product.
    success: bool
    status: str
    provider: str
    iteration_count: int
    max_iterations: int
    workers_used: list[str]
    research_result: ResearchResult | None
    writer_result: WriterResult | None
    review_result: ReviewResult | None
    final_output: str
    activity_log: list[TraceEntry]
    errors: list[str]


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


def build_supervisor_digest(state: WorkflowState) -> str:
    # The supervisor does not perform specialist work itself. It keeps a compact
    # digest of what has happened so far, then uses that to route the next step.
    parts = [f"Task: {state.task}", f"Iteration: {state.iteration_count}/{state.max_iterations}"]
    if state.research_result:
        parts.append(f"Research summary: {state.research_result.summary}")
        parts.append("Key points: " + "; ".join(state.research_result.key_points))
    if state.writer_result:
        parts.append(f"Current draft title: {state.writer_result.title}")
    if state.review_result:
        parts.append(f"Latest review score: {state.review_result.score}/10")
        parts.append(f"Revision brief: {state.review_result.revision_brief}")
    return "\n".join(parts)


def build_research_prompt(task: str) -> str:
    return (
        "You are the Researcher worker in a multi-agent system.\n"
        "Goal: gather the strongest factual framing for the task.\n"
        "Rules:\n"
        "- do not write the final polished answer\n"
        "- produce concrete points instead of generic filler\n"
        "- return strict JSON only\n\n"
        f"Task:\n{task}\n\n"
        'Return JSON with this shape: {"summary":"...","key_points":["..."],"sources":["..."],"open_questions":["..."]}'
    )


def build_writer_prompt(task: str, research: ResearchResult, review: ReviewResult | None) -> str:
    # Module 05 theory: workers should receive only the context they need for
    # their role. The writer gets research plus focused review feedback, not the
    # entire raw workflow history.
    review_context = ""
    if review and review.issues:
        review_context = (
            "\nRevision requirements from Reviewer:\n"
            f"- score: {review.score}/10\n"
            f"- issues: {'; '.join(review.issues)}\n"
            f"- revision brief: {review.revision_brief}\n"
        )

    return (
        "You are the Writer worker in a multi-agent system.\n"
        "Goal: turn the research into a polished answer for the user.\n"
        "Rules:\n"
        "- use the research provided\n"
        "- organize the answer clearly\n"
        "- do not invent unsupported facts\n"
        "- return strict JSON only\n\n"
        f"Task:\n{task}\n\n"
        f"Research summary:\n{research.summary}\n\n"
        "Key points:\n- "
        + "\n- ".join(research.key_points)
        + "\n\n"
        + ("Open questions:\n- " + "\n- ".join(research.open_questions) + "\n" if research.open_questions else "")
        + review_context
        + '\nReturn JSON with this shape: {"title":"...","draft":"...","format_notes":["..."]}'
    )


def build_reviewer_prompt(task: str, research: ResearchResult, writer: WriterResult) -> str:
    return (
        "You are the Reviewer worker in a multi-agent system.\n"
        "Goal: decide if the draft is ready and identify the highest-value fixes.\n"
        "Rules:\n"
        "- do not rewrite the whole answer\n"
        "- focus on clarity, completeness, and grounding\n"
        "- return strict JSON only\n\n"
        f"Task:\n{task}\n\n"
        f"Research summary:\n{research.summary}\n\n"
        "Research key points:\n- "
        + "\n- ".join(research.key_points)
        + "\n\n"
        f"Draft title: {writer.title}\n\nDraft:\n{writer.draft}\n\n"
        '{"approved":true,"score":8,"strengths":["..."],"issues":["..."],"revision_brief":"..."}'
    )


class AgentBackend(ABC):
    name: str

    # The backend interface keeps worker roles stable even if the provider
    # changes. That mirrors the production idea of separating orchestration from
    # model vendor details.
    @abstractmethod
    def research(self, task: str) -> ResearchResult:
        raise NotImplementedError

    @abstractmethod
    def write(
        self,
        task: str,
        research: ResearchResult,
        review: ReviewResult | None,
    ) -> WriterResult:
        raise NotImplementedError

    @abstractmethod
    def review(self, task: str, research: ResearchResult, writer: WriterResult) -> ReviewResult:
        raise NotImplementedError


class MockAgentBackend(AgentBackend):
    name = "mock"

    def research(self, task: str) -> ResearchResult:
        # This mock path preserves the orchestration architecture for local
        # development, even when no external model is available.
        compact_task = task.strip().rstrip(".")
        key_points = [
            "Break the task into understandable sections so each worker adds a clear value.",
            "Use concrete explanations, not abstract claims, so the final answer feels useful.",
            "Preserve any important tradeoffs, risks, or constraints mentioned in the task.",
        ]
        if "compare" in compact_task.lower():
            key_points.append("Highlight where the compared options differ in control, speed, and reliability.")

        return ResearchResult(
            summary=f"Research gathered for: {compact_task}. Focus on practical explanation, structure, and tradeoffs.",
            key_points=key_points,
            sources=[
                "Internal mock research summary",
                "Structured reasoning based on the task wording",
            ],
            open_questions=[],
        )

    def write(
        self,
        task: str,
        research: ResearchResult,
        review: ReviewResult | None,
    ) -> WriterResult:
        title = "Coordinated Research Brief"
        revision_line = ""
        if review and review.issues:
            revision_line = f"\n## Revision Pass\nClarity upgrade applied: {review.revision_brief}\n"

        draft = (
            f"# {title}\n\n"
            "## Task\n"
            f"{task.strip()}\n\n"
            "## What Matters Most\n"
            + "\n".join(f"- {point}" for point in research.key_points)
            + "\n\n## Recommended Answer\n"
            f"{research.summary}\n"
            "The best response here is one that explains the topic directly, surfaces the main tradeoffs, "
            "and keeps the structure easy to scan for a busy reader.\n"
            f"{revision_line}\n"
            "## Sources Used\n"
            + "\n".join(f"- {source}" for source in research.sources)
        )
        return WriterResult(
            title=title,
            draft=draft.strip(),
            format_notes=[
                "Uses headings so the frontend can render a readable final answer.",
                "Keeps the answer grounded in the research summary and key points.",
            ],
        )

    def review(self, task: str, research: ResearchResult, writer: WriterResult) -> ReviewResult:
        revised = "Clarity upgrade applied" in writer.draft
        if revised:
            return ReviewResult(
                approved=True,
                score=9,
                strengths=[
                    "The draft is clearly structured.",
                    "The answer stays aligned with the research points.",
                ],
                issues=[],
                revision_brief="No further revision needed.",
            )

        return ReviewResult(
            approved=False,
            score=7,
            strengths=[
                "The draft has useful structure.",
                "The core task is addressed.",
            ],
            issues=[
                "Add a clearer statement of the final recommendation.",
                "Make the practical takeaway easier to spot.",
            ],
            revision_brief="Add a sharper takeaway section and make the recommendation more explicit.",
        )


class GroqAgentBackend(AgentBackend):
    name = "groq"

    def __init__(self) -> None:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required when ORCHESTRATOR_PROVIDER=groq.")

        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    def _complete_json(self, prompt: str) -> dict[str, object]:
        # Structured JSON output is doing real architectural work here: it makes
        # worker handoffs predictable and reduces fragile text parsing.
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a reliable worker inside a multi-agent application. "
                            "Return strict JSON only. No markdown fences."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except OpenAIAPIConnectionError as exc:
            raise RuntimeError(f"Could not reach Groq: {exc}") from exc
        except OpenAIAPIStatusError as exc:
            raise RuntimeError(f"Groq returned an API error: {exc}") from exc

        content = response.choices[0].message.content or "{}"
        return extract_json_object(content)

    def research(self, task: str) -> ResearchResult:
        payload = self._complete_json(build_research_prompt(task))
        return ResearchResult.model_validate(payload)

    def write(
        self,
        task: str,
        research: ResearchResult,
        review: ReviewResult | None,
    ) -> WriterResult:
        payload = self._complete_json(build_writer_prompt(task, research, review))
        return WriterResult.model_validate(payload)

    def review(self, task: str, research: ResearchResult, writer: WriterResult) -> ReviewResult:
        payload = self._complete_json(build_reviewer_prompt(task, research, writer))
        return ReviewResult.model_validate(payload)


def build_backend() -> AgentBackend:
    provider = normalize_provider_name(os.getenv("ORCHESTRATOR_PROVIDER", "mock"))
    if provider == "groq":
        try:
            return GroqAgentBackend()
        except RuntimeError as exc:
            LOGGER.warning("Groq backend unavailable, falling back to mock: %s", exc)
            return MockAgentBackend()
    return MockAgentBackend()


class MultiAgentService:
    def __init__(self, backend: AgentBackend) -> None:
        self.backend = backend

    def _log(
        self,
        state: WorkflowState,
        actor: str,
        event: str,
        detail: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        # Module 05 theory: if you cannot inspect agent decisions, debugging and
        # demos become much harder. The trace gives us an explicit audit trail.
        state.activity_log.append(
            TraceEntry(
                step=len(state.activity_log) + 1,
                actor=actor,
                event=event,
                detail=detail,
                payload=payload or {},
            )
        )

    def _finalize(self, state: WorkflowState) -> None:
        # Production mindset: even if the workflow stops early, return the best
        # available artifact instead of failing silently and losing progress.
        if state.writer_result:
            review_note = ""
            if state.review_result and not state.review_result.approved:
                review_note = (
                    "\n\n## Supervisor Note\n"
                    "The iteration limit was reached before the reviewer fully approved the draft. "
                    "The latest revision is returned below so progress is not lost."
                )
            state.final_output = state.writer_result.draft + review_note
        elif state.research_result:
            state.final_output = (
                "# Research Snapshot\n\n"
                f"{state.research_result.summary}\n\n"
                "## Key Points\n"
                + "\n".join(f"- {item}" for item in state.research_result.key_points)
            )
        else:
            state.final_output = "No final output could be generated."

    def run(self, payload: RunRequest) -> RunResponse:
        state = WorkflowState(task=payload.task.strip(), max_iterations=payload.max_iterations)
        self._log(
            state,
            actor="supervisor",
            event="received_task",
            detail="Supervisor accepted the task and initialized workflow state.",
            payload={"task": state.task, "max_iterations": state.max_iterations},
        )

        # This loop is the heart of the supervisor pattern:
        # - inspect current state
        # - choose the next worker
        # - update shared state
        # - stop when approved or out of iterations
        while state.iteration_count < state.max_iterations:
            if state.research_result is None:
                self._log(
                    state,
                    actor="supervisor",
                    event="delegate",
                    detail="Delegating to Researcher to gather context and key points.",
                    payload={"worker": "researcher", "digest": build_supervisor_digest(state)},
                )
                # Supervisor delegates to a specialist instead of trying to do
                # the research itself. That is the key orchestration idea.
                state.iteration_count += 1
                state.research_result = self.backend.research(state.task)
                self._log(
                    state,
                    actor="researcher",
                    event="result",
                    detail="Researcher returned summary, key points, sources, and open questions.",
                    payload=state.research_result.model_dump(),
                )
                continue

            if state.writer_result is None:
                self._log(
                    state,
                    actor="supervisor",
                    event="delegate",
                    detail="Delegating to Writer to turn the research into a polished draft.",
                    payload={"worker": "writer", "digest": build_supervisor_digest(state)},
                )
                # The writer consumes structured research output, which is a
                # cleaner handoff than passing one huge free-form transcript.
                state.iteration_count += 1
                state.writer_result = self.backend.write(state.task, state.research_result, state.review_result)
                self._log(
                    state,
                    actor="writer",
                    event="result",
                    detail="Writer returned a polished draft.",
                    payload=state.writer_result.model_dump(),
                )
                continue

            if state.review_result is None:
                self._log(
                    state,
                    actor="supervisor",
                    event="delegate",
                    detail="Delegating to Reviewer for quality control and revision guidance.",
                    payload={"worker": "reviewer", "digest": build_supervisor_digest(state)},
                )
                # Reviewer acts as the quality gate. This is one of the main
                # reasons multi-agent can outperform a single monolithic prompt.
                state.iteration_count += 1
                state.review_result = self.backend.review(
                    state.task,
                    state.research_result,
                    state.writer_result,
                )
                self._log(
                    state,
                    actor="reviewer",
                    event="result",
                    detail="Reviewer scored the draft and returned approval status.",
                    payload=state.review_result.model_dump(),
                )
                if state.review_result.approved:
                    state.status = "completed"
                    break
                continue

            if not state.review_result.approved:
                if state.iteration_count >= state.max_iterations:
                    break

                self._log(
                    state,
                    actor="supervisor",
                    event="revise",
                    detail="Reviewer requested changes. Sending the revision brief back to Writer.",
                    payload={"revision_brief": state.review_result.revision_brief},
                )
                # Instead of looping blindly, the supervisor converts review
                # feedback into a focused revision pass for the writer.
                state.writer_result = None
                state.review_result = None
                continue

            state.status = "completed"
            break

        if state.status != "completed":
            state.status = "max_iterations_reached"
            self._log(
                state,
                actor="supervisor",
                event="forced_completion",
                detail="Iteration limit reached. Returning the best available output.",
                payload={"iteration_count": state.iteration_count},
            )
        else:
            self._log(
                state,
                actor="supervisor",
                event="finalize",
                detail="Workflow completed with reviewer approval.",
                payload={"iteration_count": state.iteration_count},
            )

        self._finalize(state)
        workers_used = []
        if state.research_result:
            workers_used.append("researcher")
        if state.writer_result:
            workers_used.append("writer")
        if state.review_result:
            workers_used.append("reviewer")

        return RunResponse(
            success=bool(state.final_output),
            status=state.status,
            provider=self.backend.name,
            iteration_count=state.iteration_count,
            max_iterations=state.max_iterations,
            workers_used=workers_used,
            research_result=state.research_result,
            writer_result=state.writer_result,
            review_result=state.review_result,
            final_output=state.final_output or "No final output could be generated.",
            activity_log=state.activity_log,
            errors=state.errors,
        )


app = FastAPI(title="Lab 05 Multi-Agent Orchestration")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

multi_agent_service = MultiAgentService(build_backend())


@app.get("/")
def root() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "lab05-multi-agent",
        "provider": multi_agent_service.backend.name,
        "available_endpoints": [
            "GET /health",
            "POST /run",
            "POST /api/run",
        ],
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "lab05-multi-agent",
        "provider": multi_agent_service.backend.name,
    }


@app.post("/run", response_model=RunResponse)
@app.post("/api/run", response_model=RunResponse)
def run_workflow(payload: RunRequest) -> RunResponse:
    try:
        # The HTTP layer stays thin. Most of the theory-relevant behavior lives
        # inside the orchestration service rather than inside route handlers.
        return multi_agent_service.run(payload)
    except (RuntimeError, ValueError) as exc:
        LOGGER.exception("Workflow failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
