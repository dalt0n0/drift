"""
Auth utilities: password hashing (Argon2id), JWT, refresh tokens, MFA.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt
import pyotp
import qrcode
import io
import base64

from app.config import settings

# ── Password hashing (Argon2id) ────────────────────────────────────────────────
_ph = PasswordHasher(
    time_cost=3,       # iterations
    memory_cost=65536, # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


# ── JWT ────────────────────────────────────────────────────────────────────────
def create_access_token(user_id: str, username: str, role: str) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    expire = datetime.now(tz=timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(tz=timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


def decode_access_token(token: str) -> dict:
    """Raises JWTError on invalid/expired."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── Refresh tokens ─────────────────────────────────────────────────────────────
def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, hashed_token). Store only the hash."""
    raw = secrets.token_urlsafe(64)
    hashed = _hash_token(raw)
    return raw, hashed


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_refresh_token(token: str) -> str:
    return _hash_token(token)


# ── API keys ───────────────────────────────────────────────────────────────────
def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_hash, key_prefix). Store hash + prefix."""
    raw = "drk_" + secrets.token_urlsafe(40)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:12]
    return raw, hashed, prefix


def verify_api_key(raw: str, stored_hash: str) -> bool:
    computed = hashlib.sha256(raw.encode()).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


# ── TOTP / MFA ─────────────────────────────────────────────────────────────────
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    # valid_window=1 allows ±30s clock skew
    return totp.verify(code, valid_window=1)


def get_totp_provisioning_uri(secret: str, username: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name="Drift")


def get_totp_qr_base64(provisioning_uri: str) -> str:
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
