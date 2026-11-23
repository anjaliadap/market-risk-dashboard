import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/research.db"
    excel_workbook_path: str = Field(
        default="",
        validation_alias=AliasChoices("excel_workbook_path", "process_workbook_path"),
    )
    excel_settle_seconds: float = 5.0
    excel_poll_seconds: float = 10.0
    excel_artifact_dir: str = str(
        Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "MarketRiskDashboard"
    )
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
