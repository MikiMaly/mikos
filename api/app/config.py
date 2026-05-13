from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://mikos:mikos@localhost:5432/mikos"

    cf_access_team_domain: str = ""
    cf_access_aud: str = ""
    mikos_allowed_emails: str = ""

    dev_mode: bool = False
    tz: str = "Europe/Prague"

    cors_origins: str = "https://mmaly.cz,http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_emails(self) -> list[str]:
        return [e.strip().lower() for e in self.mikos_allowed_emails.split(",") if e.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
