import unittest

from fastapi.testclient import TestClient

from main import app


class Lab03ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_migrate_endpoint_returns_structured_response(self) -> None:
        response = self.client.post(
            "/api/migrate",
            json={
                "source_framework": "flask",
                "target_framework": "fastapi",
                "source_files": [
                    {
                        "path": "app.py",
                        "content": (
                            "from flask import Flask, jsonify\n\n"
                            "app = Flask(__name__)\n\n"
                            "@app.route('/hello')\n"
                            "def hello():\n"
                            "    return jsonify({'message': 'hello'})\n"
                        ),
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_framework"], "flask")
        self.assertEqual(payload["target_framework"], "fastapi")
        self.assertIn("analysis_summary", payload)
        self.assertIn("plan", payload)
        self.assertIn("migrated_files", payload)
        self.assertIn("verification", payload)
        self.assertEqual(payload["provider"], "mock")
        self.assertTrue(payload["migrated_files"])
        self.assertIn("FastAPI", payload["migrated_files"][0]["content"])

    def test_unsupported_pair_is_rejected(self) -> None:
        response = self.client.post(
            "/api/migrate",
            json={
                "source_framework": "flask",
                "target_framework": "hono",
                "source_files": [{"path": "app.py", "content": "print('hi')"}],
            },
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
