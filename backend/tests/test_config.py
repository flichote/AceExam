"""Tests for core config module.

Verifies that pydantic-settings correctly reads from environment,
falls back to defaults, and that the Settings singleton is importable.
"""

import os
from importlib import reload

import app.core.config as config_module


class TestSettingsDefaults:
    """RED → GREEN: verify defaults when no env vars are set."""

    def test_default_database_url(self, monkeypatch):
        """Default DATABASE_URL should be the local Postgres string.

        Uses Settings(_env_file=None) to isolate from any .env file
        (e.g. a local dev .env with DATABASE_URL=sqlite... would otherwise
        override the default and make this test environment-dependent).
        """
        monkeypatch.delenv("DATABASE_URL", raising=False)
        s = config_module.Settings(_env_file=None)
        assert "asyncpg" in s.DATABASE_URL
        assert "aceexam" in s.DATABASE_URL

    def test_default_jwt_algorithm_is_hs256(self):
        assert config_module.settings.JWT_ALGORITHM == "HS256"

    def test_default_llm_models(self):
        assert config_module.settings.LLM_FLASH_MODEL == "deepseek-chat"
        assert config_module.settings.LLM_PRO_MODEL == "deepseek-reasoner"

    def test_default_max_tokens(self):
        assert config_module.settings.LLM_FLASH_MAX_TOKENS == 512
        assert config_module.settings.LLM_PRO_MAX_TOKENS == 2048

    def test_default_timeout(self):
        assert config_module.settings.LLM_REQUEST_TIMEOUT == 30


class TestSettingsFromEnv:
    """RED → GREEN: verify env-var override path."""

    def test_env_override_works(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key-12345")
        monkeypatch.setenv("JWT_SECRET", "super-secret-test")
        # Force reload to pick up env vars
        reload(config_module)
        try:
            assert config_module.settings.DEEPSEEK_API_KEY == "sk-test-key-12345"
            assert config_module.settings.JWT_SECRET == "super-secret-test"
        finally:
            # Clean up env vars and reload defaults
            monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
            monkeypatch.delenv("JWT_SECRET", raising=False)
            reload(config_module)
