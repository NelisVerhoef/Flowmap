import json
import sys
import unittest

from tests.helpers import REPO, cli_app, fixture_repo, flowmap

sys.path.insert(0, str(REPO / "flowmap"))
import graphs  # noqa: E402


class RegistryTest(unittest.TestCase):
    def test_builder_dispatch_by_suffix(self):
        self.assertIs(graphs.builder_for("app/x.py"), graphs.python)
        self.assertIsNone(graphs.builder_for("app/page.tsx"))
        self.assertIn(".py", graphs.suffixes())

    def test_python_symbols_and_signature(self):
        text = "class A:\n    def m(self, x=1):\n        pass\n"
        self.assertEqual(graphs.python.symbols(text), [(1, 3, "A"), (2, 3, "A.m")])
        self.assertEqual(graphs.python.signature(text, "A.m"), "self, x=1")
        self.assertIsNone(graphs.python.signature(text, "A"))


class PythonBuilderTest(unittest.TestCase):
    def test_unparseable_file_is_skipped(self):
        files = cli_app()
        files["tool/broken.py"] = "def oops(:\n"
        root, base = fixture_repo(self, files)
        for args in (("callgraph", "dump", base), ("callgraph", "dump")):
            with self.subTest(args=args):
                g = json.loads(flowmap(*args, root=root))
                self.assertIn(["tool/run.py:main", "tool/helpers.py:shout"], g["edges"])
                self.assertIn(["tool/run.py:__main__", "tool/run.py:main"], g["edges"])
                self.assertFalse([d for d in g["defs"] if d.startswith("tool/broken.py")])
