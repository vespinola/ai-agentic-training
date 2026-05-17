from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

from app import ShortenerHandler, URLRepository, create_short_url, is_valid_url


class URLShortenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.repository = URLRepository(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validates_urls(self) -> None:
        self.assertTrue(is_valid_url("https://example.com"))
        self.assertTrue(is_valid_url("http://example.com/path"))
        self.assertFalse(is_valid_url("example.com"))
        self.assertFalse(is_valid_url("javascript:alert(1)"))

    def test_creates_six_character_short_code(self) -> None:
        entry = create_short_url(self.repository, "https://example.com")
        self.assertEqual(len(entry["short_code"]), 6)

    def test_duplicate_url_returns_existing_code(self) -> None:
        first = create_short_url(self.repository, "https://example.com")
        second = create_short_url(self.repository, "https://example.com")
        self.assertEqual(first["short_code"], second["short_code"])

    def test_invalid_url_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            create_short_url(self.repository, "not-a-url")


class URLShortenerHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.database_path = Path(cls.temp_dir.name) / "test.db"
        cls.repository = URLRepository(cls.database_path)
        ShortenerHandler.repository = cls.repository

        try:
            cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ShortenerHandler)
        except PermissionError as exc:
            raise unittest.SkipTest(f"Socket binding not available in this environment: {exc}") from exc

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "server"):
            cls.server.shutdown()
            cls.server.server_close()
            cls.server_thread.join(timeout=1)
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def test_post_shorten_returns_created_short_url(self) -> None:
        payload = json.dumps({"url": "https://example.com"}).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/shorten",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(req) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertEqual(response.status, 201)
        self.assertEqual(len(body["short_code"]), 6)
        self.assertTrue(body["short_url"].startswith(f"{self.base_url}/"))

    def test_post_shorten_rejects_invalid_url(self) -> None:
        payload = json.dumps({"url": "not-a-url"}).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/shorten",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(error.HTTPError) as context:
            request.urlopen(req)

        self.assertEqual(context.exception.code, 400)
        error_body = json.loads(context.exception.read().decode("utf-8"))
        self.assertIn("valid http or https URL", error_body["error"])


if __name__ == "__main__":
    unittest.main()
