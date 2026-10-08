import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    PROJECT_ROOT: Path = BASE_DIR.parent

    # Database
    DATABASE_URL: str = ""

    # Storage paths
    GENERATED_DIR: Path = BASE_DIR / "generated"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    FRONTEND_DIR: Path = PROJECT_ROOT / "frontend"

    # Ingestion limits
    MAX_RECIPIENTS_LIMIT: int = 5000
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    RECOMMENDED_POLLING_INTERVAL_SECONDS: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        if not self.DATABASE_URL:
            db_path = (self.BASE_DIR / "certificates.db").as_posix()
            self.DATABASE_URL = f"sqlite:///{db_path}"


settings = Settings()
