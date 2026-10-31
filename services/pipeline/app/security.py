"""Password hashing (stdlib scrypt) and JWT helpers. Secrets come from the environment only."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

import jwt

TOKEN_TTL_SECONDS = 60 * 60 * 12
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, dk_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
    except ValueError:
        return False
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return hmac.compare_digest(dk, expected)


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret or len(secret) < 32:
        raise RuntimeError("Defina JWT_SECRET (mÃ­nimo de 16 caracteres) no ambiente.")
    return secret


def create_token(user_id: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + TOKEN_TTL_SECONDS}, _secret(), algorithm="HS256")


def decode_token(token: str) -> str | None:
    """Return the user id, or None if the token is invalid or expired."""
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        return None
