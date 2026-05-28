const API_BASE_URL =
  (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000";

const form = document.getElementById("migration-form");
const sourceFramework = document.getElementById("source-framework");
const targetFramework = document.getElementById("target-framework");
const addFileBtn = document.getElementById("add-file-btn");
const migrateBtn = document.getElementById("migrate-btn");
const filesList = document.getElementById("files-list");
const fileTemplate = document.getElementById("file-template");
const status = document.getElementById("status");
const resultEmpty = document.getElementById("result-empty");
const resultContent = document.getElementById("result-content");
const providerBadge = document.getElementById("provider-badge");
const analysisSummary = document.getElementById("analysis-summary");
const patternsList = document.getElementById("patterns-list");
const risksList = document.getElementById("risks-list");
const planList = document.getElementById("plan-list");
const filesOutput = document.getElementById("files-output");
const verificationSummary = document.getElementById("verification-summary");
const verificationIssues = document.getElementById("verification-issues");
const humanReview = document.getElementById("human-review");
const errorsList = document.getElementById("errors-list");
const phasePills = [...document.querySelectorAll(".phase-pill")];

let progressTimer = null;

function setStatus(message, kind = "") {
  status.textContent = message;
  status.className = `status ${kind}`.trim();
}

function resetPhases() {
  phasePills.forEach((pill) => {
    pill.classList.remove("active", "done");
  });
}

function setPhase(phase) {
  let activeFound = false;
  phasePills.forEach((pill) => {
    const matches = pill.dataset.phase === phase;
    pill.classList.toggle("active", matches);
    if (!activeFound && !matches && pill.classList.contains("done")) {
      return;
    }
    if (!activeFound && !matches) {
      pill.classList.remove("active");
    }
    if (matches) {
      activeFound = true;
    }
  });
}

function markPhasesComplete(finalPhase) {
  let reachedFinal = false;
  phasePills.forEach((pill) => {
    if (!reachedFinal) {
      pill.classList.add("done");
    }
    pill.classList.toggle("active", pill.dataset.phase === finalPhase);
    if (pill.dataset.phase === finalPhase) {
      reachedFinal = true;
    }
  });
}

function startProgressAnimation() {
  resetPhases();
  const phases = ["analysis", "planning", "execution", "verification"];
  let index = 0;
  setPhase(phases[index]);
  progressTimer = window.setInterval(() => {
    index = Math.min(index + 1, phases.length - 1);
    phasePills.forEach((pill, pillIndex) => {
      pill.classList.toggle("done", pillIndex < index);
      pill.classList.toggle("active", pillIndex === index);
    });
  }, 900);
}

function stopProgressAnimation(finalPhase) {
  if (progressTimer) {
    window.clearInterval(progressTimer);
    progressTimer = null;
  }
  markPhasesComplete(finalPhase);
}

function createFileCard(path = "", content = "") {
  const fragment = fileTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".file-card");
  const pathInput = fragment.querySelector(".file-path-input");
  const contentInput = fragment.querySelector(".file-content-input");
  const removeBtn = fragment.querySelector(".remove-file-btn");

  pathInput.value = path;
  contentInput.value = content;

  removeBtn.addEventListener("click", () => {
    if (filesList.children.length === 1) {
      pathInput.value = "";
      contentInput.value = "";
      return;
    }
    card.remove();
  });

  filesList.appendChild(fragment);
}

function readFilesFromForm() {
  return [...filesList.querySelectorAll(".file-card")]
    .map((card) => ({
      path: card.querySelector(".file-path-input").value.trim(),
      content: card.querySelector(".file-content-input").value.trim()
    }))
    .filter((file) => file.path && file.content);
}

function renderSimpleList(container, items, formatter) {
  container.innerHTML = "";
  if (!items || !items.length) {
    const empty = document.createElement("li");
    empty.textContent = "None.";
    container.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const node = document.createElement("li");
    node.innerHTML = formatter(item);
    container.appendChild(node);
  });
}

function renderPatterns(patterns) {
  patternsList.innerHTML = "";
  if (!patterns.length) {
    const item = document.createElement("li");
    item.className = "chip";
    item.textContent = "No strong patterns detected";
    patternsList.appendChild(item);
    return;
  }

  patterns.forEach((pattern) => {
    const item = document.createElement("li");
    item.className = "chip";
    item.textContent = pattern;
    patternsList.appendChild(item);
  });
}

