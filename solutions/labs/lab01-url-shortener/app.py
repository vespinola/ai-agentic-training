#!/usr/bin/env python3
"""Small local URL shortener for Lab 01."""

from __future__ import annotations

import json
import secrets
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "url_shortener.db"
ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>URL Shortener</title>
  <style>
    :root {
      --bg: #f7f3ea;
      --panel: #fffdf8;
      --ink: #1f2933;
      --muted: #667085;
      --accent: #d06b2f;
      --accent-dark: #8f4619;
      --border: #eadcc9;
      --success: #0f9d58;
      --error: #c62828;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(208, 107, 47, 0.12), transparent 32%),
        linear-gradient(180deg, #f5efe4 0%, var(--bg) 100%);
      color: var(--ink);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }

    .card {
      width: min(680px, 100%);
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: 0 20px 50px rgba(70, 43, 21, 0.08);
      padding: 32px;
    }

    h1 {
      margin: 0 0 12px;
      font-size: clamp(2rem, 4vw, 3rem);
      line-height: 1;
      letter-spacing: -0.04em;
    }

    p {
      margin: 0 0 24px;
      color: var(--muted);
      line-height: 1.6;
    }

    form {
      display: grid;
      gap: 12px;
    }

    input {
      width: 100%;
      padding: 16px 18px;
      border-radius: 14px;
      border: 1px solid var(--border);
      font-size: 1rem;
      color: var(--ink);
    }

    input:focus {
      outline: 2px solid rgba(208, 107, 47, 0.25);
      border-color: var(--accent);
    }

    .actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 14px 18px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
    }

    .primary {
      background: var(--accent);
      color: white;
    }

    .primary:hover {
      background: var(--accent-dark);
    }

    .secondary {
      background: #f3e2d6;
      color: var(--accent-dark);
    }

    .panel {
      margin-top: 20px;
      padding: 16px;
      border-radius: 16px;
      background: #fff8ef;
      border: 1px solid var(--border);
      display: none;
    }

    .panel.visible {
      display: block;
    }

    .result-url {
      word-break: break-all;
      font-weight: 700;
      color: var(--accent-dark);
    }

    .status {
      min-height: 24px;
      margin-top: 12px;
      font-size: 0.95rem;
    }

    .status.loading { color: var(--muted); }
    .status.error { color: var(--error); }
    .status.success { color: var(--success); }

    @media (max-width: 640px) {
      .card { padding: 24px; }
      .actions { flex-direction: column; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <main class="card">
    <h1>Shorten a URL</h1>
    <p>Paste a long link, generate a clean short code, and copy the result.</p>

    <form id="shortener-form">
      <input
        id="url-input"
        type="url"
        name="url"
        placeholder="https://example.com/very/long/url"
        required
      />
      <div class="actions">
        <button class="primary" id="submit-btn" type="submit">Create Short URL</button>
        <button class="secondary" id="copy-btn" type="button" disabled>Copy Result</button>
      </div>
    </form>

    <div class="status" id="status"></div>

    <section class="panel" id="result-panel">
      <div>Short URL</div>
      <a class="result-url" id="result-url" href="#" target="_blank" rel="noreferrer"></a>
    </section>
  </main>

  <script>
    const form = document.getElementById("shortener-form");
    const input = document.getElementById("url-input");
    const status = document.getElementById("status");
    const resultPanel = document.getElementById("result-panel");
    const resultUrl = document.getElementById("result-url");
    const submitBtn = document.getElementById("submit-btn");
    const copyBtn = document.getElementById("copy-btn");

    let latestShortUrl = "";

    function setStatus(message, kind = "") {
      status.textContent = message;
      status.className = `status ${kind}`.trim();
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      resultPanel.classList.remove("visible");
      copyBtn.disabled = true;
      setStatus("Creating short URL...", "loading");
      submitBtn.disabled = true;

      try {
        const response = await fetch("/api/shorten", {
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
      } catch (error) {
        setStatus(error.message || "Something went wrong.", "error");
      } finally {
        submitBtn.disabled = false;
      }
    });

    copyBtn.addEventListener("click", async () => {
      if (!latestShortUrl) return;
      try {
        await navigator.clipboard.writeText(latestShortUrl);
        setStatus("Short URL copied to clipboard.", "success");
      } catch (error) {
        setStatus("Could not copy automatically. Please copy it manually.", "error");
      }
    });
  </script>
</body>
</html>
"""


def is_valid_url(raw_url: str) -> bool:
    parsed = urlparse(raw_url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class URLRepository:
    """Small SQLite-backed storage for URL mappings."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_url TEXT NOT NULL UNIQUE,
                    short_code TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def get_by_url(self, original_url: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT original_url, short_code FROM urls WHERE original_url = ?",
                (original_url,),
            ).fetchone()
        return dict(row) if row else None

    def get_by_code(self, short_code: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT original_url, short_code FROM urls WHERE short_code = ?",
                (short_code,),
            ).fetchone()
        return dict(row) if row else None

    def create(self, original_url: str, short_code: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO urls (original_url, short_code) VALUES (?, ?)",
                (original_url, short_code),
            )
            connection.commit()
        return {"original_url": original_url, "short_code": short_code}


def generate_short_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def create_short_url(repository: URLRepository, original_url: str) -> dict[str, Any]:
    if not is_valid_url(original_url):
        raise ValueError("Please provide a valid http or https URL.")

    existing = repository.get_by_url(original_url)
    if existing:
        return existing

    for _ in range(10):
        short_code = generate_short_code()
        if repository.get_by_code(short_code) is None:
            return repository.create(original_url, short_code)

    raise RuntimeError("Could not generate a unique short code.")


def build_base_url(handler: BaseHTTPRequestHandler) -> str:
    host = handler.headers.get("Host", "127.0.0.1:8000")
    return f"http://{host}"


class ShortenerHandler(BaseHTTPRequestHandler):
    repository = URLRepository(DATABASE_PATH)

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return

        short_code = self.path.lstrip("/")
        if not short_code or "/" in short_code:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return

        entry = self.repository.get_by_code(short_code)
        if entry is None:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return

        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", entry["original_url"])
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._respond_html(INDEX_HTML)
            return

        short_code = self.path.lstrip("/")
        if not short_code or "/" in short_code:
            self._respond_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return

        entry = self.repository.get_by_code(short_code)
        if entry is None:
            self._respond_json({"error": "Short code not found."}, HTTPStatus.NOT_FOUND)
            return

        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", entry["original_url"])
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/shorten":
            self._respond_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b""

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._respond_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
            return

        original_url = str(payload.get("url", "")).strip()
        try:
            entry = create_short_url(self.repository, original_url)
        except ValueError as exc:
            self._respond_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except RuntimeError as exc:
            self._respond_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        short_url = f"{build_base_url(self)}/{entry['short_code']}"
        self._respond_json(
            {"short_code": entry["short_code"], "short_url": short_url},
            HTTPStatus.CREATED,
        )

    def _respond_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _respond_json(self, data: dict[str, Any], status: HTTPStatus) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), ShortenerHandler)
    print("URL shortener running at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    run()
