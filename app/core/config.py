from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    db_path: str = "D:/aduanmy/data/aduanmy.db"
    data_dir: str = "D:/aduanmy/data"
    x_provider: str = "twitter_cli"
    threads_provider: str = "public_scrape"
    reddit_provider: str = "public_html"

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)


settings = Settings()