function renderPlan(plan) {
  planList.innerHTML = "";
  plan.forEach((step) => {
    const item = document.createElement("li");
    item.className = `plan-step ${step.status}`;

    const title = document.createElement("div");
    title.className = "plan-step-title";
    title.textContent = `${step.id} · ${step.description}`;

    const meta = document.createElement("div");
    meta.className = "plan-step-meta";
    const dependencies = step.dependencies && step.dependencies.length ? step.dependencies.join(", ") : "none";
    meta.textContent = `${step.status} · complexity ${step.complexity} · depends on ${dependencies}`;

    item.appendChild(title);
    item.appendChild(meta);
    planList.appendChild(item);
  });
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderFileOutputs(sourceFiles, migratedFiles) {
  filesOutput.innerHTML = "";

  migratedFiles.forEach((file) => {
    const source = sourceFiles.find((item) => item.path === file.path);
    const wrapper = document.createElement("article");
    wrapper.className = "diff-card";

    const header = document.createElement("div");
    header.className = "block-header";
    header.innerHTML = `<h4>${file.path}</h4><span class="diff-summary">${file.summary}</span>`;

    const grid = document.createElement("div");
    grid.className = "diff-grid";
    grid.innerHTML = `
      <section>
        <h5>Before</h5>
        <pre><code>${escapeHtml((source && source.content) || "")}</code></pre>
      </section>
      <section>
        <h5>After</h5>
        <pre><code>${escapeHtml(file.content || "")}</code></pre>
      </section>
    `;

    wrapper.appendChild(header);
    wrapper.appendChild(grid);
    filesOutput.appendChild(wrapper);
  });
}

function applyPairDefaults() {
  if (sourceFramework.value === "flask") {
    targetFramework.value = "fastapi";
  } else if (sourceFramework.value === "express") {
    targetFramework.value = "hono";
  }
}

function seedDefaultExample() {
  createFileCard(
    "app.py",
    [
      "from flask import Flask, jsonify",
      "",
      "app = Flask(__name__)",
      "",
      "@app.route(\"/hello\")",
      "def hello():",
      "    return jsonify({\"message\": \"hello\"})"
    ].join("\n")
  );
}

addFileBtn.addEventListener("click", () => createFileCard());
sourceFramework.addEventListener("change", applyPairDefaults);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const sourceFiles = readFilesFromForm();
  if (!sourceFiles.length) {
    setStatus("Add at least one file with both path and content.", "error");
    return;
  }

  migrateBtn.disabled = true;
  setStatus("Running migration workflow...", "loading");
  startProgressAnimation();

  try {
    const response = await fetch(`${API_BASE_URL}/api/migrate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_framework: sourceFramework.value,
        target_framework: targetFramework.value,
        source_files: sourceFiles
      })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || payload.error || "Migration failed.");
    }

    providerBadge.textContent = payload.provider;
    analysisSummary.textContent = payload.analysis_summary;
    renderPatterns(payload.detected_patterns || []);
    renderSimpleList(
      risksList,
      payload.risks || [],
      (risk) => `<strong>${risk.severity}</strong> · ${risk.area}: ${risk.description}`
    );
    renderPlan(payload.plan || []);
    renderFileOutputs(sourceFiles, payload.migrated_files || []);
    verificationSummary.textContent = payload.verification.summary;
    renderSimpleList(
      verificationIssues,
      payload.verification.issues || [],
      (issue) =>
        `<strong>${issue.severity}</strong>${issue.file_path ? ` · ${issue.file_path}` : ""}: ${issue.description}<br /><span>${issue.suggestion}</span>`
    );
    renderSimpleList(
      humanReview,
      payload.verification.human_review || [],
      (item) => item
    );
    renderSimpleList(errorsList, payload.errors || [], (item) => item);

    resultEmpty.classList.add("hidden");
    resultContent.classList.remove("hidden");
    stopProgressAnimation(payload.phase || "verification");
    setStatus(payload.success ? "Migration complete." : "Migration completed with follow-up items.", payload.success ? "success" : "error");
  } catch (error) {
    if (progressTimer) {
      window.clearInterval(progressTimer);
      progressTimer = null;
    }
    resetPhases();
    setStatus(error.message || "Something went wrong.", "error");
  } finally {
    migrateBtn.disabled = false;
  }
});

seedDefaultExample();
applyPairDefaults();
