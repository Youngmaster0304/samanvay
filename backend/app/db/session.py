"""Engine, session factory, request dependency and database readiness check."""

from collections.abc import Iterator
from contextlib import closing

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    # libpq connect_timeout, in seconds: keeps the readiness check from hanging.
    connect_args={"connect_timeout": max(1, int(settings.check_timeout_seconds))},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """One session per request. The service commits; closing rolls back anything left."""
    with closing(SessionLocal()) as session:
        yield session


def check_database() -> dict[str, object]:
    """Verify connectivity and that PostGIS is available in the target database."""
    try:
        with closing(SessionLocal()) as session:
            session.execute(text("SELECT 1"))
            postgis: object = session.execute(text("SELECT postgis_version()")).scalar_one()
    except Exception as exc:  # reported as a readiness status, not a crash
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "postgis_version": str(postgis)}
