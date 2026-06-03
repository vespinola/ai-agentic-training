from users import create_user, find_user_by_email, login


def register_handler(payload: dict) -> dict:
    required = {"email", "password"}
    if not required.issubset(payload):
        return {"error": "missing required fields"}
    return create_user(payload["email"], payload["password"])


def login_handler(payload: dict) -> dict:
    result = login(payload["email"], payload["password"])
    if not result:
        return {"error": "invalid credentials"}
    return result


def user_lookup_handler(email: str) -> dict:
    user = find_user_by_email(email)
    if not user:
        return {"error": "user not found"}
    return user


def health_handler() -> dict:
    return {"status": "ok", "service": "sample-code-rag"}
