"""
Application configuration using Pydantic Settings.

Loads environment variables from .env file.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./polymarket.db"

    # News API
    NEWS_API_KEY: str = ""

    # Polymarket API (Optional, for CLOB access)
    POLYMARKET_KEY_ID: str = ""
    POLYMARKET_SECRET_KEY: str = ""
    POLYMARKET_API_KEY: str = ""
    POLYMARKET_SECRET: str = ""
    POLYMARKET_PASSPHRASE: str = ""
    POLYMARKET_PRIVATE_KEY: str = ""
    POLYMARKET_FUNDER: str = ""
    POLYMARKET_SIGNATURE_TYPE: int = 0  # 0: EOA, 1: POLY_PROXY (Magic/Email), 2: POLY_GNOSIS_SAFE
    POLYMARKET_HOST: str = "https://clob.polymarket.com"
    POLYMARKET_CHAIN_ID: int = 137

    # Local LLM on UpCloud AMD EPYC (chi6)
    OLLAMA_BASE_URL: str = "http://100.110.82.53:11434"
    LOCAL_LLM_MODEL: str = "qwen2.5:7b"

    # Automated Opportunity Execution Daemon
    AUTO_TRADE_ENABLED: bool = False
    AUTO_TRADE_MAX_BET: float = 5.0
    AUTO_TRADE_MIN_EV: float = 25.0
    AUTO_TRADE_DRY_RUN: bool = True

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
