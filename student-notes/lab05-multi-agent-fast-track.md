# Lab 05 Multi-Agent Fast Track

This note is the shortest serious path through `05-production` plus the `lab05-multi-agent` exercise.

Lab 05 looks smaller than Lab 03 and Lab 04, but it teaches an important production idea: sometimes the right answer is not a bigger prompt, but a better workflow. Multi-agent orchestration is about dividing work cleanly, routing it on purpose, and making the system inspectable.

## 5-Minute Recap

If you only need the fast memory refresh, remember this:

- Multi-agent is useful when one prompt is trying to do too many jobs
- The main pattern in this lab is the `supervisor` pattern
- The supervisor routes work; workers do specialized tasks
- Good worker roles are narrow and explicit
- Structured handoffs matter more than fancy autonomy
- A good first workflow is `research -> write -> review -> final`
- You need an iteration limit so the system always stops
- A useful demo shows the agent trace, not just the final answer
- The real lesson is orchestration and specialization, not "use more agents"

## What Matters From Theory

### 1. Multi-agent is for decomposition, not decoration

- Do not add multiple agents just because it sounds advanced.
- Use multiple agents when the task benefits from:
  - specialization
  - explicit stages
  - review or second-pass checking
  - clearer control over workflow

If one well-structured agent can do the job, that is usually simpler. Multi-agent earns its complexity only when the task becomes easier to control after splitting responsibilities.

### 2. The supervisor is the control plane

The supervisor should:

- read the user task
- decide which worker acts next
- send the right context to that worker
- track intermediate outputs
- decide when the work is complete
- stop when `max_iterations` is reached

The supervisor should usually not do the specialist work itself. Its job is routing, coordination, and synthesis.

### 3. Worker boundaries are the main quality lever

A weak multi-agent system usually has workers that overlap too much.

For this lab, a strong minimal split is:

- `Researcher`: gathers facts, extracts useful points, identifies unknowns
- `Writer`: turns research into a polished answer
- `Reviewer`: checks clarity, completeness, and unsupported claims

This matters because each worker should make the next step easier. If the Writer starts researching from scratch or the Reviewer rewrites everything, the boundaries are too fuzzy.

### 4. Handoffs should be structured

Do not rely on vague free-form text if you can avoid it.

Prefer outputs with predictable fields such as:

- `summary`
- `key_points`
- `sources`
- `open_questions`
- `draft`
- `review_feedback`
- `approved`

Structured handoffs make the backend easier to reason about and the frontend much easier to visualize.

### 5. Stopping rules are part of production design

Without a stopping rule, a supervisor can loop forever or spend tokens on low-value refinement.

For this lab:

- respect `max_iterations`
- stop early if the result is already good enough
- force a final answer if the limit is reached
- return the best available result instead of hanging or failing silently

This is a small but real production pattern.

### 6. Observability is part of the deliverable

You should be able to show:

- which worker ran
- what task it received
- what it returned
- what the supervisor decided next
- why the system stopped

If the workflow is invisible, debugging and demoing become much harder.

---

## Lab 05 In Plain English

You are building a mini research assistant where one agent manages the workflow and specialized workers contribute pieces of the final result.

The lab is successful when you can prove:

- the supervisor is making orchestration decisions
- workers have clear distinct roles
- intermediate outputs are visible
- the system stops reliably
- the final answer is better than what one generic prompt would likely produce

## Read Only These Parts First

Prioritize these original files:

- `theory/05-production.md`
- `practice/lab05-multi-agent.md`

Inside `05-production`, focus on:

- production mindset around reliability and control
- the Lab 05 section
- the quick orchestration example
- the idea that systems need explicit limits and inspectable behavior

You can skim on the first pass:

- long deployment sections that are not directly needed for this lab
- broader production checklists that do not affect your first working version

---

## The Architecture You Actually Need

Keep the architecture simple and explicit:

```text
User Task
   ->
Supervisor
   ->
Researcher -> structured research result
   ->
Writer -> draft
   ->
Reviewer -> feedback / approval
   ->
Supervisor -> final answer + trace
```

