const API_BASE_URL =
  (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000";

const SAMPLE_FILES = [
  {
    path: "auth.py",
    content: [
      "import hashlib",
      "import hmac",
      "import time",
      "",
      "SECRET_KEY = \"demo-secret\"",
      "",
      "def hash_password(password: str) -> str:",
      "    return hashlib.sha256(password.encode(\"utf-8\")).hexdigest()",
      "",
      "def verify_password(password: str, password_hash: str) -> bool:",
      "    return hmac.compare_digest(hash_password(password), password_hash)",
      "",
      "def create_token(user_id: int) -> str:",
      "    issued_at = int(time.time())",
      "    return f\"{user_id}:{issued_at}:{SECRET_KEY}\"",
      "",
      "def parse_token(token: str) -> dict:",
      "    user_id, issued_at, signature = token.split(\":\")",
      "    return {\"user_id\": int(user_id), \"issued_at\": int(issued_at), \"signature\": signature}"
    ].join("\n")
  },
  {
    path: "users.py",
    content: [
      "from auth import create_token, hash_password",
      "",
      "USERS = []",
      "",
      "def create_user(email: str, password: str) -> dict:",
      "    user = {\"id\": len(USERS) + 1, \"email\": email, \"password_hash\": hash_password(password)}",
      "    USERS.append(user)",
      "    return {\"user\": user, \"token\": create_token(user[\"id\"])}",
      "",
      "def find_user_by_email(email: str) -> dict | None:",
      "    for user in USERS:",
      "        if user[\"email\"] == email:",
      "            return user",
      "    return None",
      "",
      "def login(email: str, password: str) -> dict | None:",
      "    user = find_user_by_email(email)",
      "    if not user:",
      "        return None",
      "    if user[\"password_hash\"] != hash_password(password):",
      "        return None",
      "    return {\"token\": create_token(user[\"id\"]), \"user\": user}"
    ].join("\n")
  },
  {
    path: "app.py",
    content: [
      "from users import create_user, find_user_by_email, login",
      "",
      "def register_handler(payload: dict) -> dict:",
      "    required = {\"email\", \"password\"}",
      "    if not required.issubset(payload):",
      "        return {\"error\": \"missing required fields\"}",
      "    return create_user(payload[\"email\"], payload[\"password\"])",
      "",
      "def login_handler(payload: dict) -> dict:",
      "    result = login(payload[\"email\"], payload[\"password\"])",
      "    if not result:",
      "        return {\"error\": \"invalid credentials\"}",
      "    return result",
      "",
      "def user_lookup_handler(email: str) -> dict:",
      "    user = find_user_by_email(email)",
      "    if not user:",
      "        return {\"error\": \"user not found\"}",
      "    return user",
      "",
      "def health_handler() -> dict:",
      "    return {\"status\": \"ok\", \"service\": \"sample-code-rag\"}"
    ].join("\n")
  }
];

const SAMPLE_EVAL_DATASET = [
  {
    id: "q1",
    question: "Which function hashes passwords?",
    expected_answer: "Password hashing is implemented in auth.py by the hash_password function.",
    relevant_docs: ["auth.py::function::hash_password::8"]
  },
  {
    id: "q2",
    question: "Where is password verification handled?",
    expected_answer: "Password verification is handled in auth.py by verify_password.",
    relevant_docs: ["auth.py::function::verify_password::10"]
  },
  {
    id: "q3",
    question: "Which function creates auth tokens?",
    expected_answer: "Token creation happens in auth.py inside create_token.",
    relevant_docs: ["auth.py::function::create_token::13"]
  },
  {
    id: "q4",
    question: "Where is a token parsed into user_id and issued_at?",
    expected_answer: "Token parsing is implemented in auth.py by parse_token.",
    relevant_docs: ["auth.py::function::parse_token::17"]
  },
  {
    id: "q5",
    question: "Which function creates a user record and returns a token?",
    expected_answer: "User creation is implemented in users.py by create_user, which returns both the user and a token.",
    relevant_docs: ["users.py::function::create_user::5"]
  },
  {
    id: "q6",
    question: "Where does the code search for a user by email?",
    expected_answer: "Email lookup is handled in users.py by find_user_by_email.",
    relevant_docs: ["users.py::function::find_user_by_email::10"]
  },
  {
    id: "q7",
    question: "Which function logs a user in?",
    expected_answer: "Login logic is implemented in users.py by the login function.",
    relevant_docs: ["users.py::function::login::16"]
  },
  {
    id: "q8",
    question: "Where are required registration fields checked?",
    expected_answer: "Registration field validation is done in app.py by register_handler.",
    relevant_docs: ["app.py::function::register_handler::3"]
  },
  {
    id: "q9",
    question: "Which function returns invalid credentials when login fails?",
    expected_answer: "The invalid credentials response is returned by login_handler in app.py.",
    relevant_docs: ["app.py::function::login_handler::9"]
  },
  {
    id: "q10",
    question: "Where is the sample service health response defined?",
    expected_answer: "The health response is defined in app.py by health_handler.",
    relevant_docs: ["app.py::function::health_handler::21"]
  }
];

const fileTemplate = document.getElementById("file-template");
const filesList = document.getElementById("files-list");
const hiddenFileInput = document.getElementById("hidden-file-input");
const addFileBtn = document.getElementById("add-file-btn");
const uploadFileBtn = document.getElementById("upload-file-btn");
const loadSampleBtn = document.getElementById("load-sample-btn");
const indexForm = document.getElementById("index-form");
const indexBtn = document.getElementById("index-btn");
const indexStatus = document.getElementById("index-status");
const indexSummary = document.getElementById("index-summary");
const queryForm = document.getElementById("query-form");
const questionInput = document.getElementById("question-input");
const topKInput = document.getElementById("top-k-input");
const queryBtn = document.getElementById("query-btn");
const queryStatus = document.getElementById("query-status");
const queryEmpty = document.getElementById("query-empty");
const queryResult = document.getElementById("query-result");
const providerBadge = document.getElementById("provider-badge");
const answerOutput = document.getElementById("answer-output");
const sourcesOutput = document.getElementById("sources-output");
const evaluateBtn = document.getElementById("evaluate-btn");
const evalStatus = document.getElementById("eval-status");
const evalEmpty = document.getElementById("eval-empty");
const evalResult = document.getElementById("eval-result");
const metricsGrid = document.getElementById("metrics-grid");
const examplesOutput = document.getElementById("examples-output");
const datasetBadge = document.getElementById("dataset-badge");

let usingSampleDataset = false;

function setStatus(element, message, kind = "") {
  element.textContent = message;
  element.className = `status ${kind}`.trim();
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

function resetFiles() {
  filesList.innerHTML = "";
}

function loadSampleFiles() {
  resetFiles();
  SAMPLE_FILES.forEach((file) => createFileCard(file.path, file.content));
  questionInput.value = "Which function creates auth tokens?";
  usingSampleDataset = true;
  setStatus(indexStatus, "Sample codebase loaded. Index it to continue.", "success");
}

async function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsText(file);
  });
}

