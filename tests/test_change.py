"""The change page's facts are right, and the story can't claim what the facts don't back.
Cases come from this repo's own history: PR #10 (4247d94..2559b22) and PR #4 (0d82693)."""

import json
import sys
import unittest

from tests.helpers import REPO, flowmap

sys.path.insert(0, str(REPO / "flowmap"))
import change  # noqa: E402

PR10 = ("4247d94", "2559b22")


class FactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads(flowmap("change", *PR10, "--facts"))

    def test_tests_outside_the_code_dirs_count_as_tests(self):
        self.assertEqual(change.file_kind("tests/test_merges.py"), "test")
        self.assertEqual(self.fx["tests"]["changed"], ["tests/test_graphs.py", "tests/test_merges.py"])

    def test_a_reach_move_names_the_call_that_caused_it(self):
        # both parts of PR #10 sit on the atlas step; each move belongs to one of them
        self.assertEqual(self.fx["reach"]["cause"]["gained"], {
            "flowmap/diagrams.py:Diagrams.component": ["flowmap/atlas.py:merges"],
            "flowmap/graphs/python.py:_find": ["flowmap/atlas.py:functions", "flowmap/graphs/python.py:doc"],
            "flowmap/graphs/python.py:signature": ["flowmap/atlas.py:functions"]})

    def test_map_anchors_the_change_removed(self):
        fx = json.loads(flowmap("change", "0d82693^", "0d82693", "--facts"))
        gone = {a["anchor"] for a in fx["anchors_lost"]}
        self.assertEqual(gone, {"flowmap/callgraph.py:Graph._collect", "flowmap/callgraph.py:Graph._link",
                                "flowmap/callgraph.py:Graph._imports", "flowmap/lens.py:py_symbols"})


class LintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = {**json.loads(flowmap("change", *PR10, "--facts")), "hunks": []}

    def lint(self, story):
        return change.merge(self.fx, story)["lint"]

    def test_a_backed_story_passes(self):
        story = {"no_longer": [{"was": "Shared code is a chip band", "cite": "flowmap/atlas.template.html:120",
                                "step": "new:review-change-on-map/build-atlas"}],
                 "chapters": [{"title": "t", "symbols": ["flowmap/atlas.py:merges"], "files": ["flowmap/atlas.template.html"],
                               "verified": [{"how": "test", "what": "tests/test_merges.py:MergesTest"},
                                            {"how": "not checked", "what": "wire drawing"}]}]}
        self.assertEqual(self.lint(story), [])

    def test_unbacked_claims_are_named(self):
        story = {"no_longer": [{"was": "uncited"}, {"was": "cites code this change leaves alone", "cite": "flowmap/lens.py"}],
                 "chapters": [{"title": "t", "symbols": ["flowmap/atlas.py:nope"], "files": ["nope.md"],
                               "verified": [{"how": "test", "what": "tests/test_merges.py:test_no_such_test"},
                                            {"how": "guessed", "what": "x"}]}]}
        problems = self.lint(story)
        self.assertEqual(len(problems), 6, problems)
        for word in ("flowmap/atlas.py:nope", "nope.md", "uncited", "cites code", "test_no_such_test", "'guessed'"):
            self.assertTrue(any(word in p for p in problems), word)

    def test_no_story_no_lint(self):
        self.assertEqual(self.lint({}), [])


if __name__ == "__main__":
    unittest.main()
