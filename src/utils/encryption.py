"""
Symmetric encryption for secrets stored in the database (e.g. OpenAI API keys).

The encryption key is read from the API_KEY_ENCRYPTION_KEY environment variable.
It must be a 32-byte URL-safe base64-encoded string (produce one with:
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

In development, if the variable is not set, a fixed dev key is used with a
logged warning. Never use the dev key in production.
"""

import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_DEV_KEY = b"ZmFrZWtleWZha2VrZXlmYWtla2V5ZmFrZWtleWZha2U="  # 32-byte fixed dev key
_ENV_KEY = os.getenv("API_KEY_ENCRYPTION_KEY", "").strip().encode()

if _ENV_KEY:
    try:
        _fernet = Fernet(_ENV_KEY)
    except Exception as exc:
        raise RuntimeError(
            "API_KEY_ENCRYPTION_KEY is set but is not a valid Fernet key. "
            'Generate one with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from exc
else:
    logger.warning(
        "API_KEY_ENCRYPTION_KEY is not set — using a fixed development key. "
        "Set this variable in production to protect stored API keys."
    )
    _fernet = Fernet(_DEV_KEY)


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return a URL-safe base64 token."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by encrypt(). Raises ValueError on failure."""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt value — key mismatch or corrupted data."
        ) from exc