function readFilesFromForm() {
  return [...filesList.querySelectorAll(".file-card")]
    .map((card) => ({
      path: card.querySelector(".file-path-input").value.trim(),
      content: card.querySelector(".file-content-input").value.trim()
    }))
    .filter((file) => file.path && file.content);
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderIndexSummary(payload) {
  indexSummary.classList.remove("hidden");
  indexSummary.innerHTML = `
    <strong>Index ready.</strong>
    <span>${payload.indexed_files} file(s), ${payload.chunk_count} chunk(s)</span>
    <span>Languages: ${payload.languages.join(", ")}</span>
    <span>Strategy: ${payload.chunking_strategy}</span>
  `;
}

function renderSources(sources) {
  sourcesOutput.innerHTML = "";
  if (!sources.length) {
    sourcesOutput.innerHTML = "<p>No sources retrieved.</p>";
    return;
  }

  sources.forEach((source) => {
    const article = document.createElement("article");
    article.className = "source-card";
    article.innerHTML = `
      <div class="block-header">
        <h4>${source.file_path}${source.symbol_name ? `::${source.symbol_name}` : ""}</h4>
        <span class="source-score">score ${source.score}</span>
      </div>
      <p class="source-meta">${source.chunk_type} · lines ${source.line_start}-${source.line_end}</p>
      <pre><code>${escapeHtml(source.snippet)}</code></pre>
    `;
    sourcesOutput.appendChild(article);
  });
}

function renderMetrics(summary) {
  const metrics = [
    ["Examples", summary.example_count],
    ["Avg Precision@K", summary.avg_precision_at_k],
    ["Avg Recall@K", summary.avg_recall_at_k],
    ["Avg MRR", summary.avg_mrr],
    ["Avg Relevance", summary.avg_relevance],
    ["Avg Faithfulness", summary.avg_faithfulness],
    ["Avg Correctness", summary.avg_correctness]
  ];

  metricsGrid.innerHTML = "";
  metrics.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "metric-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    metricsGrid.appendChild(card);
  });
}

function renderJudgeScores(scores) {
  return scores
    .map(
      (score) => `
        <li><strong>${score.dimension}</strong>: ${score.rating}/5<br /><span>${score.explanation}</span></li>
      `
    )
    .join("");
}

function getJudgeScore(scores, dimension) {
  return scores.find((score) => score.dimension === dimension)?.rating ?? "-";
}

