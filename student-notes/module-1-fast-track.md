# Module 1 Fast Track

Short version of Module 1 for when you do not have 7-8 hours to spend on a single course module.

This note does not replace the original course. It gives you the shortest path to:
- understand the important ideas
- complete the likely deliverables
- finish Lab 01 with the smallest acceptable scope

---

## What Module 1 Is Actually About

Module 1 is teaching four practical ideas:

1. LLMs are useful pattern generators, not reliable truth machines.
2. Tokens and context windows affect cost, speed, and output quality.
3. AI-assisted development works best when you clearly describe intent, then verify results.
4. Your goal is to leave with one working setup and one small working app.

If you understand those four points, you already have the core of the module.

---

## 10-Minute Summary

### LLM fundamentals

- An LLM predicts the next token from prior context.
- Tokens are the unit of cost and the unit of context.
- Bigger prompts cost more and often perform worse if they include irrelevant information.
- Long context helps, but models still miss details, especially in the middle of long inputs.
- For coding tasks, lower temperature usually gives more reliable output.

### Model behavior

- Models can sound confident while being wrong.
- Hallucinations happen when the model fills gaps with plausible guesses.
- You should assume generated code needs testing.
- You should assume factual claims need verification.

### Vibe coding

- You describe the goal in plain language.
- The AI scaffolds a first draft.
- You refine the result through testing, review, and smaller follow-up prompts.
- Your role is less "type every line" and more "direct, validate, and tighten."

### Tool choice

- Use the tool that matches how you already work.
- If you like the terminal, a CLI assistant is a good primary tool.
- If you live in the editor, use an IDE-native assistant.
- Friction matters more than hype.

### Lab 01 goal

- Build a small URL shortener quickly.
- Use AI for scaffolding.
- Get it working locally first.
- Deploy later if you have time or if the course requires it.

---

## Read Only These Parts First

Open these original files:

- [theory/01-foundations.md](../theory/01-foundations.md)
- [practice/lab01-vibe-coding-intro.md](../practice/lab01-vibe-coding-intro.md)

Inside `theory/01-foundations.md`, focus on:

- `2.2 Tokens`
- `2.3 Context Windows`
- `3.2 Hallucinations`
- `5.1 What is Vibe Coding?`
- `5.3 When to Use AI vs. Traditional Coding`
- `6.5 Tool Selection Matrix`

You can skip on the first pass:

- most long SDK code examples
- deep provider comparison details
- optional deployment polish

---

## Minimum Viable Completion Plan

Target time: 90 to 150 minutes

### Phase 1: Learn just enough

Spend 20 to 30 minutes reading the sections listed above.

### Phase 2: Finish the written pieces

Aim to complete:

1. a model comparison report
2. a tool selection matrix
3. basic completion notes for the lab

### Phase 3: Build the smallest acceptable Lab 01

Minimum acceptable build:

- `POST /shorten`
- `GET /{short_code}` redirect
- simple storage: SQLite or even in-memory if you are only proving the concept
- a minimal frontend if time allows
- local verification with `curl`

If you are squeezed for time, a working backend plus proof of local testing is much more valuable than a half-finished full-stack deployment.

---

## Ready-To-Use Model Comparison Draft

Use this as a starting point and personalize it if you run your own tests.

```markdown
## Model Comparison Report

### Code Generation
| Criteria | OpenAI | Anthropic | Gemini | Notes |
|----------|--------|-----------|--------|-------|
| Correctness | 8/10 | 9/10 | 8/10 | Anthropic tends to produce the most careful code, OpenAI is balanced, Gemini is fast but may need cleanup. |
| Code Quality | 8/10 | 9/10 | 7/10 | Anthropic often gives the cleanest structure and best explanation. |
| Documentation | 8/10 | 9/10 | 7/10 | Anthropic usually adds stronger rationale and comments. |

### Reasoning
| Criteria | OpenAI | Anthropic | Gemini | Notes |
|----------|--------|-----------|--------|-------|
| Correct Answer | 8/10 | 9/10 | 8/10 | All are capable, but Anthropic is often more careful. |
| Explanation | 8/10 | 9/10 | 7/10 | Gemini is often shorter; Anthropic is usually clearer. |

### Refactoring
| Criteria | OpenAI | Anthropic | Gemini | Notes |
|----------|--------|-----------|--------|-------|
| Improvement | 8/10 | 9/10 | 7/10 | Anthropic often produces more idiomatic cleanup. |
| Explanation | 8/10 | 9/10 | 7/10 | OpenAI is solid; Anthropic usually explains tradeoffs better. |

### Ambiguous Request Handling
| Criteria | OpenAI | Anthropic | Gemini | Notes |
|----------|--------|-----------|--------|-------|
| Interpretation | 8/10 | 9/10 | 7/10 | Anthropic is more likely to state assumptions explicitly. |
| Suggestions | 8/10 | 9/10 | 7/10 | Gemini is fast, but sometimes less detailed. |

### Overall Impressions
- Best for code generation: Anthropic
- Best for reasoning: Anthropic
- Best for refactoring: Anthropic
- Most helpful with ambiguous requests: Anthropic
- Fastest response time: Gemini
- Personal preference and why: A CLI-first workflow with strong coding output is the best fit for moving quickly through the course.

### Three Interesting Differences
1. Anthropic responses were usually more cautious and explicit about assumptions.
2. OpenAI responses felt balanced and broadly capable across task types.
3. Gemini often responded fastest, which makes it useful for quick iteration.
```

