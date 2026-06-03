#!/usr/bin/env python3
"""Render-ready backend starter for the Lab 04 RAG system with evaluation."""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import math
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


LanguageName = Literal[
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "ruby",
    "csharp",
    "cpp",
    "unknown",
]
ChunkType = Literal["module", "function", "class", "generic"]
JudgeDimension = Literal["relevance", "faithfulness", "correctness"]

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
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "by",
    "does",
    "for",
    "in",
    "into",
    "is",
    "of",
    "the",
    "to",
    "where",
    "which",
}
EMBEDDING_DIMENSIONS = 128
DEFAULT_TOP_K = 4

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "rag_index.json"
DEFAULT_DATASET_PATH = BASE_DIR / "evaluation_dataset.json"
LOGGER = logging.getLogger("lab04-rag-system")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())


class SourceFile(BaseModel):
    path: str = Field(min_length=1, description="Relative file path")
    content: str = Field(min_length=1, description="Source file contents")


class ChunkMetadata(BaseModel):
    file_path: str
    language: LanguageName
    chunk_type: ChunkType
    symbol_name: str | None = None
    line_start: int
    line_end: int
    chunk_index: int


class IndexedChunk(BaseModel):
    id: str
    content: str
    metadata: ChunkMetadata
    embedding: list[float]


class SourceSnippet(BaseModel):
    id: str
    file_path: str
    language: LanguageName
    chunk_type: ChunkType
    symbol_name: str | None = None
    line_start: int
    line_end: int
    score: float
    snippet: str


class RetrievalMetrics(BaseModel):
    precision_at_k: float
    recall_at_k: float
    mrr: float


class JudgeScore(BaseModel):
    dimension: JudgeDimension
    rating: int
    explanation: str


class EvalExample(BaseModel):
    id: str
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    relevant_docs: list[str] = Field(min_length=1)


class EvalExampleResult(BaseModel):
    id: str
    question: str
    expected_answer: str
    generated_answer: str
    retrieved_doc_ids: list[str]
    relevant_doc_ids: list[str]
    metrics: RetrievalMetrics
    judge_scores: list[JudgeScore]
    sources: list[SourceSnippet]


class EvaluationSummary(BaseModel):
    example_count: int
    avg_precision_at_k: float
    avg_recall_at_k: float
    avg_mrr: float
    avg_relevance: float
    avg_faithfulness: float
    avg_correctness: float


class IndexFilesRequest(BaseModel):
    files: list[SourceFile] = Field(min_length=1)


class IndexFilesResponse(BaseModel):
    indexed_files: int
    chunk_count: int
    languages: list[str]
    provider: str
    chunking_strategy: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=8)


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceSnippet]
    indexed_chunks: int
    provider: str
    top_k: int


class EvaluateRequest(BaseModel):
    examples: list[EvalExample] = Field(default_factory=list)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=8)


class EvaluateResponse(BaseModel):
    summary: EvaluationSummary
    examples: list[EvalExampleResult]
    provider: str
    dataset_name: str


class StoredIndex(BaseModel):
    chunks: list[IndexedChunk] = Field(default_factory=list)


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


def detect_language(path: str) -> LanguageName:
    suffix = Path(path).suffix.lower()
    mapping: dict[str, LanguageName] = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".h": "cpp",
    }
    return mapping.get(suffix, "unknown")


def make_chunk_id(
    file_path: str,
    chunk_type: ChunkType,
    symbol_name: str | None,
    line_start: int,
) -> str:
    symbol = symbol_name or "module"
    return f"{file_path}::{chunk_type}::{symbol}::{line_start}"