function summarizeText(text, maxLength = 120) {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength).trim()}...`;
}

function renderExampleResults(examples) {
  examplesOutput.innerHTML = "";
  examples.forEach((example) => {
    const article = document.createElement("details");
    article.className = "example-card";

    const relevance = getJudgeScore(example.judge_scores, "relevance");
    const faithfulness = getJudgeScore(example.judge_scores, "faithfulness");
    const correctness = getJudgeScore(example.judge_scores, "correctness");

    article.innerHTML = `
      <summary class="example-summary">
        <div class="example-summary-main">
          <h4>${example.id} · ${example.question}</h4>
          <p>${summarizeText(example.generated_answer, 110)}</p>
        </div>
        <div class="example-summary-metrics">
          <span>R ${relevance}/5</span>
          <span>F ${faithfulness}/5</span>
          <span>C ${correctness}/5</span>
        </div>
      </summary>
      <div class="example-details">
        <p><strong>Expected:</strong> ${example.expected_answer}</p>
        <p><strong>Generated:</strong> ${example.generated_answer}</p>
        <p><strong>Retrieved IDs:</strong> ${example.retrieved_doc_ids.join(", ") || "None"}</p>
        <p><strong>Relevant IDs:</strong> ${example.relevant_doc_ids.join(", ")}</p>
        <div class="mini-metrics">
          <span>Precision@K ${example.metrics.precision_at_k}</span>
          <span>Recall@K ${example.metrics.recall_at_k}</span>
          <span>MRR ${example.metrics.mrr}</span>
        </div>
        <ul class="judge-list">${renderJudgeScores(example.judge_scores)}</ul>
      </div>
    `;
    examplesOutput.appendChild(article);
  });
}

addFileBtn.addEventListener("click", () => createFileCard());
uploadFileBtn.addEventListener("click", () => hiddenFileInput.click());
loadSampleBtn.addEventListener("click", loadSampleFiles);

hiddenFileInput.addEventListener("change", async (event) => {
  const files = [...(event.target.files || [])];
  if (!files.length) {
    return;
  }

  try {
    for (const file of files) {
      const content = await readFileAsText(file);
      createFileCard(file.name, content);
    }
    usingSampleDataset = false;
    setStatus(indexStatus, `Loaded ${files.length} file(s).`, "success");
  } catch (error) {
    setStatus(indexStatus, error.message || "Unable to load file.", "error");
  } finally {
    hiddenFileInput.value = "";
  }
});

indexForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = readFilesFromForm();
  if (!files.length) {
    setStatus(indexStatus, "Add at least one file with both path and content.", "error");
    return;
  }

  indexBtn.disabled = true;
  setStatus(indexStatus, "Indexing files and building chunks...", "loading");

  try {
    const response = await fetch(`${API_BASE_URL}/api/index/files`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Indexing failed.");
    }

    renderIndexSummary(payload);
    setStatus(indexStatus, "Index complete. You can query and evaluate now.", "success");
  } catch (error) {
    setStatus(indexStatus, error.message || "Indexing failed.", "error");
  } finally {
    indexBtn.disabled = false;
  }
});

queryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  const topK = Number(topKInput.value || 4);
  if (!question) {
    setStatus(queryStatus, "Enter a question first.", "error");
    return;
  }

  queryBtn.disabled = true;
  setStatus(queryStatus, "Running retrieval and grounded answer generation...", "loading");

  try {
    const response = await fetch(`${API_BASE_URL}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topK })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Query failed.");
    }

    providerBadge.textContent = payload.provider;
    answerOutput.textContent = payload.answer;
    renderSources(payload.sources || []);
    queryEmpty.classList.add("hidden");
    queryResult.classList.remove("hidden");
    setStatus(queryStatus, `Retrieved ${payload.sources.length} source chunk(s).`, "success");
  } catch (error) {
    setStatus(queryStatus, error.message || "Query failed.", "error");
  } finally {
    queryBtn.disabled = false;
  }
});

evaluateBtn.addEventListener("click", async () => {
  const topK = Number(topKInput.value || 4);
  evaluateBtn.disabled = true;
  setStatus(evalStatus, "Running retrieval metrics and judge scoring...", "loading");

  try {
    const response = await fetch(`${API_BASE_URL}/api/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        examples: usingSampleDataset ? SAMPLE_EVAL_DATASET : [],
        top_k: topK
      })
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Evaluation failed.");
    }

    renderMetrics(payload.summary);
    renderExampleResults(payload.examples || []);
    datasetBadge.textContent = payload.dataset_name;
    evalEmpty.classList.add("hidden");
    evalResult.classList.remove("hidden");
    setStatus(evalStatus, `Evaluation complete for ${payload.summary.example_count} example(s).`, "success");
  } catch (error) {
    setStatus(evalStatus, error.message || "Evaluation failed.", "error");
  } finally {
    evaluateBtn.disabled = false;
  }
});

loadSampleFiles();
