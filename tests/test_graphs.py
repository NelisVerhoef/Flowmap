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

    def test_python_doc_is_the_first_paragraph(self):
        text = 'def f():\n    """Does a thing,\n    in two lines.\n\n    Details nobody reads."""\n\ndef g():\n    pass\n'
        self.assertEqual(graphs.python.doc(text, "f"), "Does a thing, in two lines.")
        self.assertIsNone(graphs.python.doc(text, "g"))
        self.assertIsNone(graphs.python.doc(text, "missing"))

    def test_defs_inside_blocks_keep_their_scope_name(self):
        text = ("try:\n    def fast():\n        pass\nexcept ImportError:\n    pass\n"
                "def outer(x):\n    if x:\n        def inner(y=2):\n            pass\n"
                "    with x:\n        class C:\n            pass\n")
        self.assertEqual(graphs.python.symbols(text),
                         [(2, 3, "fast"), (6, 12, "outer"), (8, 9, "outer.inner"), (11, 12, "outer.C")])
        self.assertEqual(graphs.python.signature(text, "outer.inner"), "y=2")
        self.assertTrue(graphs.python.same(text, text.replace("pass", "pass  # same"), "outer.inner"))


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


class PythonResolutionTest(unittest.TestCase):
    def edges(self, files):
        root, base = fixture_repo(self, {**cli_app(), **files})
        return json.loads(flowmap("callgraph", "dump", base, root=root))["edges"]

    def test_constructing_a_class_runs_its_init(self):
        edges = self.edges({"tool/loud.py": '''
            from helpers import shout


            class Loud:
                def __init__(self, s):
                    self.s = shout(s)
        '''})
        self.assertIn(["tool/loud.py:Loud", "tool/loud.py:Loud.__init__"], edges)

    def test_calls_through_a_registry_of_modules_reach_its_functions(self):
        edges = self.edges({
            "tool/plugins/__init__.py": "from . import loud\n\nPLUGINS = [loud]\n",
            "tool/plugins/loud.py": "def render(s):\n    return s.upper()\n",
            "tool/each.py": '''
                import plugins


                def render_all(s):
                    return [p.render(s) for p in plugins.PLUGINS]


                def unrelated(x):
                    return x.shout(1)
            ''',
        })
        self.assertIn(["tool/each.py:render_all", "tool/plugins/loud.py:render"], edges)
        # helpers is imported by name, never passed around as a module: x.shout() is not its shout
        self.assertNotIn(["tool/each.py:unrelated", "tool/helpers.py:shout"], edges)

    def test_flowmap_sees_its_own_builders(self):
        edges = json.loads(flowmap("callgraph", "dump"))["edges"]
        self.assertIn(["flowmap/callgraph.py:Graph.__init__", "flowmap/graphs/python.py:build"], edges)
        self.assertIn(["flowmap/lens.py:defs", "flowmap/graphs/python.py:symbols"], edges)
        self.assertIn(["flowmap/callgraph.py:Graph", "flowmap/callgraph.py:Graph.__init__"], edges)
