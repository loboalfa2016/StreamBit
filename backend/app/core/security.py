from datetime import datetime, timedelta, timezone
import hashlib
import time
import uuid
import bcrypt
from fastapi import Request
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

# Almacén en memoria de tokens revocados (jti) para logout y tokens de un solo uso
revoked_tokens: set[str] = set()

# Control básico de abuso: {clave: [timestamps]}
rate_limit_store: dict[str, list[float]] = {}


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_action_token(subject: str, purpose: str, expire_minutes: int = 15) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": subject,
        "type": purpose,  # "email_verify" o "password_reset"
        "jti": str(uuid.uuid4()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str, expected_type: str = "access") -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("jti") in revoked_tokens:
            return None
        if payload.get("type") != expected_type:
            return None
        return payload
    except InvalidTokenError:
        return None


def revoke_token(jti: str) -> None:
    revoked_tokens.add(jti)


def check_rate_limit(key: str, max_requests: int = 3, window_seconds: int = 300) -> bool:
    now = time.time()
    timestamps = [t for t in rate_limit_store.get(key, []) if now - t < window_seconds]
    if len(timestamps) >= max_requests:
        rate_limit_store[key] = timestamps
        return False
    timestamps.append(now)
    rate_limit_store[key] = timestamps
    return True


def build_visitor_fingerprint(request: Request) -> str:
    visitor_id = request.headers.get("X-Visitor-Id", "").strip()
    if visitor_id:
        raw_identity = f"visitor:{visitor_id}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        raw_identity = f"anon:{client_ip}:{user_agent}"

    salted = f"{settings.SECRET_KEY}:{raw_identity}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()