"""lens says contained, spreads or blind, and never goes quiet on what it can't see. Each case
here is a miss the FastAPI bench (bench/fastapi-template/RESULTS.md) found in lens as first shipped."""

import json
import os
import stat
import subprocess
import sys
import unittest

from tests.helpers import FLOWMAP, commit, fixture_repo, flowmap

DEPS = '''
    from typing import Annotated

    from fastapi import Depends

    TIMEOUT = 5


    def get_current_user():
        """The signed-in user."""
        return "u"


    CurrentUser = Annotated[str, Depends(get_current_user)]
'''
ITEMS = '''
    from fastapi import APIRouter

    from app.api.deps import CurrentUser

    router = APIRouter()


    @router.get("/")
    def read_items(user: CurrentUser):
        return [user]
'''


def fastapi_app():
    return {
        "flowmap.toml": '[[entry]]\nadapter = "fastapi"\nmain = "app/main.py"\n\n[code]\ngraph = ["app"]\n',
        "app/__init__.py": "",
        "app/api/__init__.py": "",
        "app/main.py": '''
            from importlib import import_module

            from fastapi import FastAPI

            from app.api import items

            app = FastAPI()
            app.include_router(items.router, prefix="/items")
            app.include_router(import_module("app.api.private").router)
        ''',
        "app/api/deps.py": DEPS,
        "app/api/items.py": ITEMS,
        "docs/flowmap/map.json": '{"flows": [], "runs": []}\n',
    }


class VerdictTest(unittest.TestCase):
    def lens(self, files):
        root, base = fixture_repo(self, fastapi_app())
        head = commit(root, files)
        return json.loads(flowmap("lens", base, head, "--json", root=root))

    def test_annotated_dependency_alias_is_reached(self):
        root, base = fixture_repo(self, fastapi_app())
        edges = json.loads(flowmap("callgraph", "dump", base, root=root))["edges"]
        self.assertIn(["app/api/items.py:read_items", "app/api/deps.py:CurrentUser"], edges)
        self.assertIn(["app/api/deps.py:CurrentUser", "app/api/deps.py:get_current_user"], edges)

    def test_unresolvable_include_router_does_not_crash_the_inventory(self):
        root, _ = fixture_repo(self, fastapi_app())
        flowmap("inventory", root=root)
        inv = json.loads((root / "docs/flowmap/inventory.json").read_text())
        self.assertEqual([e["endpoint"] for e in inv["endpoints"]], ["GET /items/"])

    def test_editing_a_dependency_spreads_to_the_endpoints_behind_its_alias(self):
        fx = self.lens({"app/api/deps.py": DEPS.replace('return "u"', 'return "admin"')})
        self.assertEqual(fx["verdict"], "spreads")
        self.assertEqual(fx["spreads_to"], ["GET /items/"])

    def test_docstring_only_edit_is_contained(self):
        fx = self.lens({"app/api/deps.py": DEPS.replace("The signed-in user.", "Who is signed in.")})
        self.assertEqual(fx["verdict"], "contained")
        self.assertEqual(fx["cosmetic"], ["app/api/deps.py:get_current_user"])
        self.assertEqual(fx["changed"], [])

    def test_module_level_change_is_blind(self):
        fx = self.lens({"app/api/deps.py": DEPS.replace("TIMEOUT = 5", "TIMEOUT = 500")})
        self.assertEqual(fx["verdict"], "blind")
        self.assertIn("module-level code changed", fx["blind"][0])

    def test_decorator_edit_changes_the_handler(self):
        fx = self.lens({"app/api/items.py": ITEMS.replace('@router.get("/")', '@router.get("/", deprecated=True)')})
        self.assertIn("app/api/items.py:read_items", fx["changed"])
        self.assertNotIn("app/api/items.py:<module>", fx["changed"])

    def test_unparseable_file_is_a_blind_spot(self):
        fx = self.lens({"app/api/broken.py": "def oops(:\n"})
        self.assertEqual(fx["verdict"], "blind")
        self.assertTrue(any("could not parse `app/api/broken.py`" in b for b in fx["blind"]), fx["blind"])

    def test_markdown_carries_the_verdict_first(self):
        root, base = fixture_repo(self, fastapi_app())
        head = commit(root, {"app/api/deps.py": DEPS.replace("TIMEOUT = 5", "TIMEOUT = 500")})
        out = flowmap("lens", base, head, root=root).splitlines()
        self.assertTrue(out[2].startswith("**Verdict: blind.**"), out[:4])
        self.assertIn("## Blind spots", out)


class ProjectPythonTest(unittest.TestCase):
    def test_flowmap_python_reruns_under_that_interpreter(self):
        root, _ = fixture_repo(self, fastapi_app())
        fake = root / "fake-python"
        fake.write_text('#!/bin/sh\necho "ran under fake: $FLOWMAP_REEXEC $2"\n')
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = {**os.environ, "FLOWMAP_ROOT": str(root), "FLOWMAP_PYTHON": str(fake)}
        env.pop("FLOWMAP_REEXEC", None)
        r = subprocess.run([sys.executable, str(FLOWMAP), "inventory"], cwd=root, env=env,
                           capture_output=True, text=True, check=True)
        self.assertEqual(r.stdout.strip(), "ran under fake: 1 inventory")


if __name__ == "__main__":
    unittest.main()
