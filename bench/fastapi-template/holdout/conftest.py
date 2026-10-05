"""Holdout invariants: what production relies on, checked against seeded "existing" data.

The repo's own tests stand in for CI. These stand in for production: they run against a
database seeded by ../seed.py at the base revision and then migrated by the change under test.
Each test names the endpoints whose behaviour it pins, so a failure can be placed on the map.
Tokens are minted directly with the secret key, so a broken login doesn't fail every test.
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import seed  # noqa: E402

API = "/api/v1"


RESULTS = {}


def pytest_configure(config):
    config.addinivalue_line("markers", "endpoints(*eps): inventory endpoints this test pins")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    rep = (yield).get_result()
    if rep.when == "call" or rep.failed:
        eps = sorted({e for m in item.iter_markers("endpoints") for e in m.args})
        prev = RESULTS.get(item.nodeid, {}).get("outcome")
        RESULTS[item.nodeid] = {"outcome": "failed" if rep.failed or prev == "failed" else rep.outcome,
                                "endpoints": eps,
                                "message": str(rep.longrepr).splitlines()[-1][:300] if rep.failed else ""}


def pytest_unconfigure(config):
    out = os.environ.get("HOLDOUT_OUT")
    if out:
        import json
        Path(out).write_text(json.dumps(RESULTS, indent=1))


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def token(email, minutes=60):
    payload = {"exp": datetime.now(UTC) + timedelta(minutes=minutes), "sub": str(seed.USER_ID[email])}
    return jwt.encode(payload, os.environ["SECRET_KEY"], algorithm="HS256")


def auth(email):
    return {"Authorization": f"Bearer {token(email)}"}


def sql(query, *args):
    with psycopg.connect(seed.dsn()) as conn:
        return conn.execute(query, args).fetchall()