def get_node_source(code: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(code, node)
    if segment:
        return segment
    lines = code.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", start + 1)
    return "\n".join(lines[start:end])


def chunk_python_file(source_file: SourceFile) -> list[tuple[ChunkMetadata, str]]:
    code = source_file.content
    lines = code.splitlines()
    chunks: list[tuple[ChunkMetadata, str]] = []

    try:
        # Module 4 theory: for code, chunk by logical units instead of fixed
        # character windows. AST parsing gives us functions and classes directly.
        tree = ast.parse(code)
    except SyntaxError:
        # If the file is incomplete or invalid Python, we still want a usable
        # index, so we fall back to the generic chunker instead of failing hard.
        return chunk_generic_file(source_file, "python")

    structured_nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    covered_lines: set[int] = set()

    for index, node in enumerate(structured_nodes):
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        covered_lines.update(range(start, end + 1))
        if isinstance(node, ast.ClassDef):
            chunk_type: ChunkType = "class"
        else:
            chunk_type = "function"
        metadata = ChunkMetadata(
            file_path=source_file.path,
            language="python",
            chunk_type=chunk_type,
            symbol_name=getattr(node, "name", None),
            line_start=start,
            line_end=end,
            chunk_index=index,
        )
        chunks.append((metadata, get_node_source(code, node).strip()))

    module_lines = [
        line
        for line_number, line in enumerate(lines, start=1)
        if line_number not in covered_lines and line.strip()
    ]
    if module_lines:
        # Module-level code matters too: imports, constants, and setup often
        # answer questions even when they are not inside a function or class.
        module_content = "\n".join(module_lines).strip()
        metadata = ChunkMetadata(
            file_path=source_file.path,
            language="python",
            chunk_type="module",
            symbol_name="module",
            line_start=1,
            line_end=len(lines),
            chunk_index=len(chunks),
        )
        chunks.insert(0, (metadata, module_content))

    return chunks or chunk_generic_file(source_file, "python")


def chunk_generic_file(
    source_file: SourceFile,
    language: LanguageName | None = None,
) -> list[tuple[ChunkMetadata, str]]:
    detected_language = language or detect_language(source_file.path)
    lines = source_file.content.splitlines()
    chunks: list[tuple[ChunkMetadata, str]] = []

    pattern = re.compile(
        r"^(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(source_file.content))

    if matches:
        # For non-Python files we use a lighter structure-aware approach first:
        # split around obvious function/class declarations before falling back
        # to fixed blocks.
        for index, match in enumerate(matches):
            start_offset = match.start()
            end_offset = matches[index + 1].start() if index + 1 < len(matches) else len(source_file.content)
            chunk_text = source_file.content[start_offset:end_offset].strip()
            line_start = source_file.content[:start_offset].count("\n") + 1
            line_end = line_start + chunk_text.count("\n")
            first_line = chunk_text.splitlines()[0]
            chunk_type: ChunkType = "class" if "class " in first_line else "function"
            metadata = ChunkMetadata(
                file_path=source_file.path,
                language=detected_language,
                chunk_type=chunk_type,
                symbol_name=match.group(1),
                line_start=line_start,
                line_end=line_end,
                chunk_index=index,
            )
            chunks.append((metadata, chunk_text))
        return chunks

    block_size = 28
    overlap = 4
    # Fixed blocks are the last fallback. The small overlap helps avoid losing
    # context when an answer sits near a chunk boundary.
    start_line = 1
    chunk_index = 0
    while start_line <= len(lines):
        end_line = min(start_line + block_size - 1, len(lines))
        chunk_lines = lines[start_line - 1 : end_line]
        content = "\n".join(chunk_lines).strip()
        if content:
            metadata = ChunkMetadata(
                file_path=source_file.path,
                language=detected_language,
                chunk_type="generic",
                symbol_name=None,
                line_start=start_line,
                line_end=end_line,
                chunk_index=chunk_index,
            )
            chunks.append((metadata, content))
            chunk_index += 1
        if end_line == len(lines):
            break
        start_line = max(end_line - overlap + 1, start_line + 1)

    return chunks


def chunk_source_file(source_file: SourceFile) -> list[tuple[ChunkMetadata, str]]:
    language = detect_language(source_file.path)
    if language == "python":
        return chunk_python_file(source_file)
    return chunk_generic_file(source_file, language)


def tokenize(text: str) -> list[str]:
    # Retrieval works better when we normalize code-ish text such as
    # `hash_password`, `hashes`, and `hashPassword` into related tokens.
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    raw_tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", normalized.lower())
    expanded: list[str] = []
    for token in raw_tokens:
        candidates = [token]
        if "_" in token:
            candidates.extend(part for part in token.split("_") if part)
        for candidate in candidates:
            if candidate in STOPWORDS:
                continue
            expanded.append(candidate)
            if len(candidate) > 5 and candidate.endswith("ing"):
                expanded.append(candidate[:-3])
            elif len(candidate) > 4 and candidate.endswith("ed"):
                expanded.append(candidate[:-2])
            elif len(candidate) > 4 and candidate.endswith("es"):
                expanded.append(candidate[:-2])
            elif len(candidate) > 4 and candidate.endswith("s"):
                expanded.append(candidate[:-1])
    return expanded


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class EmbeddingBackend(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError


class HashEmbeddingBackend(EmbeddingBackend):
    """Deterministic local embedding fallback using hashed token buckets."""

    @property
    def provider_name(self) -> str:
        return "hash-embedding"

    def embed_text(self, text: str) -> list[float]:
        # This is not a true semantic embedding model. It is a lightweight local
        # stand-in so students can run the full RAG pipeline without paid APIs.
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = digest[0] % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vector[bucket] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector
        return [value / magnitude for value in vector]


class OpenAIEmbeddingBackend(EmbeddingBackend):
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return f"openai-embedding:{self.model}"

    def embed_text(self, text: str) -> list[float]:
        try:
            response = self.client.embeddings.create(model=self.model, input=text)
        except OpenAIAPIStatusError as exc:
            message = exc.response.text if exc.response is not None else str(exc)
            raise HTTPException(
                status_code=502,
                detail=f"Embedding provider error (upstream {exc.status_code}): {message}",
            ) from exc
        except OpenAIAPIConnectionError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach embedding provider: {exc}") from exc

        return list(response.data[0].embedding)


class VectorStore:
    """Persistent local store so the app survives reloads in development."""

    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.chunks: list[IndexedChunk] = []
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            self.chunks = []
            return
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
            self.chunks = StoredIndex.model_validate(payload).chunks
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            LOGGER.warning("Could not load persisted index: %s", exc)
            self.chunks = []

    def _save(self) -> None:
        payload = StoredIndex(chunks=self.chunks).model_dump()
        self.store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def replace(self, chunks: list[IndexedChunk]) -> None:
        self.chunks = chunks
        self._save()

    def count(self) -> int:
        return len(self.chunks)

    def query(self, query_embedding: list[float], top_k: int) -> list[tuple[IndexedChunk, float]]:
        # Raw vector similarity is the first retrieval signal. We keep the store
        # simple here because the lab is about understanding the RAG pipeline,
        # not about operating a production vector database.
        ranked = [
            (chunk, cosine_similarity(query_embedding, chunk.embedding))
            for chunk in self.chunks
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_k]


def build_answer_prompt(question: str, sources: list[SourceSnippet]) -> str:
    # Module 4 theory: generation should be grounded in retrieved context.
    # The prompt explicitly tells the model to answer only from these snippets.
    context = "\n\n".join(
        (
            f"File: {source.file_path}\n"
            f"Chunk type: {source.chunk_type}\n"
            f"Symbol: {source.symbol_name or 'n/a'}\n"
            f"Lines: {source.line_start}-{source.line_end}\n"
            f"Code:\n{source.snippet}"
        )
        for source in sources
    )
    return (
        "You are a senior engineer answering questions about a codebase. "
        "Use only the retrieved context. If the answer is not supported, say that clearly. "
        "Give a concise answer and mention file paths or symbol names when possible.\n\n"
        f"Question: {question}\n\n"
        f"Retrieved context:\n{context}"
    )


def build_judge_prompt(
    dimension: JudgeDimension,
    question: str,
    expected_answer: str,
    generated_answer: str,
    sources: list[SourceSnippet],
) -> str:
    # LLM-as-judge is a second evaluation pass. Instead of asking "does this
    # feel good?", we ask the model to score a specific dimension consistently.
    source_context = "\n\n".join(
        f"{source.file_path}::{source.symbol_name or source.chunk_type}\n{source.snippet}"
        for source in sources
    )
    instructions = {
        "relevance": "Rate how well the answer addresses the question.",
        "faithfulness": "Rate whether the answer stays grounded in the retrieved code context.",
        "correctness": "Rate how correct the answer is compared to the expected answer.",
    }
    return (
        "Return strict JSON only with this shape: "
        '{"rating": 1, "explanation": "..."}.\n'
        f"{instructions[dimension]}\n"
        "Use a 1-5 scale where 1 is poor and 5 is excellent.\n\n"
        f"Question: {question}\n"
        f"Expected answer: {expected_answer}\n"
        f"Generated answer: {generated_answer}\n"
        f"Retrieved context:\n{source_context}"
    )


class RAGClient(ABC):
    @abstractmethod
    def answer_question(self, question: str, sources: list[SourceSnippet]) -> str:
        raise NotImplementedError

    @abstractmethod
    def judge_answer(
        self,
        dimension: JudgeDimension,
        question: str,
        expected_answer: str,
        generated_answer: str,
        sources: list[SourceSnippet],
    ) -> JudgeScore:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError


def summarize_code_snippet(snippet: str) -> str:
    non_empty = [line.strip() for line in snippet.splitlines() if line.strip()]
    if not non_empty:
        return "The chunk is empty."
    head = non_empty[0]
    tail = next((line for line in non_empty[1:] if line.startswith("return ")), "")
    if tail:
        return f"It starts with `{head}` and returns `{tail.removeprefix('return ').strip()}`."
    if len(non_empty) > 1:
        return f"It starts with `{head}` and includes `{non_empty[1]}`."
    return f"It contains `{head}`."


def lexical_overlap_score(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def directional_overlap_score(query_text: str, candidate_text: str) -> float:
    query_tokens = set(tokenize(query_text))
    candidate_tokens = set(tokenize(candidate_text))
    if not query_tokens or not candidate_tokens:
        return 0.0
    return len(query_tokens & candidate_tokens) / len(query_tokens)


class MockRAGClient(RAGClient):
    @property
    def provider_name(self) -> str:
        return "mock"

    def answer_question(self, question: str, sources: list[SourceSnippet]) -> str:
        if not sources:
            return "I could not find supporting code for that question in the current index."

        primary = sources[0]
        # The mock answer path is intentionally transparent: it picks the top
        # chunk, summarizes it, and says which supporting chunks were used.
        summary = summarize_code_snippet(primary.snippet)
        answer = (
            f"The strongest match is `{primary.file_path}`"
            f"{f'::{primary.symbol_name}' if primary.symbol_name else ''}. "
            f"{summary} "
            "This answer is grounded in the retrieved code snippets shown below."
        )
        if len(sources) > 1:
            supporting = ", ".join(
                f"{source.file_path}{f'::{source.symbol_name}' if source.symbol_name else ''}"
                for source in sources[1:3]
            )
            answer += f" Related context also came from {supporting}."
        return answer

    def judge_answer(
        self,
        dimension: JudgeDimension,
        question: str,
        expected_answer: str,
        generated_answer: str,
        sources: list[SourceSnippet],
    ) -> JudgeScore:
        # The mock judge uses lexical overlap as a cheap approximation for
        # relevance, faithfulness, and correctness. It is not production-grade,
        # but it lets students experience the full evaluation workflow locally.
        if dimension == "relevance":
            score = lexical_overlap_score(question, generated_answer)
            explanation = "Higher when the answer uses the same concepts as the question."
        elif dimension == "correctness":
            score = lexical_overlap_score(expected_answer, generated_answer)
            explanation = "Higher when the generated answer overlaps strongly with the expected answer."
        else:
            context = " ".join(source.snippet for source in sources)
            score = lexical_overlap_score(context, generated_answer)
            explanation = "Higher when the answer stays close to retrieved code context."

        rating = 1
        if score >= 0.58:
            rating = 5
        elif score >= 0.42:
            rating = 4
        elif score >= 0.26:
            rating = 3
        elif score >= 0.12:
            rating = 2

        return JudgeScore(dimension=dimension, rating=rating, explanation=explanation)


class OpenAICompatibleRAGClient(RAGClient):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    @property
    def provider_name(self) -> str:
        return f"openai-compatible:{self.model}"

    def answer_question(self, question: str, sources: list[SourceSnippet]) -> str:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "You answer codebase questions using only provided context."},
                {"role": "user", "content": build_answer_prompt(question, sources)},
            ],
        }
        try:
            response = self.client.chat.completions.create(**body)
        except OpenAIAPIStatusError as exc:
            message = exc.response.text if exc.response is not None else str(exc)
            raise HTTPException(
                status_code=502,
                detail=f"LLM provider error (upstream {exc.status_code}): {message}",
            ) from exc
        except OpenAIAPIConnectionError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach LLM provider: {exc}") from exc
        return response.choices[0].message.content.strip()

    def judge_answer(
        self,
        dimension: JudgeDimension,
        question: str,
        expected_answer: str,
        generated_answer: str,
        sources: list[SourceSnippet],
    ) -> JudgeScore:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are a strict evaluator for RAG answers."},
                {
                    "role": "user",
                    "content": build_judge_prompt(
                        dimension,
                        question,
                        expected_answer,
                        generated_answer,
                        sources,
                    ),
                },
            ],
        }
        try:
            response = self.client.chat.completions.create(**body)
        except OpenAIAPIStatusError as exc:
            message = exc.response.text if exc.response is not None else str(exc)
            raise HTTPException(
                status_code=502,
                detail=f"Judge provider error (upstream {exc.status_code}): {message}",
            ) from exc
        except OpenAIAPIConnectionError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach judge provider: {exc}") from exc

        content = response.choices[0].message.content
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="Judge response was not valid JSON.") from exc

        return JudgeScore(
            dimension=dimension,
            rating=max(1, min(5, int(parsed.get("rating", 3)))),
            explanation=str(parsed.get("explanation", "No explanation provided.")),
        )


