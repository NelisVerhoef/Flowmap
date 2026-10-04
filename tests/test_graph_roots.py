import json
import unittest

from tests.helpers import cli_app, commit, fixture_repo, flowmap

REACH = "- `tool/helpers.py:shout` — reachable from 1 endpoints in 0 flows"


class GraphRootsTest(unittest.TestCase):
    def lens_after_editing_helper(self, code):
        root, base = fixture_repo(self, cli_app(code))
        head = commit(root, {"tool/helpers.py": "def shout(s):\n    return s.upper() + '!'\n"})
        return flowmap("lens", base, head, root=root)

    def test_graph_key_drives_reach(self):
        self.assertIn(REACH, self.lens_after_editing_helper('graph = ["tool"]'))

    def test_python_key_still_works(self):
        self.assertIn(REACH, self.lens_after_editing_helper('python = ["tool"]'))

    def test_no_graph_roots_means_no_reach(self):
        out = self.lens_after_editing_helper('tests = []')
        self.assertIn("# Flow lens:", out)
        self.assertNotIn("## Reach", out)

    def test_vendored_dirs_and_missing_roots_stay_out(self):
        files = cli_app('graph = ["tool", "later"]')
        files["tool/node_modules/dep/index.py"] = "def vendored():\n    pass\n"
        files["tool/.venv/lib/site.py"] = "def vendored():\n    pass\n"
        root, base = fixture_repo(self, files)
        for args in (("callgraph", "dump", base), ("callgraph", "dump")):
            with self.subTest(args=args):
                defs = json.loads(flowmap(*args, root=root))["defs"]
                self.assertIn("tool/helpers.py:shout", defs)
                self.assertEqual([d for d in defs if "node_modules" in d or ".venv" in d], [])
