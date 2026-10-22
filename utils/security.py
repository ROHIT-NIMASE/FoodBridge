"""Security helpers – password hashing and verification.

Uses PBKDF2-HMAC-SHA256 with a random 16-byte salt, storing everything as
a single colon-delimited string so it can be stored in one VARCHAR column.

Format: sha256:<iterations>:<hex_salt>:<hex_key>
"""
from __future__ import annotations

import hashlib
import hmac
import os


_ALGORITHM  = "sha256"
_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Return a string suitable for storing in users.password_hash."""
    salt = os.urandom(16)
    key  = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}:{_ITERATIONS}:{salt.hex()}:{key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Return True if *password* matches *stored_hash*."""
    try:
        algo, iters_str, salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        iters = int(iters_str)
        candidate = hashlib.pbkdf2_hmac(algo, password.encode(), salt, iters)
        return hmac.compare_digest(candidate.hex(), key_hex)
    except Exception:
        return False
