import sys
import unittest

from tests.helpers import REPO, cli_app, fixture_repo, flowmap

sys.path.insert(0, str(REPO / "flowmap"))
import callgraph  # noqa: E402

NEXT_ROUTE = "export async function GET() {\n  return Response.json({ ok: true })\n}\n"


class ClassifyTest(unittest.TestCase):
    def test_sorts_handlers_by_whether_the_graph_can_walk_from_them(self):
        eps = [{"endpoint": "A", "handler": "a.py:f"}, {"endpoint": "B", "handler": "a.py:g"},
               {"endpoint": "C", "handler": "b.ts:GET"}]
        got = callgraph.classify(eps, {"a.py:f": (1, 2)}, {"a.py"})
        self.assertEqual({k: [e["endpoint"] for e in v] for k, v in got.items()},
                         {"node": ["A"], "not graphed": ["C"], "broken": ["B"]})


class CheckCommandTest(unittest.TestCase):
    def test_python_handlers_resolve(self):
        root, _ = fixture_repo(self, cli_app('graph = ["tool"]'))
        out = flowmap("callgraph", "check", root=root)
        self.assertIn("1 entry points: 1 handlers are graph nodes, 0 not graphed, 0 broken", out)

    def test_handler_without_builder_is_not_graphed_not_broken(self):
        files = cli_app('graph = ["tool"]', extra='\n[[entry]]\nadapter = "nextjs"\nroot = "web"\n')
        files["web/next.config.js"] = "module.exports = {}\n"
        files["web/app/api/ping/route.ts"] = NEXT_ROUTE
        root, _ = fixture_repo(self, files)
        out = flowmap("callgraph", "check", root=root)  # raises if it exits non-zero
        self.assertIn("2 entry points: 1 handlers are graph nodes, 1 not graphed, 0 broken", out)
        self.assertIn("NOT GRAPHED GET /api/ping -> web/app/api/ping/route.ts:GET (no builder for .ts)", out)
