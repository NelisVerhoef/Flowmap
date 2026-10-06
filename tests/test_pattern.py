import contextlib
import io
import json
import sys
import unittest

from tests.helpers import REPO, fixture_repo, flowmap

sys.path.insert(0, str(REPO / "flowmap"))
import adapters  # noqa: E402
import reconcile  # noqa: E402

# the rules a setup session writes into flowmap.toml after reading the code
RULES = """
[[entry]]
adapter = "pattern"
files = ["svc/*.py"]
match = '''@\\w+\\.(?P<verb>get|post|put|patch|delete)\\(\\s*["'](?P<path>[^"']*)'''
endpoint = "{VERB} {path}"

[[entry]]
adapter = "pattern"
files = ["svc/*.py"]
match = '''\\.add_api_route\\(\\s*["'](?P<path>[^"']*)["']\\s*,\\s*(?P<handler>\\w+)'''
endpoint = "GET {path}"

[[entry]]
adapter = "pattern"
files = ["svc/mcp/*.py"]
match = '''@\\w+\\.tool\\b(?:\\([^)]*?\\bname\\s*=\\s*["'](?P<name>[^"']+))?'''
endpoint = "MCP {name|def}"

[code]
graph = ["svc"]
"""

APP = {
    "flowmap.toml": RULES,
    "docs/flowmap/map.json": '{"flows": [], "runs": []}\n',
    # routes on a module-level app, plus one registered by call
    "svc/app.py": '''
        from typing import TYPE_CHECKING

        from fastapi import FastAPI

        app = FastAPI(title="kg")

        if TYPE_CHECKING:
            def typed_only():
                pass


        @app.get("/health")
        async def health():
            return ok()


        @app.post("/search", response_model=dict)
        async def search(request):
            return ok()


        def ping():
            return ok()


        def ok():
            return {}


        app.router.add_api_route("/ping", ping)
    ''',
    # routes on an app built in a factory, one of them inside an `if`
    "svc/correct.py": '''
        from fastapi import FastAPI


        def build_app(static):
            app = FastAPI()

            @app.exception_handler(KeyError)
            def not_found(request, error):
                return None

            @app.get("/api/vocabulary")
            def vocabulary():
                return []

            if static.exists():
                app.mount("/static", static)

                @app.get("/page/{standard_id}/{page_num}")
                def deep_link_page(standard_id: str, page_num: int):
                    return vocabulary()

            return app
    ''',
    # a helper that receives the app
    "svc/sign_in.py": '''
        def add_sign_in_routes(app, *, signer):
            @app.post("/api/login")
            async def login(body, response):
                return signer(body)
    ''',
    "svc/mcp/server.py": '''
        def build_server(service):
            server = MCPServer("standards")

            @server.tool(description="Search the standards")
            async def search(ctx, query: str):
                return service.search(query)

            @server.tool(name="clause", description="One clause (by id)")
            async def get_clause(ctx, clause: str):
                return service.clause(clause)

            return server
    ''',
}


class PatternAdapterTest(unittest.TestCase):
    def setUp(self):
        self.root, self.base = fixture_repo(self, APP)

    def test_rules_find_every_route_and_tool_with_its_graph_handler(self):
        flowmap("inventory", root=self.root)
        eps = json.loads((self.root / "docs/flowmap/inventory.json").read_text())["endpoints"]
        self.assertEqual({e["endpoint"]: e["handler"] for e in eps}, {
            "GET /health": "svc/app.py:health",
            "POST /search": "svc/app.py:search",
            "GET /ping": "svc/app.py:ping",
            "GET /api/vocabulary": "svc/correct.py:build_app.vocabulary",
            "GET /page/{standard_id}/{page_num}": "svc/correct.py:build_app.deep_link_page",
            "POST /api/login": "svc/sign_in.py:add_sign_in_routes.login",
            "MCP search": "svc/mcp/server.py:build_server.search",
            "MCP clause": "svc/mcp/server.py:build_server.get_clause",
        })
        self.assertEqual(next(e["line"] for e in eps if e["endpoint"] == "GET /health"), 12)

    def test_every_handler_is_a_graph_node(self):
        out = flowmap("callgraph", "check", root=self.root)
        self.assertIn("8 entry points: 8 handlers are graph nodes, 0 not graphed, 0 broken", out)


class HandlerGroupTest(unittest.TestCase):
    def test_a_named_handler_is_the_nearest_definition_before_the_match(self):
        from adapters.pattern import _handler
        syms = [(1, 3, "a"), (2, 3, "a.show"), (5, 7, "b"), (6, 7, "b.show")]
        self.assertEqual([_handler(syms, line, "show")[2] for line in (0, 4, 8)], ["a.show", "a.show", "b.show"])


class ListAdapterTest(unittest.TestCase):
    def test_listed_entries_take_their_line_from_the_handler(self):
        text = {"jobs.py": "import x\n\n\ndef sync():\n    pass\n"}
        cfg = {"entry": [{"adapter": "list", "entries": [
            {"endpoint": "JOB nightly-sync", "handler": "jobs.py:sync"},
            {"endpoint": "JOB gone", "handler": "missing.py:f"}]}]}
        self.assertEqual(adapters.entries(cfg, text.get), [
            {"endpoint": "JOB gone", "handler": "missing.py:f", "line": 1},
            {"endpoint": "JOB nightly-sync", "handler": "jobs.py:sync", "line": 4}])


class DuplicateEndpointTest(unittest.TestCase):
    def entries(self, *listed):
        cfg = {"entry": [{"adapter": "list", "entries": [{"endpoint": e, "handler": h}] } for e, h in listed]}
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = adapters.entries(cfg, lambda rel: None)
        return [(e["endpoint"], e["handler"]) for e in got], err.getvalue()

    def test_two_handlers_for_one_endpoint_keep_the_first_and_say_so(self):
        got, err = self.entries(("GET /health", "a.py:health"), ("GET /health", "b.py:health"))
        self.assertEqual(got, [("GET /health", "a.py:health")])
        self.assertEqual(err, "flowmap: GET /health is handled by both a.py:health and b.py:health; "
                              "keeping a.py:health\n")

    def test_the_same_handler_found_twice_is_quietly_one(self):
        got, err = self.entries(("GET /health", "a.py:health"), ("GET /health", "a.py:health"))
        self.assertEqual((got, err), ([("GET /health", "a.py:health")], ""))


class TestedEndpointsTest(unittest.TestCase):
    def test_a_named_entry_is_tested_when_a_test_quotes_its_name(self):
        inv = [{"endpoint": "MCP search", "handler": "s.py:search"},
               {"endpoint": "MCP clause", "handler": "s.py:get_clause"}]
        text = "# search the standards first\nclient.call_tool('clause', {})\n"
        self.assertEqual(reconcile.tested_endpoints(inv, text), {"MCP clause"})


if __name__ == "__main__":
    unittest.main()