Minimal system pieces:

- `POST /run`
- supervisor function or class
- two or three worker functions with different prompts
- shared state object
- iteration counter
- activity trace
- frontend that shows agent activity and final output

## Minimum Implementation Plan

### Backend

Create these endpoints:

- `POST /run`
- `GET /health`

Suggested backend responsibilities:

- validate the incoming task
- initialize orchestration state
- delegate to the correct worker
- store worker outputs in shared state
- stop when complete or at iteration limit
- return both final output and trace data

### Frontend

Your UI should have three visible ideas:

- task input
- live or step-by-step agent activity
- final answer panel

Minimum frontend behaviors:

- accept a research task
- call `POST /run`
- show which agent worked in what order
- display intermediate worker results or summaries
- show the final response clearly

## Recommended State Shape

Use something close to this even if your exact fields differ:

```json
{
  "task": "Explain vector databases for a junior backend developer",
  "iteration": 2,
  "max_iterations": 5,
  "status": "running",
  "research_result": {
    "summary": "...",
    "key_points": ["...", "..."],
    "open_questions": []
  },
  "draft_result": {
    "draft": "..."
  },
  "review_result": {
    "approved": false,
    "feedback": ["add a simpler explanation of embeddings"]
  },
  "activity_log": [
    {
      "agent": "supervisor",
      "action": "delegate",
      "target": "researcher"
    }
  ],
  "final_output": null,
  "errors": []
}
```

## Prompt Checklist

Before calling the model, make sure your prompts specify:

- the role of the current agent
- what that agent is responsible for
- what that agent should not do
- what context it is receiving
- what output format it must return
- how to signal completion or needed revision

### Example worker expectations

For `Researcher`:

- find and summarize relevant information
- list key points
- avoid polishing into final prose

For `Writer`:

- use the research input only
- produce a polished answer
- avoid inventing unsupported facts

For `Reviewer`:

- critique the draft
- flag missing support or unclear sections
- decide whether it is good enough

## Recommended Supervisor Behavior

The simplest good decision policy is:

1. if there is no research result, call `Researcher`
2. if there is research but no draft, call `Writer`
3. if there is a draft but no review, call `Reviewer`
4. if review says revise and you still have iterations left, send focused revision task to `Writer`
5. if review approves or you hit the iteration limit, return `FINAL`

This is enough to demonstrate orchestration without overengineering.

## Deliverables Checklist

Use this exact list before you submit:

- [ ] Working `POST /run` endpoint
- [ ] Supervisor plus at least 2 worker agents
- [ ] Clear role specialization
- [ ] Shared state across iterations
- [ ] Iteration limit with forced completion
- [ ] Agent activity trace or conversation log
- [ ] Web frontend that visualizes the workflow
- [ ] Deployed backend and frontend
- [ ] Final live URL to share

## Easy Misses

- building three agents that all behave like the same general assistant
- letting the supervisor do the worker tasks itself
- no visible trace of delegation decisions
- no stopping condition
- passing huge unstructured blobs between agents
- treating the final answer as the only output that matters
- adding too many workers before the basic loop works

## If You Are Short On Time

Build the smallest convincing version:

- one supervisor
- two workers such as `Researcher` and `Writer`
- optional `Reviewer` if time allows
- linear routing first, dynamic routing second
- one task input box
- one activity feed
- one final result panel

It is better to show a clean, inspectable workflow than a more ambitious system with confusing agent boundaries.

## What To Read In The Original Course

Prioritize these two course files:

- `theory/05-production.md`
- `practice/lab05-multi-agent.md`

Focus on:

- why production systems need control and limits
- when multi-agent is worth the extra complexity
- the supervisor pattern
- specialization and structured communication
- visible workflow state

## Summary

Lab 05 is really about coordination. If you can show that the supervisor controls a small team of specialized workers, records what happened, and reaches a final answer reliably, you learned the important part of the lab.
