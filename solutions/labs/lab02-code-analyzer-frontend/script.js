const API_BASE_URL =
  (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000";

const form = document.getElementById("analyzer-form");
const languageSelect = document.getElementById("language-select");
const analysisTypeSelect = document.getElementById("analysis-type-select");
const fileInput = document.getElementById("file-input");
const codeInput = document.getElementById("code-input");
const analyzeBtn = document.getElementById("analyze-btn");
const status = document.getElementById("status");
const resultEmpty = document.getElementById("result-empty");
const resultContent = document.getElementById("result-content");
const summaryText = document.getElementById("summary-text");
const issuesList = document.getElementById("issues-list");
const suggestionsList = document.getElementById("suggestions-list");
const metricsGrid = document.getElementById("metrics-grid");
const providerBadge = document.getElementById("provider-badge");

function setStatus(message, kind = "") {
  status.textContent = message;
  status.className = `status ${kind}`.trim();
}

function titleCase(value) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderIssues(issues) {
  issuesList.innerHTML = "";

  for (const issue of issues) {
    const item = document.createElement("li");
    item.className = `issue-card ${issue.severity}`;

    const meta = document.createElement("div");
    meta.className = "issue-meta";
    meta.textContent = `${issue.severity} · ${issue.category}${issue.line ? ` · line ${issue.line}` : ""}`;

    const description = document.createElement("p");
    description.textContent = issue.description;

    const suggestion = document.createElement("p");
    suggestion.innerHTML = `<strong>Suggestion:</strong> ${issue.suggestion}`;

    item.appendChild(meta);
    item.appendChild(description);
    item.appendChild(suggestion);
    issuesList.appendChild(item);
  }
}

function renderSuggestions(suggestions) {
  suggestionsList.innerHTML = "";

  for (const suggestion of suggestions) {
    const item = document.createElement("li");
    item.textContent = suggestion;
    suggestionsList.appendChild(item);
  }
}

function renderMetrics(metrics) {
  metricsGrid.innerHTML = "";

  Object.entries(metrics).forEach(([key, value]) => {
    const card = document.createElement("div");
    card.className = "metric";

    const label = document.createElement("span");
    label.className = "metric-label";
    label.textContent = titleCase(key);

    const metricValue = document.createElement("span");
    metricValue.className = "metric-value";
    metricValue.textContent = value;

    card.appendChild(label);
    card.appendChild(metricValue);
    metricsGrid.appendChild(card);
  });
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
    const content = await readFileAsText(file);
    codeInput.value = content;
    setStatus(`Loaded ${file.name}.`, "success");
  } catch (error) {
    setStatus(error.message || "Unable to load file.", "error");
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  analyzeBtn.disabled = true;
  setStatus("Analyzing code...", "loading");

  try {
    const response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: languageSelect.value,
        analysis_type: analysisTypeSelect.value,
        code: codeInput.value.trim()
      })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || payload.error || "Analysis failed.");
    }

    summaryText.textContent = payload.summary;
    providerBadge.textContent = payload.provider;
    renderIssues(payload.issues || []);
    renderSuggestions(payload.suggestions || []);
    renderMetrics(payload.metrics || {});
    resultEmpty.classList.add("hidden");
    resultContent.classList.remove("hidden");
    setStatus("Analysis complete.", "success");
  } catch (error) {
    setStatus(error.message || "Something went wrong.", "error");
  } finally {
    analyzeBtn.disabled = false;
  }
});