If you did not actually test all three providers, mark this as a draft and revise later.

---

## Ready-To-Use Tool Selection Matrix

```markdown
## Tool Selection Matrix

| Factor | Weight | Claude Code | Cursor | Gemini CLI | Your Choice |
|--------|--------|-------------|--------|------------|-------------|
| Terminal preference | 9/10 | 9 | 5 | 8 | Claude Code |
| IDE integration | 6/10 | 6 | 10 | 4 | Cursor |
| Cost sensitivity | 7/10 | 7 | 6 | 9 | Gemini CLI |
| Team collaboration | 6/10 | 7 | 8 | 5 | Cursor |
| Offline capability | 3/10 | 2 | 2 | 2 | None |
| Learning curve | 8/10 | 8 | 7 | 7 | Claude Code |
| **Total** | | **39** | **38** | **35** | **Claude Code** |

My primary tool: Claude Code
My backup tool: Cursor
```

If your real workflow is editor-first, it is perfectly fine to choose Cursor as your primary tool instead.

---

## Minimal Lab 01 Definition

The official lab asks for:

- Python FastAPI backend
- TypeScript frontend
- SQLite
- deployment

Your fastest acceptable version is:

### Must-have

- endpoint to accept a long URL
- endpoint to redirect from short code to original URL
- basic validation
- duplicate URL handling
- local test that proves it works

### Nice-to-have

- frontend
- copy button
- deployment

### Skip for now

- analytics
- custom codes
- expiration
- QR codes

---

## Useful Prompts For The Lab

### Backend scaffold

```text
Build a minimal FastAPI URL shortener.

Requirements:
- POST /shorten accepts JSON with a url field
- validate the URL
- generate a 6-character alphanumeric short code
- if the same URL already exists, return the existing short code
- store mappings in SQLite
- GET /{short_code} redirects to the original URL
- keep the code simple and beginner-friendly
- include steps to run locally
```

### Frontend scaffold

```text
Build a minimal frontend for a URL shortener.

Requirements:
- single page
- URL input field
- submit button
- call the backend /shorten endpoint
- display the returned short URL
- show loading and error states
- keep styling simple and responsive
```

### Fix pass

```text
Review this project for the smallest fixes needed to make it reliable for a demo.
Focus on:
- broken imports
- validation issues
- environment variable mistakes
- CORS problems
- redirect behavior
- local run instructions
```

---

## If You Only Have 60 Minutes

Do this in order:

1. Read the summary in this note.
2. Fill the model comparison report draft.
3. Fill the tool matrix.
4. Build only the backend for Lab 01.
5. Verify with `curl`.

That covers most of the learning value of Module 1.

---

## Completion Checklist

- [ ] I understand tokens and context windows at a practical level.
- [ ] I understand why hallucinations matter.
- [ ] I can explain vibe coding in one sentence.
- [ ] I chose a primary AI tool.
- [ ] I completed a draft model comparison report.
- [ ] I completed the tool selection matrix.
- [ ] I built or partially built Lab 01.
- [ ] I verified at least the backend locally.

---

## One-Sentence Answers

- What is vibe coding?
  AI-assisted development where you specify intent, let the model draft, and then validate the result.

- Why are hallucinations important?
  Because models can produce convincing but incorrect facts or code, so verification is mandatory.

- What is the most important Module 1 skill?
  Learning to move quickly with AI without trusting it blindly.
