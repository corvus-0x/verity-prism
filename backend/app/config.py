from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder values shipped in docker-compose / .env.example that must never
# be used as a real signing key.
_WEAK_SECRET_KEYS = {
    "dev-secret-key-change-in-production",
    "change-this-to-a-long-random-string-in-production",
}
_MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    anthropic_api_key: str
    upload_dir: str = "./uploads"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 52_428_800  # 50 MB
    cookie_secure: bool = False  # set True in production (HTTPS only)
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        """Reject empty, placeholder, or short signing keys at startup.

        A weak SECRET_KEY lets anyone forge JWTs for any user, so we fail fast
        rather than boot with a guessable key.
        """
        candidate = (v or "").strip()
        if not candidate:
            raise ValueError(
                "SECRET_KEY must be set (see backend/.env.example)")
        if candidate in _WEAK_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY is a known placeholder. Generate a strong key: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if len(candidate) < _MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_KEY_LENGTH} characters"
            )
        return v


settings = Settings()
