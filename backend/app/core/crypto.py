"""
AES-256-GCM encryption for vault secrets.
All ciphertext stored as base64-encoded bytes: nonce(12) + tag(16) + ciphertext.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _get_key() -> bytes:
    """Derive 32-byte key from VAULT_MASTER_KEY (base64-encoded Fernet key or raw hex)."""
    raw = settings.VAULT_MASTER_KEY.strip()
    # Accept Fernet key (44 bytes base64) or 64-char hex
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        key = bytes.fromhex(raw)[:32]
    else:
        key = base64.urlsafe_b64decode(raw + "==")[:32]
    if len(key) < 32:
        raise ValueError("VAULT_MASTER_KEY too short — must yield ≥32 bytes")
    return key[:32]


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext → base64(nonce + ciphertext_with_tag)."""
    key = _get_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(encoded: str) -> str:
    """Decrypt base64(nonce + ciphertext_with_tag) → plaintext."""
    key = _get_key()
    raw = base64.b64decode(encoded)
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
