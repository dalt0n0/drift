from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

_settings = get_settings()

_NONCE_SIZE = 12
_TAG_SIZE = 16


def _get_key() -> bytes:
    raw = _settings.VAULT_MASTER_KEY.strip()
    # Accept Fernet-style base64 (44 chars) or raw base64
    try:
        decoded = base64.urlsafe_b64decode(raw + "==")
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    # Accept 64-char hex
    if len(raw) == 64:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            pass
    raise ValueError("VAULT_MASTER_KEY must be 32-byte urlsafe-base64 or 64-char hex")


def encrypt(plaintext: str) -> str:
    """AES-256-GCM encrypt. Returns base64(nonce || ciphertext+tag)."""
    key = _get_key()
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = AESGCM(key)
    ct_with_tag = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct_with_tag).decode()


def decrypt(encoded: str) -> str:
    """Reverse of encrypt()."""
    key = _get_key()
    raw = base64.urlsafe_b64decode(encoded.encode() + b"==")
    nonce = raw[:_NONCE_SIZE]
    ct_with_tag = raw[_NONCE_SIZE:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct_with_tag, None).decode()
