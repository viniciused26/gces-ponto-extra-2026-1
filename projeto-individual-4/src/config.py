from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "conjuntura.db"
DEFAULT_DB_URL = f"sqlite:///{DB_PATH}"
COMPANIES_CONFIG_PATH = ROOT / "configs" / "companies.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    poll_interval_hours: int = Field(default=24, alias="POLL_INTERVAL_HOURS")


@dataclass(frozen=True)
class CompanyConfig:
    name: str
    results_url: str


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()


def load_companies_config(path: Path | None = None) -> list[CompanyConfig]:
    config_path = path or COMPANIES_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    return [
        CompanyConfig(name=item["name"], results_url=item["results_url"])
        for item in payload.get("companies", [])
    ]
