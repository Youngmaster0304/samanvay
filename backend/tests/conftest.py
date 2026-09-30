import os
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "policies" / "naksha_default.yaml"

# Must be set before app modules are imported: get_settings() is cached at import time.
os.environ.setdefault("POLICY_PATH", str(POLICY_PATH))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

# Rows written by these tests carry this prefix so teardown touches nothing else.
TEST_NAME_PREFIX = "__stage1test__"


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def policy_path() -> Path:
    assert POLICY_PATH.is_file(), f"policy file missing: {POLICY_PATH}"
    return POLICY_PATH


@pytest.fixture()
def db() -> Iterator["Session"]:
    """A session on the configured database, or a skip when none is reachable.

    Stage 1 tests that only read bytes (detection, CRS, connectors, archives) run
    without this; the ones that write a registry row ask for it.
    """
    from sqlalchemy import text

    from app.db.session import SessionLocal

    try:
        with closing(SessionLocal()) as probe:
            probe.execute(text("SELECT 1"))
    except Exception as exc:  # a missing database is a skip, not a failure
        pytest.skip(f"database not reachable: {type(exc).__name__}: {exc}")

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        from sqlalchemy import delete

        from app.db.models import SourceRegistry

        session.execute(
            delete(SourceRegistry).where(SourceRegistry.name.like(f"{TEST_NAME_PREFIX}%"))
        )
        session.commit()
        session.close()
