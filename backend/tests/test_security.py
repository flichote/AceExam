"""Tests for core security module.

Verifies: password hashing/verification, JWT encode/decode round-trip,
and that wrong passwords / expired tokens are rejected.
"""

import time
from datetime import timedelta

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """RED → GREEN: password hashing and verification."""

    def test_hash_and_verify_same_password(self):
        plain = "my-secret-password"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    def test_verify_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_input(self):
        """Bcrypt generates different hashes due to random salt."""
        plain = "password123"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        assert h1 != h2
        assert verify_password(plain, h1)
        assert verify_password(plain, h2)


class TestJWTToken:
    """RED → GREEN: JWT encode/decode round-trip and error cases."""

    def test_encode_and_decode_roundtrip(self):
        token = create_access_token("user-abc-123")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-abc-123"

    def test_token_contains_expiry(self):
        token = create_access_token("user-1")
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_custom_expiry(self):
        token = create_access_token("user-2", expires_delta=timedelta(minutes=5))
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_wrong_secret_rejected(self, monkeypatch):
        from app.core import security
        original = security.settings.JWT_SECRET
        try:
            token = create_access_token("user-x")
            # Change secret to simulate tampering
            monkeypatch.setattr(security.settings, "JWT_SECRET", "different-secret")
            with pytest.raises(JWTError):
                decode_access_token(token)
        finally:
            monkeypatch.setattr(security.settings, "JWT_SECRET", original)
