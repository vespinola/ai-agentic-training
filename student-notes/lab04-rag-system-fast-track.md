# Lab 04 RAG System Fast Track

This note is the shortest serious path through `04-rag-eval` plus the `lab04-rag-system` exercise.

Lab 04 is more important than it first looks. It is not just "make semantic search work." It is really about building a grounded AI system, proving that retrieval is helping, and showing evaluation evidence instead of intuition.

## 5-Minute Recap

If you only need the fast memory refresh, remember this:

- `RAG = chunk -> embed -> retrieve -> answer`
- Retrieval quality and answer quality are different problems
- Chunking is the most important implementation decision
- For code, chunk by functions, classes, and meaningful code units
- Store metadata so you can show where answers came from
- Lab 04 requires evaluation, not just a working chat flow
- Required metrics are `Precision@K`, `Recall@K`, and `MRR`
- You also need `LLM-as-judge` for generation quality
- Your deliverable includes an evaluation dataset with `10+` examples
- A good demo shows indexed files, retrieved chunks, answer, and metrics

## What Matters From Theory

### 1. RAG has two separate jobs

- Retrieval must find the right source chunks.
- Generation must answer using those chunks instead of guessing.

If either half fails, the whole system fails.

### 2. Chunking is the highest-leverage implementation choice

- Bad chunking is the most common RAG failure.
- For code, chunk by logical units such as functions, classes, or modules.
- Chunks should usually be self-contained enough to answer one question.
- Add small overlap or preserve surrounding context when helpful.

For this lab, "smart code-aware chunking" is a deliverable, not an optional polish item.

### 3. Metadata makes retrieval usable

Do not store bare text only. Keep metadata such as:

- file path
- language
- chunk type such as `function`, `class`, or `module`
- symbol name when available
- line range when available
- chunk index

This helps both retrieval quality and UI display.

### 4. Evaluation is part of the product

Lab 04 explicitly asks for:

- Precision@K
- Recall@K
- MRR
- LLM-as-judge for answer quality

That means a working chat UI is not enough. You need a repeatable way to measure whether the system is retrieving the right code and answering well.

#### What the required metrics actually mean

- `Precision@K`: out of the top `K` retrieved chunks, how many were actually relevant
- `Recall@K`: out of all relevant chunks for the question, how many did you successfully retrieve in the top `K`
- `MRR`: how early the first relevant result appears in the ranking

Quick intuition:

- high `Precision@K` means your top results are clean and not noisy
- high `Recall@K` means you are not missing important relevant chunks
- high `MRR` means the first useful result appears near the top, which matters a lot for real user experience

Example:

- expected relevant chunks: `A`, `B`
- retrieved top 3: `C`, `A`, `D`

Then:

- `Precision@3 = 1/3` because only `A` is relevant
- `Recall@3 = 1/2` because you found one of the two relevant chunks
- `MRR = 1/2` because the first relevant result appears at rank 2

This matters because a system can look "kind of okay" while still having weak retrieval.

- good answer with bad retrieval is often luck
- bad answer with good retrieval usually points to prompt or generation issues

### 5. Separate retrieval quality from answer quality

- If the wrong chunks are retrieved, generation is downstream damage.
- If the right chunks are retrieved but the answer is still weak, your prompt or answer construction is the problem.

Students often mix these together and then do not know what to fix.

#### Retrieval quality vs generation quality

Think about them as two separate tests:

- retrieval test: "did we fetch the right code?"
- generation test: "did we explain that code correctly and faithfully?"

You need both because:

- a relevant chunk can still produce a vague or wrong answer
- a polished answer can still be unsupported by the retrieved code

That is why the lab asks for both retrieval metrics and `LLM-as-judge`.

### 6. A RAG system should be inspectable

You want to be able to show:

- which files were indexed
- how many chunks were created
- which chunks were retrieved for a question
- what scores or ranking came back
- how the final answer was judged

If the system feels like a black box, it will be hard to debug and hard to demo.

---

## Lab 04 In Plain English

You are building a codebase Q&A app with three flows:

1. upload code files and index them
2. ask questions and retrieve relevant code chunks
3. run an evaluation suite and show metrics

The lab is successful when you can prove:

- indexing works
- retrieval is grounded in real code chunks
- answers cite or show source snippets
- evaluation results are visible and believable

## Read Only These Parts First

Prioritize these original files:

- `theory/04-rag-eval.md`
- `practice/lab04-rag-system.md`

Inside `04-rag-eval`, focus on:

- `1.1 What is RAG?`
- `2.1 Why Chunking Matters`
- `2.2 Chunking Strategies`
- `2.3 Chunking Best Practices`
- `3.1 Common RAG Failures`
- `5.2 Retrieval Metrics`
- `5.3 LLM-as-Judge Evaluation`
- `5.4 Building Evaluation Datasets`
- `5.5 Evaluation Pipeline`
- `6.1 Tracing AI Systems`
- `6.4 Common Debugging Patterns`
- `7. Lab 04: Build & Evaluate RAG System`

