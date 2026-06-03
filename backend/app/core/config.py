from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NexusQuant Backend"
    env: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    upstox_base_url: str = "https://api.upstox.com/v2"
    upstox_feed_authorize_v3_path: str = "/feed/market-data-feed/v3/authorize"
    upstox_feed_authorize_v2_path: str = "/feed/market-data-feed/authorize"
    upstox_access_token: str = Field(default="", alias="UPSTOX_ACCESS_TOKEN")
    upstox_client_id: str = Field(default="", alias="UPSTOX_CLIENT_ID")
    upstox_redirect_uri: str = Field(default="", alias="UPSTOX_REDIRECT_URI")

    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/nexusquant"

    # Comma-separated instrument keys as expected by Upstox
    instrument_keys: str = "NSE_INDEX|Nifty 50,BSE_INDEX|SENSEX"
    telemetry_interval_seconds: int = 1
    profile_poll_seconds: int = 5
    stale_feed_seconds: int = 3

    # Risk defaults
    daily_capital: float = 200000.0
    capital_allocation_pct: float = 20.0
    max_exposure_pct: float = 50.0
    max_drawdown_pct: float = 5.0
    max_slippage_pct: float = 0.5
    max_latency_ms: int = 300
    trade_quality_threshold: float = 70.0

    @property
    def instrument_list(self) -> list[str]:
        return [value.strip() for value in self.instrument_keys.split(",") if value.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
