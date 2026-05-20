const API_BASE_URL =
  (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000";

const form = document.getElementById("shortener-form");
const input = document.getElementById("url-input");
const status = document.getElementById("status");
const resultPanel = document.getElementById("result-panel");
const resultUrl = document.getElementById("result-url");
const submitBtn = document.getElementById("submit-btn");
const copyBtn = document.getElementById("copy-btn");
const refreshBtn = document.getElementById("refresh-btn");
const historyList = document.getElementById("history-list");
const historyEmpty = document.getElementById("history-empty");

let latestShortUrl = "";

function setStatus(message, kind = "") {
  status.textContent = message;
  status.className = `status ${kind}`.trim();
}

function renderHistory(items) {
  historyList.innerHTML = "";
  if (!items.length) {
    historyEmpty.style.display = "block";
    return;
  }

  historyEmpty.style.display = "none";

  for (const item of items) {
    const listItem = document.createElement("li");
    listItem.className = "history-item";

    const shortLink = document.createElement("a");
    shortLink.className = "history-short";
    shortLink.href = item.short_url;
    shortLink.textContent = item.short_url;
    shortLink.target = "_blank";
    shortLink.rel = "noreferrer";

    const original = document.createElement("div");
    original.className = "history-original";
    original.textContent = item.original_url;

    listItem.appendChild(shortLink);
    listItem.appendChild(original);
    historyList.appendChild(listItem);
  }
}

async function loadHistory() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/links`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Unable to load previous links");
    }
    renderHistory(data.links || []);
  } catch (error) {
    historyEmpty.textContent = error.message || "Could not load previous links right now.";
    historyEmpty.style.display = "block";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resultPanel.classList.remove("visible");
  copyBtn.disabled = true;
  setStatus("Creating short URL...", "loading");
  submitBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE_URL}/api/shorten`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: input.value.trim() })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Unable to shorten URL");
    }

    latestShortUrl = data.short_url;
    resultUrl.href = latestShortUrl;
    resultUrl.textContent = latestShortUrl;
    resultPanel.classList.add("visible");
    copyBtn.disabled = false;
    setStatus("Short URL created successfully.", "success");
    await loadHistory();
  } catch (error) {
    setStatus(error.message || "Something went wrong.", "error");
  } finally {
    submitBtn.disabled = false;
  }
});

copyBtn.addEventListener("click", async () => {
  if (!latestShortUrl) {
    return;
  }

  try {
    await navigator.clipboard.writeText(latestShortUrl);
    setStatus("Short URL copied to clipboard.", "success");
  } catch (error) {
    setStatus("Could not copy automatically. Please copy it manually.", "error");
  }
});

refreshBtn.addEventListener("click", () => {
  setStatus("Refreshing history...", "loading");
  loadHistory().finally(() => {
    setStatus("History refreshed.", "success");
  });
});

loadHistory();
