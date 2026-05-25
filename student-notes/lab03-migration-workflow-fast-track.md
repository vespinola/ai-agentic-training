# Lab 03 Migration Workflow Fast Track

This note is the shortest path through `03-agents` plus the `lab03-migration-workflow` exercise.

## What Matters From Theory

### 1. An agent is a loop, not a single prompt

- A normal LLM call answers once.
- An agent observes, decides, acts, checks the result, and repeats.
- For this lab, that loop becomes four explicit phases: analysis, planning, execution, verification.

### 2. State is part of the product

- Do not treat each step as a fresh prompt.
- Keep shared state for:
  - input files
  - source and target frameworks
  - migration plan
  - step status
  - generated files
  - verification result
  - errors

If state is messy, the agent will feel random even when the prompts are decent.

### 3. Planning is the main pattern in this lab

The model should not jump straight from input code to final output.

Instead:

1. inspect the source files
2. create an ordered plan
3. execute one step at a time
4. verify the result before claiming success

This is the difference between a toy demo and an actual workflow agent.

### 4. Verification keeps the agent honest

- Do not trust generated code just because it looks plausible.
- Add a final verification pass that checks for obvious migration gaps.
- Your response should clearly say what succeeded, what failed, and what still needs human review.

### 5. Tool-use can stay simple

You do not need a huge autonomous system for this lab.

A good minimal version can:
- accept files in the request
- use the model to analyze and plan
- use the model again to generate migrated code
- use one more pass to verify the output

The important part is the workflow, not fancy infrastructure.

## Lab 03 In Plain English

You are building an app that takes source files from one framework and produces:

- a migration plan
- migrated output files
- step-by-step status
- a verification summary

The UI should make the workflow visible, not just show the final code dump.

## Minimum Implementation Plan

### Backend

- Create `POST /migrate`
- Accept:
  - source files
  - source framework
  - target framework
- Define an agent state object with the four phases
- Run the phases in order:
  1. analysis
  2. planning
  3. execution
  4. verification
- Return structured JSON with:
  - `success`
  - `plan`
  - `migrated_files`
  - `verification`
  - `errors`

### Frontend

- input area for one or more source files
- source framework selector
- target framework selector
- run migration button
- progress indicator for the four phases
- plan display with step statuses
- migrated output panel
- verification or issues panel

## Suggested State Shape

Use something close to this even if your exact fields differ:

```text
{
  "phase": "analysis",
  "source_framework": "flask",
  "target_framework": "fastapi",
  "source_files": [...],
  "analysis_summary": "...",
  "plan": [
    {
      "id": "step-1",
      "description": "...",
      "status": "pending",
      "dependencies": []
    }
  ],
  "migrated_files": [...],
  "verification": {
    "passed": false,
    "issues": []
  },
  "errors": []
}
```

## Prompt Checklist

Before calling the model, make sure your prompts specify:

- the agent phase it is performing
- the source and target frameworks
- the expected output schema
- that step ordering must be explicit
- that migrated code should preserve functionality
- that verification must call out missing pieces, not just praise the result

## Recommended Phase Behavior

### Analysis

- summarize what the input app is doing
- identify framework-specific patterns
- note risky migration points such as routing, state, middleware, config, or async behavior

### Planning

- create small ordered steps
- mark dependencies between steps
- avoid vague plan items like "migrate everything"

### Execution

- generate migrated files or transformed code blocks
- update step statuses as work completes
- collect any partial failures instead of hiding them

### Verification

- check whether the migrated code matches the requested target framework
- identify unresolved imports, missing files, broken assumptions, or incomplete conversions
- produce a final migration report

## Deliverables Checklist

Use this exact list before you submit:

- [ ] Working `POST /migrate` endpoint
- [ ] Agent state management across all 4 phases
- [ ] Migration plan with statuses
- [ ] Code generation for migration steps
- [ ] Verification phase with clear result
- [ ] Web frontend that visualizes progress
- [ ] Deployed backend and frontend
- [ ] Final live URL to share

## Easy Misses

- skipping the plan and jumping straight to code generation
- returning unstructured text instead of a clear JSON result
- no explicit step statuses
- verification that is just another summary with no concrete issues
- UI only showing final output and hiding the workflow
- supporting only one happy path with no error reporting

## If You Are Short On Time

Build the smallest convincing version:

- support one migration pair such as Flask to FastAPI or Express to Hono
- accept a small number of files
- generate a short plan with 3 to 5 steps
- return migrated code for the main file first
- add a basic verification summary

It is better to finish one clean end-to-end workflow than to promise many framework combinations and leave them half-working.

## What To Read In The Original Course

Prioritize these two course files:

- `theory/03-agents.md`
- `practice/lab03-migration-workflow.md`

Inside `03-agents`, focus on:

- what makes an agent different from a simple LLM call
- tool-use and function calling
- planning and verification patterns
- state and memory concepts
- the lab 03 section

## Summary

Lab 03 is really about orchestration. If you can show a clear four-phase workflow with state, plan execution, and verification, you have built the important part of the lab.
