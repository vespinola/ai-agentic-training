import unittest

from fastapi.testclient import TestClient

from main import app, rag_service


class Lab04ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        rag_service.store.replace([])
        self.sample_files = [
            {
                "path": "auth.py",
                "content": (
                    "import hashlib\n"
                    "import hmac\n"
                    "import time\n\n"
                    "SECRET_KEY = \"demo-secret\"\n\n"
                    "def hash_password(password: str) -> str:\n"
                    "    return hashlib.sha256(password.encode(\"utf-8\")).hexdigest()\n\n"
                    "def verify_password(password: str, password_hash: str) -> bool:\n"
                    "    return hmac.compare_digest(hash_password(password), password_hash)\n\n"
                    "def create_token(user_id: int) -> str:\n"
                    "    issued_at = int(time.time())\n"
                    "    return f\"{user_id}:{issued_at}:{SECRET_KEY}\"\n"
                ),
            },
            {
                "path": "app.py",
                "content": (
                    "def health_handler() -> dict:\n"
                    "    return {\"status\": \"ok\", \"service\": \"sample-code-rag\"}\n"
                ),
            },
        ]

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_index_query_and_evaluate_flow(self) -> None:
        index_response = self.client.post("/api/index/files", json={"files": self.sample_files})
        self.assertEqual(index_response.status_code, 200)
        index_payload = index_response.json()
        self.assertGreaterEqual(index_payload["chunk_count"], 2)

        query_response = self.client.post(
            "/api/query",
            json={"question": "Which function creates auth tokens?", "top_k": 3},
        )
        self.assertEqual(query_response.status_code, 200)
        query_payload = query_response.json()
        self.assertIn("answer", query_payload)
        self.assertTrue(query_payload["sources"])

        eval_response = self.client.post(
            "/api/evaluate",
            json={
                "examples": [
                    {
                        "id": "q1",
                        "question": "Which function creates auth tokens?",
                        "expected_answer": "Token creation happens in auth.py inside create_token.",
                        "relevant_docs": ["auth.py::function::create_token::12"],
                    }
                ],
                "top_k": 3,
            },
        )
        self.assertEqual(eval_response.status_code, 200)
        eval_payload = eval_response.json()
        self.assertEqual(eval_payload["summary"]["example_count"], 1)
        self.assertEqual(len(eval_payload["examples"]), 1)
        self.assertIn("judge_scores", eval_payload["examples"][0])

    def test_query_without_index_is_rejected(self) -> None:
        response = self.client.post("/api/query", json={"question": "test", "top_k": 3})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
