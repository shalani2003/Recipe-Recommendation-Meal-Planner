"""Compatibility import for the plural password service name used by routes."""
from services.password import PasswordHashError, hash_password, verify_password

__all__ = ["PasswordHashError", "hash_password", "verify_password"]