class GeminiRAGClient(RAGClient):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return f"gemini:{self.model}"

    def _request(self, prompt: str, expect_json: bool = False) -> str:
        endpoint = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                **({"responseMimeType": "application/json"} if expect_json else {}),
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=45) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=502, detail=f"Gemini provider error: {detail}") from exc
        except error.URLError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach Gemini provider: {exc}") from exc

        parsed = json.loads(raw)
        candidates = parsed.get("candidates") or []
        if not candidates:
            raise HTTPException(status_code=502, detail="Gemini response had no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise HTTPException(status_code=502, detail="Gemini response had no content parts.")
        return parts[0].get("text", "").strip()

    def answer_question(self, question: str, sources: list[SourceSnippet]) -> str:
        return self._request(build_answer_prompt(question, sources))

    def judge_answer(
        self,
        dimension: JudgeDimension,
        question: str,
        expected_answer: str,
        generated_answer: str,
        sources: list[SourceSnippet],
    ) -> JudgeScore:
        raw = self._request(
            build_judge_prompt(dimension, question, expected_answer, generated_answer, sources),
            expect_json=True,
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="Gemini judge response was not valid JSON.") from exc

        return JudgeScore(
            dimension=dimension,
            rating=max(1, min(5, int(parsed.get("rating", 3)))),
            explanation=str(parsed.get("explanation", "No explanation provided.")),
        )


def create_embedding_backend() -> EmbeddingBackend:
    provider = os.getenv("EMBEDDING_PROVIDER", "mock").strip().lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY.")
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddingBackend(api_key=api_key, model=model)
    return HashEmbeddingBackend()


def create_rag_client() -> RAGClient:
    provider = os.getenv("RAG_PROVIDER", "mock").strip().lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("RAG_PROVIDER=openai requires OPENAI_API_KEY.")
        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        return OpenAICompatibleRAGClient(api_key=api_key, model=model, base_url="https://api.openai.com/v1")
    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("RAG_PROVIDER=groq requires GROQ_API_KEY.")
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        return OpenAICompatibleRAGClient(api_key=api_key, model=model, base_url="https://api.groq.com/openai/v1")
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("RAG_PROVIDER=gemini requires GEMINI_API_KEY or GOOGLE_API_KEY.")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return GeminiRAGClient(api_key=api_key, model=model, base_url="https://generativelanguage.googleapis.com/v1beta")
    return MockRAGClient()


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    retrieved_k = retrieved[:k]
    relevant_retrieved = len(set(retrieved_k) & relevant)
    return relevant_retrieved / k if k > 0 else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    retrieved_k = retrieved[:k]
    relevant_retrieved = len(set(retrieved_k) & relevant)
    return relevant_retrieved / len(relevant) if relevant else 0.0


def mean_reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for index, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / index
    return 0.0


class RAGService:
    def __init__(
        self,
        embedding_backend: EmbeddingBackend,
        rag_client: RAGClient,
        store: VectorStore,
    ) -> None:
        self.embedding_backend = embedding_backend
        self.rag_client = rag_client
        self.store = store

    @property
    def provider_name(self) -> str:
        return f"{self.rag_client.provider_name} | {self.embedding_backend.provider_name}"

    def index_files(self, payload: IndexFilesRequest) -> IndexFilesResponse:
        indexed_chunks: list[IndexedChunk] = []
        languages: set[str] = set()

        for source_file in payload.files:
            language = detect_language(source_file.path)
            languages.add(language)
            for metadata, content in chunk_source_file(source_file):
                # Every chunk gets a stable ID plus metadata. That matters for
                # traceability, UI display, and retrieval evaluation datasets.
                chunk_id = make_chunk_id(
                    metadata.file_path,
                    metadata.chunk_type,
                    metadata.symbol_name,
                    metadata.line_start,
                )
                embedding = self.embedding_backend.embed_text(
                    f"{metadata.file_path}\n{metadata.symbol_name or ''}\n{content}"
                )
                indexed_chunks.append(
                    IndexedChunk(
                        id=chunk_id,
                        content=content,
                        metadata=metadata,
                        embedding=embedding,
                    )
                )

        self.store.replace(indexed_chunks)
        return IndexFilesResponse(
            indexed_files=len(payload.files),
            chunk_count=len(indexed_chunks),
            languages=sorted(languages),
            provider=self.provider_name,
            chunking_strategy="AST-based for Python with regex/fixed fallback for other languages",
        )

    def ensure_indexed(self) -> None:
        if self.store.count() == 0:
            raise HTTPException(status_code=400, detail="No code is indexed yet. Call /index/files first.")

    def _rank_sources(self, question: str, top_k: int) -> list[SourceSnippet]:
        self.ensure_indexed()
        query_embedding = self.embedding_backend.embed_text(question)
        ranked_matches: list[tuple[IndexedChunk, float]] = []
        for chunk in self.store.chunks:
            semantic_score = cosine_similarity(query_embedding, chunk.embedding)
            searchable_text = "\n".join(
                [
                    chunk.metadata.file_path,
                    chunk.metadata.symbol_name or "",
                    chunk.content,
                ]
            )
            keyword_score = directional_overlap_score(question, searchable_text)
            symbol_score = directional_overlap_score(question, chunk.metadata.symbol_name or "")
            # This is a small hybrid-search style ranking:
            # - semantic_score helps with meaning
            # - keyword_score helps with exact code terms
            # - symbol_score boosts chunks whose function/class name matches
            combined_score = (semantic_score * 0.25) + (keyword_score * 0.45) + (symbol_score * 0.30)
            ranked_matches.append((chunk, combined_score))

        ranked_matches.sort(key=lambda item: item[1], reverse=True)
        matches = ranked_matches[:top_k]
        return [
            SourceSnippet(
                id=chunk.id,
                file_path=chunk.metadata.file_path,
                language=chunk.metadata.language,
                chunk_type=chunk.metadata.chunk_type,
                symbol_name=chunk.metadata.symbol_name,
                line_start=chunk.metadata.line_start,
                line_end=chunk.metadata.line_end,
                score=round(score, 4),
                snippet=chunk.content,
            )
            for chunk, score in matches
        ]

    def query(self, payload: QueryRequest) -> QueryResponse:
        sources = self._rank_sources(payload.question, payload.top_k)
        answer = self.rag_client.answer_question(payload.question, sources)
        return QueryResponse(
            answer=answer,
            sources=sources,
            indexed_chunks=self.store.count(),
            provider=self.provider_name,
            top_k=payload.top_k,
        )

    def load_default_dataset(self) -> list[EvalExample]:
        if not DEFAULT_DATASET_PATH.exists():
            raise HTTPException(status_code=500, detail="Default evaluation dataset file is missing.")
        raw = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
        return [EvalExample.model_validate(item) for item in raw]

    def evaluate(self, payload: EvaluateRequest) -> EvaluateResponse:
        self.ensure_indexed()
        examples = payload.examples or self.load_default_dataset()
        results: list[EvalExampleResult] = []

        for example in examples:
            # Each evaluation example runs the same real query flow as a user.
            # Then we compare the retrieved IDs and generated answer to the
            # expected ground truth for this test case.
            query_result = self.query(QueryRequest(question=example.question, top_k=payload.top_k))
            retrieved_ids = [source.id for source in query_result.sources]
            relevant_ids = set(example.relevant_docs)
            metrics = RetrievalMetrics(
                precision_at_k=round(precision_at_k(retrieved_ids, relevant_ids, payload.top_k), 4),
                recall_at_k=round(recall_at_k(retrieved_ids, relevant_ids, payload.top_k), 4),
                mrr=round(mean_reciprocal_rank(retrieved_ids, relevant_ids), 4),
            )
            judge_scores = [
                self.rag_client.judge_answer(
                    dimension=dimension,
                    question=example.question,
                    expected_answer=example.expected_answer,
                    generated_answer=query_result.answer,
                    sources=query_result.sources,
                )
                for dimension in ("relevance", "faithfulness", "correctness")
            ]
            results.append(
                EvalExampleResult(
                    id=example.id,
                    question=example.question,
                    expected_answer=example.expected_answer,
                    generated_answer=query_result.answer,
                    retrieved_doc_ids=retrieved_ids,
                    relevant_doc_ids=example.relevant_docs,
                    metrics=metrics,
                    judge_scores=judge_scores,
                    sources=query_result.sources,
                )
            )

        def avg(values: list[float]) -> float:
            return round(sum(values) / len(values), 4) if values else 0.0

        summary = EvaluationSummary(
            # The summary is what a student would usually show in the demo:
            # average retrieval quality plus average judge scores across the set.
            example_count=len(results),
            avg_precision_at_k=avg([result.metrics.precision_at_k for result in results]),
            avg_recall_at_k=avg([result.metrics.recall_at_k for result in results]),
            avg_mrr=avg([result.metrics.mrr for result in results]),
            avg_relevance=avg(
                [score.rating for result in results for score in result.judge_scores if score.dimension == "relevance"]
            ),
            avg_faithfulness=avg(
                [score.rating for result in results for score in result.judge_scores if score.dimension == "faithfulness"]
            ),
            avg_correctness=avg(
                [score.rating for result in results for score in result.judge_scores if score.dimension == "correctness"]
            ),
        )

        dataset_name = "request-provided" if payload.examples else DEFAULT_DATASET_PATH.name
        return EvaluateResponse(
            summary=summary,
            examples=results,
            provider=self.provider_name,
            dataset_name=dataset_name,
        )


embedding_backend = create_embedding_backend()
rag_client = create_rag_client()
vector_store = VectorStore(INDEX_PATH)
rag_service = RAGService(embedding_backend=embedding_backend, rag_client=rag_client, store=vector_store)

app = FastAPI(title="Lab 04 RAG System", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "name": "Lab 04 RAG System",
        "status": "ok",
        "provider": rag_service.provider_name,
        "indexed_chunks": rag_service.store.count(),
        "endpoints": [
            "/index/files",
            "/query",
            "/evaluate",
            "/api/index/files",
            "/api/query",
            "/api/evaluate",
        ],
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "provider": rag_service.provider_name,
        "indexed_chunks": rag_service.store.count(),
    }


@app.post("/index/files", response_model=IndexFilesResponse)
@app.post("/api/index/files", response_model=IndexFilesResponse)
def index_files(payload: IndexFilesRequest) -> IndexFilesResponse:
    return rag_service.index_files(payload)


@app.post("/query", response_model=QueryResponse)
@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    return rag_service.query(payload)


@app.post("/evaluate", response_model=EvaluateResponse)
@app.post("/api/evaluate", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    return rag_service.evaluate(payload)
