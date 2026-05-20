#!/usr/bin/env python3
"""Railway-ready backend for the Lab 01 URL shortener."""

from __future__ import annotations

import json
import os
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
CORS_ALLOW_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "*")


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

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT original_url, short_code, created_at
                FROM urls
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


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
    forwarded_proto = handler.headers.get("X-Forwarded-Proto")
    scheme = forwarded_proto or "http"
    host = handler.headers.get("Host", "127.0.0.1:8000")
    return f"{scheme}://{host}"


class ShortenerHandler(BaseHTTPRequestHandler):
    repository = URLRepository(DATABASE_PATH)

    def log_message(self, format: str, *args: object) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path in {"/", "/health"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
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
        if self.path == "/" or self.path == "/health":
            self._respond_json(
                {
                    "status": "ok",
                    "service": "lab01-url-shortener-backend",
                    "endpoints": ["/api/shorten", "/api/links", "/health", "/{short_code}"],
                },
                HTTPStatus.OK,
            )
            return

        if self.path == "/api/links":
            base_url = build_base_url(self)
            links = [
                {
                    "original_url": entry["original_url"],
                    "short_code": entry["short_code"],
                    "short_url": f"{base_url}/{entry['short_code']}",
                    "created_at": entry["created_at"],
                }
                for entry in self.repository.list_recent()
            ]
            self._respond_json({"links": links}, HTTPStatus.OK)
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
            {
                "short_code": entry["short_code"],
                "short_url": short_url,
                "original_url": entry["original_url"],
            },
            HTTPStatus.CREATED,
        )

    def _respond_json(self, data: dict[str, Any], status: HTTPStatus) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run() -> None:
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ShortenerHandler)
    print(f"URL shortener backend running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
