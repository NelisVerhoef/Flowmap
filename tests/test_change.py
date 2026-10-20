"""The change page's facts are right, and the story can't claim what the facts don't back.
Cases come from this repo's own history: PR #10 (4247d94..2559b22) and PR #4 (0d82693)."""

import json
import os
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
        # both parts of PR #10 sit on the atlas step; each move belongs to one of them. (build's
        # map(d.component, ...) reached Diagrams.component before PR #10, so that one didn't move)
        self.assertEqual(self.fx["reach"]["cause"]["gained"], {
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
        cls.fx = {**json.loads(flowmap("change", *PR10, "--facts")), "hunks": [{**h, "symbols": []} for h in change.hunks(*PR10)]}

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
            self.assertTrue(any(word in p["problem"] for p in problems), word)
        self.assertEqual({p["subject"] for p in problems}, {
            "chapters[0].symbols", "chapters[0].files", "no_longer[0].cite", "no_longer[1].cite",
            "chapters[0].verified[0].what", "chapters[0].verified[1].how"})

    def test_a_cited_line_must_be_one_the_diff_shows(self):
        # PR #10's first atlas.template.html hunk shows lines 7-15 at head; line 1 and 5000 it leaves alone
        cite = lambda c: self.lint({"no_longer": [{"was": "w", "cite": c}], "chapters": [{"title": "t"}]})
        self.assertEqual(cite("flowmap/atlas.template.html:120"), [])
        self.assertEqual(cite("flowmap/atlas.template.html:3-8"), [])  # a span that touches the diff
        self.assertEqual(cite("flowmap/atlas.py:merges"), [])  # a symbol, not a line
        self.assertEqual([p["code"] for p in cite("flowmap/atlas.template.html:1")], ["story/cite-not-in-diff"])

    def test_no_story_no_lint(self):
        self.assertEqual(self.lint({}), [])


class LinkSizeTest(unittest.TestCase):
    """Issue #13: a plan doc and a call path per step pushed an ordinary PR's link past a PR body."""

    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads(flowmap("change", *PR10, "--facts"))

    def test_only_files_the_story_claims_keep_their_diff_text(self):
        fx = {**self.fx, "hunks": [{"file": "README.md", "symbols": [], "lines": ["+x"]},
                                   {"file": "flowmap/atlas.template.html", "symbols": [], "lines": ["+y"]}]}
        story = {"chapters": [{"title": "t", "symbols": [], "files": ["flowmap/atlas.template.html"]}]}
        self.assertEqual([h["file"] for h in change.merge(fx, story)["facts"]["hunks"]], ["flowmap/atlas.template.html"])
        self.assertEqual(change.merge(fx, {})["facts"]["hunks"], [])

    def test_one_call_path_per_flow_and_one_on_the_page(self):
        flow = {st["key"]: f["id"] for f in self.fx["map"] for st in f["steps"]}
        for s in self.fx["symbols"]:
            self.assertEqual(len(s["witness"]), len({flow[k] for k in s["witness"]}), s["id"])
        self.assertTrue(all(len(s["witness"]) <= 1 for s in change.merge({**self.fx, "hunks": []}, {})["facts"]["symbols"]))

    def test_an_oversized_link_drops_diff_text_and_says_so(self):
        big = [{"file": "flowmap/atlas.py", "symbols": ["x"], "lines": [f"+{i} {hash(i * 7.1)}" for i in range(9000)]}]
        url, dropped = change.fitted_link(change.merge({**self.fx, "hunks": big}, {}), "https://v")
        self.assertLessEqual(len(url), change.BUDGET)
        self.assertEqual(dropped, ["diff text of non-code files", "all diff text"])
        data = change.merge({**self.fx, "hunks": []}, {"intent": os.urandom(60000).hex()})
        self.assertIsNone(change.fitted_link(data, "https://v")[0])  # main prints a line to paste instead


if __name__ == "__main__":
    unittest.main()
