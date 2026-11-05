"""Password hashing and verification for account credentials and recovery codes."""
from argon2 import PasswordHasher, Type
from argon2.exceptions import HashingError, InvalidHashError, VerificationError
from werkzeug.security import check_password_hash

_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    type=Type.ID,
)


class PasswordHashError(Exception):
    """Raised when a secret cannot be hashed securely."""


def hash_password(secret):
    try:
        return _PASSWORD_HASHER.hash(secret)
    except (HashingError, MemoryError, TypeError, ValueError):
        raise PasswordHashError("Secure password hashing is unavailable") from None


def verify_password(encoded_hash, candidate):
    if not isinstance(encoded_hash, str) or not isinstance(candidate, str):
        return False

    if encoded_hash.startswith("$argon2id$"):
        try:
            return _PASSWORD_HASHER.verify(encoded_hash, candidate)
        except (InvalidHashError, VerificationError, TypeError, ValueError):
            return False

    if encoded_hash.startswith(("scrypt:", "pbkdf2:")):
        try:
            return check_password_hash(encoded_hash, candidate)
        except (TypeError, ValueError):
            return False
    return False
