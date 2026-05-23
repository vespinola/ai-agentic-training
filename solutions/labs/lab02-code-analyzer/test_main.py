import unittest

from fastapi.testclient import TestClient

from main import app


class Lab02ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_analyze_endpoint_returns_structured_response(self) -> None:
        response = self.client.post(
            "/api/analyze",
            json={
                "language": "python",
                "analysis_type": "security",
                "code": 'password = "secret"\nprint(password)\n',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["analysis_type"], "security")
        self.assertIn("summary", payload)
        self.assertIn("issues", payload)
        self.assertIn("suggestions", payload)
        self.assertIn("metrics", payload)
        self.assertTrue(payload["issues"])

    def test_unsupported_language_is_rejected(self) -> None:
        response = self.client.post(
            "/api/analyze",
            json={"language": "elixir", "analysis_type": "general", "code": "IO.puts(:ok)"},
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
