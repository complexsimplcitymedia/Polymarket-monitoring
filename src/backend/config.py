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

    # Keep only the sports leagues we trade (MLB, college football, NFL, tennis, basketball) in the market list
    SPORTS_ONLY: bool = True

    # Alerts: a team that is AHEAD on the scoreboard but still priced to lose
    ALERTS_ENABLED: bool = True
    ALERT_MAX_PRICE: float = 0.50  # alert while a leading team is priced below this
    ALERT_MIN_LEAD: int = 5  # and is ahead by at least this many points (5 is the floor)
    ALERT_TRAIL_MAX_DEFICIT: int = 8  # college football: a team down by this many or fewer (one score)...
    ALERT_TRAIL_MAX_PRICE: float = 0.30  # ...and priced below this (30%) is alert-worthy
    ALERT_COOLDOWN_MINUTES: int = 30  # at most one alert per game and team in this window
    # Email delivery. Preferred: a Hostinger Agentic Mail API token (sends from its mailbox).
    # Fallback: SMTP. Leave both unset, or ALERT_EMAIL_TO empty, to keep alerts in the app only.
    HOSTINGER_MAIL_API_TOKEN: str = ""
    HOSTINGER_MAILBOX_ID: str = ""  # optional; the token's first mailbox is used when empty
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True
    ALERT_EMAIL_TO: str = ""

    # The AI inside the app (NanoGPT, OpenAI-compatible). Leave the key empty to keep the AI off.
    NANOGPT_API_KEY: str = ""
    NANOGPT_BASE_URL: str = "https://nano-gpt.com/api/v1"

    # Poll live college football every minute and flag price-vs-game-state gaps
    ENABLE_CFB_SCANNER: bool = True

    # Keep weather, parlay, debate and trading routes mounted (isolated in src/backend/extras)
    ENABLE_EXTRAS: bool = True

    # Automated Opportunity Execution Daemon
    AUTO_TRADE_ENABLED: bool = False
    AUTO_TRADE_MAX_BET: float = 5.0
    AUTO_TRADE_MIN_EV: float = 25.0
    AUTO_TRADE_DRY_RUN: bool = True

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Optional: route CLOB order traffic through a London-egress SOCKS5 proxy.
    # Format: socks5h://host:port (set in .env; no auth). Example:
    # TRADE_SOCKS_PROXY=socks5h://polymarket-ts-london-trade:1080
    TRADE_SOCKS_PROXY: str = ""

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
