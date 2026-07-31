from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_api_key: str = ""
    llm_model_id: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout: int = 60
    data_dir: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    zotero_base_url: str = "http://localhost:23119/api"
    spacecraft_dir: str = ""

    @property
    def root(self) -> Path:
        if self.data_dir:
            return Path(self.data_dir)
        return Path(__file__).resolve().parents[2] / "data"

    @property
    def spacecraft_root(self) -> Path:
        if self.spacecraft_dir:
            return Path(self.spacecraft_dir)
        return Path(__file__).resolve().parents[2] / "spacecraft"


settings = Settings()
