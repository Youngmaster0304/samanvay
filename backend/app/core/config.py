"""Application settings loaded from the environment."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every field maps to an uppercase environment variable."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    database_url: str = Field(
        default="postgresql+psycopg://samanvay:samanvay_local_dev_only@localhost:5432/samanvay",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="samanvay", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="samanvay_local_dev_only", alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="samanvay", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    policy_path: str = Field(default="policies/naksha_default.yaml", alias="POLICY_PATH")
    web_origin: str = Field(default="http://localhost:3000", alias="WEB_ORIGIN")

    storage_srid: int = Field(
        default=32643,
        alias="STORAGE_SRID",
        description="Metric storage CRS for the AOI: a UTM zone or the state projected CRS.",
    )

    check_timeout_seconds: float = Field(default=2.0, alias="CHECK_TIMEOUT_SECONDS")
    objectstore_warmup_seconds: float = Field(
        default=45.0,
        alias="OBJECTSTORE_WARMUP_SECONDS",
        description=(
            "How long /readyz keeps re-probing a cold object store so one held "
            "request carries a spun-down MinIO through its boot; 0 disables."
        ),
    )

    # Ingest bounds (Stage 1). These are operational limits on what a single upload is
    # allowed to cost the process, not quality thresholds: those live in the policy file.
    max_upload_bytes: int = Field(
        default=512 * 1024 * 1024,
        alias="MAX_UPLOAD_BYTES",
        description="Refuse an upload larger than this many bytes (413).",
    )
    max_archive_entries: int = Field(
        default=4096,
        alias="MAX_ARCHIVE_ENTRIES",
        description="Refuse a zip with more members than this, as a zip-bomb bound.",
    )
    max_archive_bytes: int = Field(
        default=2 * 1024 * 1024 * 1024,
        alias="MAX_ARCHIVE_BYTES",
        description="Refuse an archive whose unpacked size exceeds this many bytes (413).",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_scheme(cls, value: object) -> object:
        """Accept managed platforms' `postgres://` URLs and pin psycopg (v3).

        Render (and Heroku-style platforms) hand out `postgres://`; SQLAlchemy
        maps a bare `postgresql://` to psycopg2, which this project does not
        install, so both schemes are rewritten to `postgresql+psycopg://`.
        """
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+psycopg://" + value[len("postgres://") :]
            if value.startswith("postgresql://"):
                return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
