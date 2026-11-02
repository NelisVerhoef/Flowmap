"""The canvas: the map as one left-to-right picture, built from the atlas's data."""

import base64
import json
import os
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from tests.helpers import REPO, flowmap

sys.path.insert(0, str(REPO / "flowmap"))
import canvas  # noqa: E402

BENCH = REPO / "bench" / "fastapi-template" / "map" / "atlas.html"


def step(key, endpoint, nodes, edges, writes=(), ui=()):
    return {"key": key, "name": key, "actor": "user", "evidence": "agreed", "endpoints": [endpoint],
            "writes": list(writes), "ui": list(ui),
            "code": {"nodes": [{"id": n, "file": n.split(":")[0], "sym": n.split(":")[1], "depth": 0,
                                "root": i == 0} for i, n in enumerate(nodes)],
                     "edges": [list(e) for e in edges], "hidden": 0}}


# two flows meet in shared.py; one step writes the User model, one starts from a screen
ATLAS = {"flows": [
    {"id": "sign-in", "summary": "", "steps": [
        step("sign-in/log-in", "POST /login", ["login.py:log_in", "shared.py:check", "deep.py:hash"],
             [("login.py:log_in", "shared.py:check"), ("shared.py:check", "deep.py:hash")],
             writes=["User.last_login"], ui=["web/routes/login.tsx:Login"])]},
    {"id": "new:admin", "summary": "", "steps": [
        step("new:admin/edit", "PATCH /users", ["users.py:edit", "shared.py:check"],
             [("users.py:edit", "shared.py:check")], writes=["User.email"])]},
]}


class Graph(unittest.TestCase):
    def setUp(self):
        self.g = canvas.graph(ATLAS)

    def test_files_sit_at_their_call_depth(self):
        depth = {f: F["depth"] for f, F in self.g["files"].items()}
        self.assertEqual(depth, {"f:login.py": 0, "f:users.py": 0, "f:shared.py": 1, "f:deep.py": 2})

    def test_every_wire_knows_the_steps_that_run_along_it(self):
        wires = {(e["a"], e["b"]): e["steps"] for e in self.g["edges"]}
        self.assertEqual(wires[("f:login.py", "f:shared.py")], ["s:sign-in/log-in"])
        self.assertEqual(wires[("f:users.py", "f:shared.py")], ["s:new:admin/edit"])
        self.assertEqual(self.g["files"]["f:shared.py"]["steps"], ["s:new:admin/edit", "s:sign-in/log-in"])

    def test_writes_become_data_with_their_fields(self):
        self.assertEqual(self.g["data"]["d:User"]["parts"], ["email", "last_login"])
        wires = {(e["a"], e["b"], e["kind"]) for e in self.g["edges"]}
        self.assertIn(("f:login.py", "d:User", "writes"), wires)

    def test_screens_group_by_route_file_and_draft_flows_say_so(self):
        self.assertEqual(list(self.g["screens"]), ["u:web/routes/login"])
        self.assertEqual([f["draft"] for f in self.g["flows"]], [False, True])
        self.assertEqual(self.g["flows"][1]["title"], "Admin")


class Paint(unittest.TestCase):
    def test_a_change_paints_files_steps_and_what_the_map_does_not_know(self):
        g = canvas.graph(ATLAS)
        overlay = {"id": "pr-1", "title": "PR #1", "range": "a..b",
                   "steps": {"sign-in/log-in": {"kind": "reach", "via": ["hash"]}},
                   "changed_ids": ["deep.py:hash", "elsewhere.py:helper"], "new_ids": ["shared.py:audit"]}
        story = {"chapters": [{"title": "Hashing moves", "symbols": ["deep.py:hash", "elsewhere.py:helper"]}]}
        p = canvas.paint(g, overlay, story)
        self.assertEqual(p["files"], {"f:deep.py": {"kind": "changed", "syms": ["hash"]},
                                      "f:shared.py": {"kind": "new", "syms": ["audit"]}})
        self.assertEqual([o["path"] for o in p["off_files"]], ["elsewhere.py"])
        ch = p["story"]["chapters"][0]
        self.assertEqual((ch["n"], ch["files"], ch["steps"]), (1, ["f:deep.py", "o:elsewhere.py"], ["s:sign-in/log-in"]))
        self.assertIn("s:sign-in/log-in", p["steps"])


class Page(unittest.TestCase):
    def test_draws_an_existing_atlas_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "canvas.html"
            said = flowmap("canvas", "--from", str(BENCH), "--out", str(out))
            self.assertIn("7 flows, 26 steps, 8 files", said)
            html = out.read_text()
            self.assertIn("<title>Full Stack FastAPI Template · flowmap canvas</title>", html)
            data = json.loads(html.split("const EMBEDDED = ", 1)[1].split(";\n", 1)[0])
            self.assertEqual(data["files"]["f:crud.py"]["depth"], 1)
            self.assertNotIn("__CANVAS", html)

    def test_link_carries_the_map_in_its_fragment_to_the_viewers_canvas_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"FLOWMAP_VIEWER": "https://v.example/v1/change.html"}):
                said = flowmap("canvas", "--from", str(BENCH), "--out", str(Path(tmp) / "canvas.html"), "--link")
        url = said.strip()
        self.assertTrue(url.startswith("https://v.example/v1/canvas.html#v1."), url[:60])
        packed = base64.urlsafe_b64decode(url.split("#v1.", 1)[1] + "==")
        data = json.loads(zlib.decompress(packed, -15))
        self.assertEqual(data["name"], "Full Stack FastAPI Template")
        self.assertEqual(data["files"]["f:crud.py"]["depth"], 1)

    def test_viewer_page_holds_no_data_and_can_make_no_requests(self):
        html = canvas.viewer_html()
        self.assertIn("default-src 'none'", html)
        self.assertNotIn("fonts.googleapis", html)
        self.assertNotIn("__CANVAS_NAME__", html)
        self.assertIn("/*__CANVAS_DATA__*/null", html)


if __name__ == "__main__":
    unittest.main()
