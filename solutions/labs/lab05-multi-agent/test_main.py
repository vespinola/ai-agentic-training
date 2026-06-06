import unittest

from fastapi.testclient import TestClient

from main import app


class Lab05ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("provider", payload)

    def test_run_workflow_returns_trace_and_final_output(self) -> None:
        response = self.client.post(
            "/api/run",
            json={
                "task": "Explain how vector databases work for a junior backend developer and include practical tradeoffs.",
                "max_iterations": 5,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn(payload["status"], {"completed", "max_iterations_reached"})
        self.assertTrue(payload["activity_log"])
        self.assertIn("researcher", payload["workers_used"])
        self.assertIn("writer", payload["workers_used"])
        self.assertIn("reviewer", payload["workers_used"])
        self.assertTrue(payload["final_output"])
        self.assertIsNotNone(payload["review_result"])

    def test_request_validation_rejects_too_short_task(self) -> None:
        response = self.client.post("/api/run", json={"task": "short", "max_iterations": 5})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
