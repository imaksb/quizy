from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    AUTH_SECRET_KEY: str
    ENVIRONMENT: Literal["development", "production"] = "development"
    DOMAIN: str = "localhost"

    FAKE_HASH: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 * 2

    POSTGRES_USER: str
    POSTGRES_DB: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    GOOGLE_CLIENT_SECRET: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_REDIRECT_URI: str

    FRONTEND_ADMIN_URL: str
    FRONTEND_CLIENT_URL: str
    CORS_ALLOWED_ORIGINS: str = (
        "https://mmquiz.site,https://www.mmquiz.site"
    )
    CORS_ALLOWED_ORIGIN_REGEX: str | None = (
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    )

    OPENAPI_SWAGGER_PASSWORD: str
    OPENAPI_SWAGGER_USERNAME: str = "admin"

    @computed_field
    @property
    def cors_allowed_origins(self) -> list[str]:
        origins = [
            self.FRONTEND_ADMIN_URL,
            self.FRONTEND_CLIENT_URL,
            *self.CORS_ALLOWED_ORIGINS.split(","),
        ]
        return list(dict.fromkeys(origin.strip() for origin in origins if origin.strip()))

    @computed_field
    @property
    def sqlalchemy_database_uri(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        )


settings = Settings() # noqa
