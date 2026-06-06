const API_BASE_URL =
  (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000";

const SAMPLE_TASK = [
  "Create a concise research brief explaining how vector databases work for a junior backend developer.",
  "Include the main use case, the tradeoffs versus traditional databases, and when not to use one.",
  "Keep it practical and easy to scan."
].join(" ");

const runForm = document.getElementById("run-form");
const taskInput = document.getElementById("task-input");
const iterationsInput = document.getElementById("iterations-input");
const loadSampleBtn = document.getElementById("load-sample-btn");
const runBtn = document.getElementById("run-btn");
const runStatus = document.getElementById("run-status");
const providerBadge = document.getElementById("provider-badge");
const workflowEmpty = document.getElementById("workflow-empty");
const workflowSummary = document.getElementById("workflow-summary");
const activityOutput = document.getElementById("activity-output");
const resultEmpty = document.getElementById("result-empty");
const resultContent = document.getElementById("result-content");
const finalOutput = document.getElementById("final-output");
const researchOutput = document.getElementById("research-output");
const writerOutput = document.getElementById("writer-output");
const reviewOutput = document.getElementById("review-output");

function setStatus(message, kind = "") {
  runStatus.textContent = message;
  runStatus.className = `status ${kind}`.trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatList(items) {
  if (!items || !items.length) {
    return "<p class=\"structured-copy\">None.</p>";
  }

  return `<ul class="structured-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderSummary(payload) {
  workflowEmpty.classList.add("hidden");
  workflowSummary.classList.remove("hidden");

  workflowSummary.innerHTML = `
    <article class="summary-card">
      <h3>Status</h3>
      <p class="summary-value">${escapeHtml(payload.status)}</p>
    </article>
    <article class="summary-card">
      <h3>Iterations</h3>
      <p class="summary-value">${payload.iteration_count} / ${payload.max_iterations}</p>
    </article>
    <article class="summary-card">
      <h3>Workers Used</h3>
      <p class="summary-value">${escapeHtml(payload.workers_used.join(", ") || "None")}</p>
    </article>
    <article class="summary-card">
      <h3>Errors</h3>
      <p class="summary-value">${escapeHtml(payload.errors.length ? payload.errors.join(" | ") : "None")}</p>
    </article>
  `;
}

function renderActivity(log) {
  activityOutput.innerHTML = "";

  if (!log || !log.length) {
    activityOutput.innerHTML = "<div class=\"empty-state\">No activity recorded.</div>";
    return;
  }

  log.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "activity-card";
    const payloadText =
      entry.payload && Object.keys(entry.payload).length
        ? JSON.stringify(entry.payload, null, 2)
        : "No extra payload.";

    card.innerHTML = `
      <div class="activity-header">
        <div>
          <h3>${escapeHtml(entry.actor)}</h3>
          <p class="activity-detail">${escapeHtml(entry.detail)}</p>
        </div>
        <div class="activity-meta">
          <span class="step-badge">Step ${entry.step}</span>
          <span class="event-pill ${escapeHtml(entry.event)}">${escapeHtml(entry.event)}</span>
        </div>
      </div>
      <pre class="payload-block">${escapeHtml(payloadText)}</pre>
    `;
    activityOutput.appendChild(card);
  });
}

function renderStructuredResearch(payload) {
  if (!payload) {
    researchOutput.innerHTML = "<p class=\"structured-copy\">No research result.</p>";
    return;
  }

  researchOutput.innerHTML = `
    <p class="structured-copy"><strong>Summary</strong><br />${escapeHtml(payload.summary)}</p>
    <p class="structured-copy"><strong>Key Points</strong></p>
    ${formatList(payload.key_points)}
    <p class="structured-copy"><strong>Sources</strong></p>
    ${formatList(payload.sources)}
    <p class="structured-copy"><strong>Open Questions</strong></p>
    ${formatList(payload.open_questions)}
  `;
}

function renderStructuredWriter(payload) {
  if (!payload) {
    writerOutput.innerHTML = "<p class=\"structured-copy\">No writer result.</p>";
    return;
  }

  writerOutput.innerHTML = `
    <p class="structured-copy"><strong>Title</strong><br />${escapeHtml(payload.title)}</p>
    <p class="structured-copy"><strong>Format Notes</strong></p>
    ${formatList(payload.format_notes)}
    <pre class="payload-block">${escapeHtml(payload.draft)}</pre>
  `;
}

function renderStructuredReview(payload) {
  if (!payload) {
    reviewOutput.innerHTML = "<p class=\"structured-copy\">No review result.</p>";
    return;
  }

  reviewOutput.innerHTML = `
    <p class="structured-copy"><strong>Approved</strong>: ${payload.approved ? "Yes" : "Not yet"}</p>
    <p class="structured-copy"><strong>Score</strong>: ${payload.score} / 10</p>
    <p class="structured-copy"><strong>Strengths</strong></p>
    ${formatList(payload.strengths)}
    <p class="structured-copy"><strong>Issues</strong></p>
    ${formatList(payload.issues)}
    <p class="structured-copy"><strong>Revision Brief</strong><br />${escapeHtml(payload.revision_brief)}</p>
  `;
}

function renderResult(payload) {
  resultEmpty.classList.add("hidden");
  resultContent.classList.remove("hidden");
  providerBadge.textContent = `Provider: ${payload.provider}`;
  finalOutput.textContent = payload.final_output;
  renderStructuredResearch(payload.research_result);
  renderStructuredWriter(payload.writer_result);
  renderStructuredReview(payload.review_result);
}

loadSampleBtn.addEventListener("click", () => {
  taskInput.value = SAMPLE_TASK;
  iterationsInput.value = "5";
  setStatus("Sample task loaded. Run the orchestration when ready.", "success");
});

runForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const task = taskInput.value.trim();
  const maxIterations = Number(iterationsInput.value);

  if (!task) {
    setStatus("Please describe a task for the multi-agent system.", "error");
    return;
  }

  runBtn.disabled = true;
  setStatus("Supervisor is coordinating the team...", "");
  providerBadge.textContent = "Provider pending";

  try {
    const response = await fetch(`${API_BASE_URL}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task,
        max_iterations: maxIterations
      })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to run the multi-agent workflow.");
    }

    renderSummary(payload);
    renderActivity(payload.activity_log);
    renderResult(payload);
    setStatus(`Workflow finished with status: ${payload.status}.`, "success");
  } catch (error) {
    setStatus(error.message || "Request failed.", "error");
  } finally {
    runBtn.disabled = false;
  }
});

taskInput.value = SAMPLE_TASK;
