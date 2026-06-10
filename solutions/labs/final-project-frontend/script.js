const API_BASE_URL =
  (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000";

const SAMPLE_CODE = `API_KEY = "super-secret"

def load_user(user_id, cache=[]):
    print("loading", user_id)
    cache.append(user_id)
    return cache
`;

const reviewForm = document.getElementById("review-form");
const codeInput = document.getElementById("code-input");
const languageSelect = document.getElementById("language-select");
const reviewModeSelect = document.getElementById("review-mode-select");
const focusInput = document.getElementById("focus-input");
const fileInput = document.getElementById("file-input");
const loadSampleBtn = document.getElementById("load-sample-btn");
const reviewBtn = document.getElementById("review-btn");
const reviewStatus = document.getElementById("review-status");
const evaluateBtn = document.getElementById("evaluate-btn");
const providerBadge = document.getElementById("provider-badge");
const summaryEmpty = document.getElementById("summary-empty");
const summaryGrid = document.getElementById("summary-grid");
const guidanceOutput = document.getElementById("guidance-output");
const activityOutput = document.getElementById("activity-output");
const resultEmpty = document.getElementById("result-empty");
const resultContent = document.getElementById("result-content");
const summaryText = document.getElementById("summary-text");
const issuesList = document.getElementById("issues-list");
const metricsGrid = document.getElementById("metrics-grid");
const suggestionsList = document.getElementById("suggestions-list");
const warningsList = document.getElementById("warnings-list");
const evalSummary = document.getElementById("eval-summary");
const evalResults = document.getElementById("eval-results");

function setStatus(message, kind = "") {
  reviewStatus.textContent = message;
  reviewStatus.className = `status ${kind}`.trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function titleCase(value) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderSummary(payload) {
  summaryEmpty.classList.add("hidden");
  summaryGrid.classList.remove("hidden");
  summaryGrid.innerHTML = `
    <article class="summary-card">
      <h3>Status</h3>
      <p class="summary-value">${escapeHtml(payload.status)}</p>
    </article>
    <article class="summary-card">
      <h3>Mode</h3>
      <p class="summary-value">${escapeHtml(payload.review_mode)}</p>
    </article>
    <article class="summary-card">
      <h3>Issues</h3>
      <p class="summary-value">${payload.issues.length}</p>
    </article>
    <article class="summary-card">
      <h3>Duration</h3>
      <p class="summary-value">${payload.duration_ms} ms</p>
    </article>
  `;
}

function renderGuidance(hits) {
  guidanceOutput.innerHTML = "";
  if (!hits || !hits.length) {
    guidanceOutput.innerHTML = '<div class="empty-state">No guidance retrieved.</div>';
    return;
  }

  hits.forEach((hit) => {
    const card = document.createElement("article");
    card.className = "guidance-card";
    card.innerHTML = `
      <div class="guidance-meta">
        <span class="pill">${escapeHtml(hit.category)}</span>
        <span class="score">score ${hit.score}</span>
      </div>
      <h3>${escapeHtml(hit.title)}</h3>
      <p>${escapeHtml(hit.excerpt)}</p>
    `;
    guidanceOutput.appendChild(card);
  });
}

function renderActivity(log) {
  activityOutput.innerHTML = "";
  if (!log || !log.length) {
    activityOutput.innerHTML = '<div class="empty-state">No activity recorded.</div>';
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
          <span class="event-pill">${escapeHtml(entry.event)}</span>
        </div>
      </div>
      <pre class="payload-block">${escapeHtml(payloadText)}</pre>
    `;
    activityOutput.appendChild(card);
  });
}

function renderIssues(issues) {
  issuesList.innerHTML = "";
  issues.forEach((issue) => {
    const item = document.createElement("li");
    item.className = `issue-card ${issue.severity}`;
    item.innerHTML = `
      <div class="issue-topline">
        <span class="pill severity ${escapeHtml(issue.severity)}">${escapeHtml(issue.severity)}</span>
        <span class="pill">${escapeHtml(issue.category)}</span>
        <span class="issue-line">${issue.line ? `line ${issue.line}` : "line n/a"}</span>
      </div>
      <p>${escapeHtml(issue.description)}</p>
      <p><strong>Suggestion:</strong> ${escapeHtml(issue.suggestion)}</p>
    `;
    issuesList.appendChild(item);
  });
}

function renderMetrics(metrics) {
  metricsGrid.innerHTML = "";
  Object.entries(metrics).forEach(([key, value]) => {
    const metric = document.createElement("div");
    metric.className = "metric-card";
    metric.innerHTML = `
      <span class="metric-label">${escapeHtml(titleCase(key))}</span>
      <span class="metric-value">${escapeHtml(value)}</span>
    `;
    metricsGrid.appendChild(metric);
  });
}

function renderSimpleList(element, items, emptyText) {
  element.innerHTML = "";
  if (!items || !items.length) {
    const empty = document.createElement("li");
    empty.textContent = emptyText;
    element.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    element.appendChild(li);
  });
}

function renderResult(payload) {
  resultEmpty.classList.add("hidden");
  resultContent.classList.remove("hidden");
  providerBadge.textContent = `Provider: ${payload.provider}`;
  summaryText.textContent = payload.summary;
  renderIssues(payload.issues || []);
  renderMetrics(payload.metrics || {});
  renderSimpleList(suggestionsList, payload.suggestions || [], "No suggestions.");
  renderSimpleList(warningsList, payload.warnings || [], "No warnings.");
}

function renderEvaluation(payload) {
  evalSummary.classList.add("hidden");
  evalResults.classList.remove("hidden");
  evalResults.innerHTML = `
    <article class="result-block">
      <h3>Evaluation Summary</h3>
      <div class="metrics-grid">
        <div class="metric-card">
          <span class="metric-label">Examples</span>
          <span class="metric-value">${payload.summary.example_count}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Avg Category Recall</span>
          <span class="metric-value">${payload.summary.avg_category_recall}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Issue Count Pass Rate</span>
          <span class="metric-value">${payload.summary.issue_count_pass_rate}</span>
        </div>
      </div>
    </article>
    ${payload.examples
      .map(
        (example) => `
      <article class="result-block">
        <h3>${escapeHtml(example.id)}</h3>
        <p class="structured-copy"><strong>Matched Categories:</strong> ${escapeHtml(example.matched_categories.join(", ") || "none")}</p>
        <p class="structured-copy"><strong>Returned Categories:</strong> ${escapeHtml(example.returned_categories.join(", ") || "none")}</p>
        <p class="structured-copy"><strong>Recall:</strong> ${example.category_recall}</p>
      </article>
    `
      )
      .join("")}
  `;
}

async function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read the selected file."));
    reader.readAsText(file);
  });
}

fileInput.addEventListener("change", async (event) => {
  const [file] = event.target.files || [];
  if (!file) {
    return;
  }

  try {
    codeInput.value = await readFileAsText(file);
    setStatus(`Loaded ${file.name}.`, "success");
  } catch (error) {
    setStatus(error.message || "Unable to load file.", "error");
  }
});

loadSampleBtn.addEventListener("click", () => {
  codeInput.value = SAMPLE_CODE;
  languageSelect.value = "python";
  reviewModeSelect.value = "deep";
  focusInput.value = "secret-handling, logging";
  setStatus("Sample code loaded.", "success");
});

reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  reviewBtn.disabled = true;
  setStatus("Running the review workflow...", "loading");

  try {
    const response = await fetch(`${API_BASE_URL}/api/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: codeInput.value.trim(),
        language: languageSelect.value,
        review_mode: reviewModeSelect.value,
        focus: focusInput.value
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Review failed.");
    }

    renderSummary(payload);
    renderGuidance(payload.knowledge_hits);
    renderActivity(payload.activity_log);
    renderResult(payload);
    setStatus("Review complete.", "success");
  } catch (error) {
    setStatus(error.message || "Something went wrong.", "error");
  } finally {
    reviewBtn.disabled = false;
  }
});

evaluateBtn.addEventListener("click", async () => {
  evaluateBtn.disabled = true;
  setStatus("Running the bundled evaluation set...", "loading");

  try {
    const response = await fetch(`${API_BASE_URL}/api/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Evaluation failed.");
    }

    renderEvaluation(payload);
    setStatus("Evaluation complete.", "success");
  } catch (error) {
    setStatus(error.message || "Evaluation request failed.", "error");
  } finally {
    evaluateBtn.disabled = false;
  }
});

codeInput.value = SAMPLE_CODE;
