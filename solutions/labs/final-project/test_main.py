import unittest

from fastapi.testclient import TestClient

from main import app


class FinalProjectApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("provider", payload)

    def test_review_endpoint_returns_trace_and_guidance(self) -> None:
        response = self.client.post(
            "/api/review",
            json={
                "language": "python",
                "review_mode": "deep",
                "code": 'API_KEY = "secret"\nprint(API_KEY)\n',
                "focus": ["secret-handling"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["status"], "completed")
        self.assertTrue(payload["activity_log"])
        self.assertTrue(payload["knowledge_hits"])
        self.assertIn("validator", payload["workers_used"])
        self.assertTrue(payload["issues"])

    def test_unsupported_language_is_rejected(self) -> None:
        response = self.client.post(
            "/api/review",
            json={"language": "elixir", "review_mode": "general", "code": "IO.puts(:ok)"},
        )
        self.assertEqual(response.status_code, 400)

    def test_evaluate_endpoint_runs_default_dataset(self) -> None:
        response = self.client.post("/api/evaluate", json={})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["summary"]["example_count"], 1)
        self.assertTrue(payload["examples"])


if __name__ == "__main__":
    unittest.main()
