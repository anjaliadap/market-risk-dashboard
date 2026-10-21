from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/research.db"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
