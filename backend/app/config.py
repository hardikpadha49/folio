"""
FolioPulse AI — Application Configuration
Reads all values from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://foliopulse:password@localhost:5432/foliopulse_db"

    # Auth
    secret_key: str = "CHANGE_ME"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # CORS
    frontend_url: str = "http://localhost:3000"

    # Environment
    app_env: str = "development"

    # Future phases — optional, won't break if missing
    alpha_vantage_api_key: str = ""
    google_api_key: str = ""
    redis_url: str = "redis://localhost:6379"
    digio_client_id: str = ""
    digio_client_secret: str = ""
    digio_base_url: str = "https://ext.digio.in:444"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
