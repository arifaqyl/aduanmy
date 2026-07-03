from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_db_path() -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / "data" / "aduanmy.db")


def _default_data_dir() -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / "data")


def _default_threads_session_path() -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / "data" / "private" / "threads-session.json")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ADUANMY_",
        extra="ignore",
    )

    env: str = "dev"
    db_path: str = Field(default_factory=_default_db_path)
    data_dir: str = Field(default_factory=_default_data_dir)
    host: str = "0.0.0.0"
    port: int = 8000

    x_provider: str = "public_scrape"
    threads_provider: str = "authenticated_playwright"
    threads_session_path: str = Field(default_factory=_default_threads_session_path)
    reddit_provider: str = "public_html"
    rss_provider: str = "public_rss"
    x_auto_collect_enabled: bool = False
    reddit_min_interval_seconds: int = 7200
    x_min_interval_seconds: int = 21600

    auto_refresh_enabled: bool = True
    auto_refresh_interval_seconds: int = 900
    gtfs_anomaly_enabled: bool = False
    gtfs_refresh_interval_seconds: int = 300
    full_refresh_interval_seconds: int = 900
    refresh_on_startup: bool = False
    backup_enabled: bool = True
    backup_interval_seconds: int = 21600
    backup_retention_count: int = 14

    refresh_api_key: str = ""
    allow_dashboard_refresh: bool = False
    dashboard_poll_interval_seconds: int = 300
    cors_origins: str = "*"
    expose_raw_sources: bool = False

    stale_after_minutes: int = 120
    retention_days: int = 90
    discovery_depth: str = "normal"  # minimal | normal | full

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [part.strip() for part in raw.split(",") if part.strip()]


settings = Settings()
