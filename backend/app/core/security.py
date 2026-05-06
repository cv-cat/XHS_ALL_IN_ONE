from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet
from fastapi import HTTPException, status

from backend.app.core.config import get_settings

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
PASSWORD_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8").rstrip("=")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    password_hash = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${password_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        _, iterations, salt, expected_hash = password_hash.split("$", 3)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        actual_hash = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
        return secrets.compare_digest(actual_hash, expected_hash)
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(legacy_hash, password_hash)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def _sign_token(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(get_settings().secret_key.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _create_token(user_id: int, expires_delta: timedelta, token_type: str) -> str:
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload = {"user_id": user_id, "token_type": token_type, "exp": int(expires_at.timestamp())}
    return _sign_token(payload)


def create_access_token(user_id: int) -> str:
    return _create_token(user_id, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), "access")


def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS), "refresh")


def decode_token(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header_value, payload_value, signature_value = token.split(".")
    except ValueError as exc:
        raise credentials_exception from exc

    signing_input = f"{header_value}.{payload_value}"
    expected_signature = hmac.new(
        get_settings().secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual_signature = _base64url_decode(signature_value)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise credentials_exception

    try:
        payload = json.loads(_base64url_decode(payload_value))
    except (json.JSONDecodeError, ValueError) as exc:
        raise credentials_exception from exc

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(datetime.now(timezone.utc).timestamp()):
        raise credentials_exception
    if not isinstance(payload.get("user_id"), int):
        raise credentials_exception
    return payload


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    settings = get_settings()
    key: Optional[str] = settings.fernet_key or None
    return Fernet(key.encode("utf-8") if key else _derive_fernet_key(settings.secret_key))


def encrypt_text(value: str) -> str:
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
