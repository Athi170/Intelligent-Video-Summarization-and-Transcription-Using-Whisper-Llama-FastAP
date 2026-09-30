import hashlib
import hmac
import os
import secrets
from datetime import datetime

from .redis_service import redis_client

# How long a login session stays valid (seconds). 7 days.
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", 60 * 60 * 24 * 7))

PBKDF2_ITERATIONS = 260_000


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()


def hash_password(password: str) -> str:
    """Returns a 'salt$hash' string safe to store in Redis."""
    salt = secrets.token_hex(16)
    return f"{salt}${_hash_password(password, salt)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected_hash = stored.split("$", 1)
    except (ValueError, AttributeError):
        return False

    actual_hash = _hash_password(password, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def username_exists(username: str) -> bool:
    return redis_client.exists(f"user:{username}") == 1


def create_user(username: str, password: str) -> bool:
    """Returns False if the username is already taken."""
    if username_exists(username):
        return False

    redis_client.hset(
        f"user:{username}",
        mapping={
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    redis_client.sadd("users", username)
    return True


def authenticate_user(username: str, password: str) -> bool:
    user = redis_client.hgetall(f"user:{username}")

    if not user:
        return False

    return verify_password(password, user.get("password_hash", ""))


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)

    redis_client.set(
        f"session:{token}",
        username,
        ex=SESSION_TTL_SECONDS,
    )

    return token


def get_session_user(token: str):
    if not token:
        return None

    return redis_client.get(f"session:{token}")


def delete_session(token: str):
    if token:
        redis_client.delete(f"session:{token}")
