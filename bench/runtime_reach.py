"""pytest plugin: record which app functions each endpoint actually executes (runtime reach).

Ground truth for the bench, independent of flowmap's static call graph. Every HTTP request the
tests make is attributed to the handler that served it, and every app function that starts
while serving it is recorded. Functions run by a test outside any request (direct crud calls,
fixtures) are recorded per test.

    REACH_APP=backend/app REACH_OUT=reach.json pytest -p runtime_reach ...

REACH_APP is the app source dir relative to the repo root (the git toplevel of the cwd).
Output: {"endpoints": {handler: [symbol]}, "tests": {nodeid: {"endpoints": [...], "symbols": [...]}}}
where handler and symbol are flowmap anchors, `repo/relative/path.py:Qual.name`.
"""

import contextvars
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                           text=True, check=True).stdout.strip())
APP = str((ROOT / os.environ.get("REACH_APP", ".")).resolve()) + os.sep
TOOL = 3  # sys.monitoring tool ids 3 and 4 are free for user tools

REQUEST = contextvars.ContextVar("request_bucket", default=None)
endpoints = defaultdict(set)   # handler anchor -> symbols
tests = defaultdict(lambda: {"endpoints": set(), "symbols": set()})
current_test = None


def anchor(filename, qualname):
    return f"{Path(filename).resolve().relative_to(ROOT)}:{qualname}"


def on_start(code, offset):
    if not code.co_filename.startswith(APP):
        return
    sym = anchor(code.co_filename, code.co_qualname)
    bucket = REQUEST.get()
    if bucket is not None:
        bucket.add(sym)
    elif current_test:
        tests[current_test]["symbols"].add(sym)


class Recorder:
    """Pure ASGI middleware: a bucket per request, filed under the handler that served it."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        bucket = set()
        token = REQUEST.set(bucket)
        try:
            await self.app(scope, receive, send)
        finally:
            REQUEST.reset(token)
            fn = scope.get("endpoint")
            if fn is not None and getattr(fn, "__code__", None) and fn.__code__.co_filename.startswith(APP):
                key = anchor(fn.__code__.co_filename, fn.__code__.co_qualname)
            else:
                key = f"unrouted {scope.get('method')} {scope.get('path')}"
            endpoints[key] |= bucket
            if current_test:
                tests[current_test]["endpoints"].add(key)


def pytest_configure(config):
    sys.monitoring.use_tool_id(TOOL, "flowmap-runtime-reach")
    sys.monitoring.register_callback(TOOL, sys.monitoring.events.PY_START, on_start)
    sys.monitoring.set_events(TOOL, sys.monitoring.events.PY_START)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_finish(session):
    # the app is imported by now (conftest); wrap it before any TestClient starts it
    from app.main import app
    app.add_middleware(Recorder)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    global current_test
    current_test = item.nodeid
    try:
        yield
    finally:
        current_test = None


def pytest_unconfigure(config):
    sys.monitoring.set_events(TOOL, 0)
    sys.monitoring.free_tool_id(TOOL)
    out = os.environ.get("REACH_OUT")
    if out:
        Path(out).write_text(json.dumps({
            "endpoints": {k: sorted(v) for k, v in sorted(endpoints.items())},
            "tests": {k: {"endpoints": sorted(v["endpoints"]), "symbols": sorted(v["symbols"])}
                      for k, v in sorted(tests.items())},
        }, indent=1))
