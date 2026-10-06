"""Shared fixtures. The explorer binds its DB engine at import time, so DATABASE_URL is set
here before anything from `app` is imported:
  TEST_DATABASE_URL unset  -> a throwaway SQLite file
  TEST_DATABASE_URL=postgresql+psycopg://...  -> that Postgres DB (created if missing)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "hornet"
sys.path[:0] = [str(ROOT / "explorer"), str(ROOT / "messages-api")]

TEST_DB = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["DATABASE_URL"] = TEST_DB
os.environ.setdefault("HORNET_URL", "http://hornet.invalid:14265")


def _ensure_postgres_db(url: str) -> None:
    import psycopg
    from sqlalchemy.engine import make_url
    u = make_url(url)
    with psycopg.connect(host=u.host, port=u.port or 5432, user=u.username, password=u.password,
                         dbname="postgres", autocommit=True) as c:
        if not c.execute("select 1 from pg_database where datname=%s", (u.database,)).fetchone():
            c.execute(f'create database "{u.database}"')


if TEST_DB.startswith("postgresql"):
    _ensure_postgres_db(TEST_DB)


def load(name: str):
    """A real Hornet response captured by scripts/capture_hornet.sh."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def fresh_db():
    from app.db import Base, engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db_name() -> str:
    return "postgresql" if TEST_DB.startswith("postgresql") else "sqlite"