You can skim on the first pass:

- long vector database comparisons
- advanced hybrid search and reranking details
- full observability implementation examples if you are short on time

---

## The Architecture You Actually Need

Keep the architecture simple and explicit:

```text
Files -> Chunker -> Embeddings -> Vector Store

Question -> Query Embedding -> Top-K Retrieval -> Answer Prompt -> LLM Answer

Eval Dataset -> RAG Pipeline -> Retrieval Metrics + LLM Judge -> Results
```

Minimal system pieces:

- file ingestion
- code-aware chunker
- embedding function
- vector store
- query pipeline
- answer generator
- evaluation runner
- frontend for indexing, querying, and metrics

## Minimum Implementation Plan

### Backend

Create these endpoints:

- `POST /index/files`
- `POST /query`
- `POST /evaluate`
- `GET /health`

Suggested backend responsibilities:

- validate uploaded files
- detect language from filename or extension
- chunk code in a language-aware way
- store chunk content plus metadata
- retrieve top `k` chunks for each question
- generate grounded answers using retrieved chunks only
- run evaluation against a dataset with expected relevant chunk IDs and expected answers

### Frontend

Your UI should have three visible areas:

- indexing panel for file upload and indexing results
- query panel with question input and answer output
- evaluation panel with metrics and per-example results

Minimum frontend behaviors:

- show selected or uploaded files
- show indexing summary such as file count and chunk count
- allow a user to ask a question
- display the answer and retrieved source snippets
- run evaluation and display aggregate metrics

## Recommended Data Shapes

### Indexed chunk

```json
{
  "id": "src_app_py::function::create_user::12-34",
  "content": "def create_user(...): ...",
  "metadata": {
    "file_path": "src/app.py",
    "language": "python",
    "chunk_type": "function",
    "symbol_name": "create_user",
    "line_start": 12,
    "line_end": 34
  }
}
```

### Query response

```json
{
  "answer": "The user creation flow is implemented in create_user...",
  "sources": [
    {
      "id": "src_app_py::function::create_user::12-34",
      "file_path": "src/app.py",
      "symbol_name": "create_user",
      "score": 0.89,
      "snippet": "def create_user(...): ..."
    }
  ]
}
```

### Evaluation example

```json
{
  "id": "q1",
  "question": "Where is JWT authentication configured?",
  "expected_answer": "JWT authentication is configured in auth.py...",
  "relevant_docs": ["src_auth_py::function::setup_jwt::10-42"]
}
```

## Chunking Strategy That Is Good Enough

For this lab, do not overcomplicate chunking.

### Why chunking matters so much

Embeddings work on the chunk you give them. If the chunk is bad, retrieval quality usually drops before generation even begins.

Common chunking mistakes:

- chunks are too large, so one chunk mixes unrelated concerns
- chunks are too small, so the answer gets split across several fragments
- chunks ignore code structure, so a function body loses meaning
- chunks have no metadata, so even good retrieval is hard to explain in the UI

Good chunking for code means one chunk should usually represent one meaningful unit of behavior.

### Python

- Prefer AST-based chunking by `class` and `def`
- Include module-level code if it matters
- Preserve docstrings with the function or class

### TypeScript or JavaScript

- Prefer parser-based chunking if practical
- Otherwise chunk by exported functions, classes, handlers, and logical blocks

### Fallback

If parser-based chunking gets too heavy:

- split by function and class patterns
- keep chunk sizes reasonable
- include file path and symbol metadata

That is acceptable as long as chunks are meaningful and retrieval works.

## Retrieval Strategy That Is Good Enough

Start with the smallest convincing version:

1. embed each chunk once during indexing
2. embed the user question at query time
3. retrieve top `k` chunks by similarity
4. pass those chunks to the answer prompt
5. instruct the model to answer only from provided context

Reasonable defaults:

- `k = 3` or `k = 5`
- include scores if the vector store returns them
- show sources in the UI

### What `top K` means

`K` is the number of chunks you retrieve before generating the answer.

- low `K` can miss important context
- high `K` can add noise and make the model less focused

For this lab, `3` to `5` is usually a practical range for a small codebase demo.

If quality is poor, test different `K` values before changing everything else.

## Prompt Checklist

Your answer-generation prompt should specify:

- the system is answering questions about code
- only use retrieved context
- if the answer is not supported, say so clearly
- mention file paths or symbols when possible
- return a concise answer plus source references

Suggested prompt shape:

```text
You are a senior engineer answering questions about a codebase.

Use only the retrieved code context below.
If the answer is not supported by the context, say that directly.
Cite the most relevant file path or symbol names in the answer.

Question: ...
Retrieved context: ...
```

## Evaluation Plan You Should Implement

Think of evaluation in two layers.

### Retrieval evaluation

For each test question:

- define the relevant chunk IDs
- run retrieval
- compare returned IDs to expected IDs
- compute:
  - Precision@K
  - Recall@K
  - MRR

What this tells you:

