from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    anthropic_api_key: str
    upload_dir: str = "./uploads"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 52_428_800  # 50 MB

settings = Settings()
