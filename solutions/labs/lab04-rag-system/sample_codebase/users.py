from auth import create_token, hash_password

USERS = []


def create_user(email: str, password: str) -> dict:
    user = {"id": len(USERS) + 1, "email": email, "password_hash": hash_password(password)}
    USERS.append(user)
    return {"user": user, "token": create_token(user["id"])}


def find_user_by_email(email: str) -> dict | None:
    for user in USERS:
        if user["email"] == email:
            return user
    return None


def login(email: str, password: str) -> dict | None:
    user = find_user_by_email(email)
    if not user:
        return None
    if user["password_hash"] != hash_password(password):
        return None
    return {"token": create_token(user["id"]), "user": user}
