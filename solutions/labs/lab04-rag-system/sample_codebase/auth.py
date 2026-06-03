import hashlib
import hmac
import time

SECRET_KEY = "demo-secret"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def create_token(user_id: int) -> str:
    issued_at = int(time.time())
    return f"{user_id}:{issued_at}:{SECRET_KEY}"


def parse_token(token: str) -> dict:
    user_id, issued_at, signature = token.split(":")
    return {"user_id": int(user_id), "issued_at": int(issued_at), "signature": signature}
