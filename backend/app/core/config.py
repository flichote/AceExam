"""Core configuration module."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aceexam"

    # ── DeepSeek ──
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # ── JWT ──
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── LLM Gateway ──
    LLM_DEFAULT_MODEL: str = "flash"
    LLM_FLASH_MODEL: str = "deepseek-chat"
    LLM_PRO_MODEL: str = "deepseek-reasoner"
    LLM_FLASH_MAX_TOKENS: int = 512
    LLM_PRO_MAX_TOKENS: int = 2048
    LLM_REQUEST_TIMEOUT: int = 30

    # ── Embedding ──
    # NOTE: DeepSeek may not provide a dedicated embeddings API.
    # When this is empty or returns 404, the embedder falls back to keyword-based
    # retrieval (bag-of-words + TF-IDF scoring against chunk text / title).
    EMBEDDING_ENABLED: bool = True
    EMBEDDING_MODEL: str = ""  # e.g. "text-embedding-3-small" if using OpenAI-compatible API
    EMBEDDING_BASE_URL: str = ""  # separate base URL for embeddings (OpenAI / local)
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_DIM: int = 1024  # must match pgvector VECTOR(N) column

    # ── App ──
    APP_NAME: str = "AceExam"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