- `Precision@K` answers: "how noisy are my top results?"
- `Recall@K` answers: "am I missing relevant material?"
- `MRR` answers: "does the useful result show up early enough?"

This is important because ranking matters. If the correct chunk is technically retrieved but always buried low, the user experience is still weak.

### Generation evaluation

For each test question:

- compare generated answer to expected answer
- judge relevance
- judge faithfulness to retrieved context
- judge correctness against expected answer

What these usually mean:

- relevance: did the answer address the question asked
- faithfulness: did the answer stay grounded in retrieved context
- correctness: did the answer match the expected answer closely enough

For RAG, faithfulness is especially important. A fluent answer is not a good answer if it invents details not found in the code.

If you are rushed, the most important thing is to implement:

- real retrieval metrics
- one LLM-as-judge pass with a visible score and explanation

### What `LLM-as-judge` is doing

This means you use a second evaluation prompt to score the generated answer instead of only eyeballing it yourself.

Typical judge questions:

- Is the answer relevant to the question?
- Is the answer faithful to the retrieved context?
- Is the answer correct compared to the expected answer?

This is useful because:

- it gives repeatable scoring
- it scales better than manual checking
- it helps compare prompt or retrieval changes over time

But remember:

- the judge is still another model, not absolute truth
- use it as structured evaluation, not as a magical guarantee

## How To Build the Evaluation Dataset

The dataset is one of the deliverables, so make it intentionally.

Aim for at least 10 examples covering:

- function lookup questions
- architecture questions
- config or auth questions
- data flow questions
- edge cases where retrieval could confuse similar files

Good evaluation questions are:

- answerable from the indexed code
- specific enough to map to known chunks
- varied across files and concepts

Weak evaluation questions are:

- too broad
- opinion-based
- answerable from many unrelated chunks

### What makes a strong evaluation example

A strong example usually has:

- one clear question
- one expected answer or very narrow answer space
- one or a few known relevant chunk IDs
- enough specificity that you can tell whether retrieval succeeded

Weak example:

- "How does this app work?"

Strong example:

- "Which function validates JWT tokens, and what file is it in?"

The stronger your examples are, the more meaningful your metrics become.

## Deliverables Checklist

Use this exact list before you submit:

- [ ] Working `POST /index/files` endpoint
- [ ] Working `POST /query` endpoint
- [ ] Working `POST /evaluate` endpoint
- [ ] Code-aware chunking, not just naive giant file embeddings
- [ ] Stored metadata for chunks and visible source snippets
- [ ] Retrieval metrics: Precision@K, Recall@K, MRR
- [ ] LLM-as-judge evaluation for generated answers
- [ ] Evaluation dataset with at least 10 examples
- [ ] Web frontend for indexing, Q&A, and metrics
- [ ] Deployed backend and frontend
- [ ] Final live URL to share

## What To Demo

Your demo should show:

1. Uploading or indexing a small codebase
2. A summary of indexed files and chunk count
3. Asking a concrete code question
4. The answer plus retrieved source snippets
5. Running evaluation
6. Displaying Precision@K, Recall@K, and MRR
7. Showing at least one LLM-judge result or explanation
8. The deployed app working end to end

## Easy Misses

- embedding whole files without meaningful chunking
- returning answers without showing sources
- evaluating answer quality but not retrieval quality
- having no dataset with expected relevant docs
- using chunk text in storage but no stable chunk IDs
- claiming grounding while the prompt allows unsupported guesses
- building only the query flow and skipping `/evaluate`
- showing aggregate metrics only, with no per-example visibility

## Do Not Forget These 7 Things

1. Do not embed entire files as single chunks unless the files are tiny.
2. Do not build query answering without stable chunk IDs and metadata.
3. Do not judge the answer only by vibes; compute retrieval metrics too.
4. Do not skip the evaluation dataset; it is part of the actual lab output.
5. Do not let the model answer beyond retrieved context without saying so.
6. Do not hide the retrieved snippets in the UI; they help with trust and debugging.
7. Do not submit without proving the three flows: indexing, querying, and evaluation.

## Debugging Order

When the app gives wrong answers, debug in this order:

1. Check whether the right chunks were retrieved
2. Check whether those chunks actually contain the answer
3. Check whether chunk sizes are too small or too large
4. Check whether metadata and IDs are consistent
5. Check the answer-generation prompt
6. Check whether too many irrelevant chunks are being passed

This order matters. Most RAG bugs are retrieval bugs first.

## If You Are Short On Time

Build the smallest convincing version:

- support one small codebase only
- use one embedding provider
- use ChromaDB or a simple in-memory vector store
- chunk by functions and classes
- retrieve top 3 to 5 chunks
- build a dataset with exactly 10 questions
- compute the three required retrieval metrics
- add one LLM-as-judge score for correctness or faithfulness

It is much better to have a small system with real evaluation than a bigger system with vague claims.

## Summary

Lab 04 is about evidence. A good submission does not just answer questions about code. It shows how the code was chunked, what was retrieved, how answers were grounded, and how quality was measured.
