"""Characterisation: flowmap's output on this repo's own history must not move while the call
graph is restructured. Regenerate only on purpose (python3 -m tests.test_golden --regen) and
read the diff: a changed golden is a behaviour change."""

import json
import sys
import unittest

from tests.helpers import REPO, flowmap

GOLDEN = REPO / "tests" / "golden"
BASE, HEAD = "6d9eaff", "770f1a7"


def facts(text):
    fx = json.loads(text)
    fx["symbols"] = sorted(fx["symbols"], key=lambda s: s["id"])  # built from a set: order varies per run
    return fx


CASES = {
    f"lens-{BASE}-{HEAD}.md": lambda: flowmap("lens", BASE, HEAD),
    f"change-facts-{BASE}-{HEAD}.json": lambda: flowmap("change", BASE, HEAD, "--facts"),
    f"graph-{BASE}.json": lambda: flowmap("callgraph", "dump", BASE),
    f"graph-{HEAD}.json": lambda: flowmap("callgraph", "dump", HEAD),
}


class GoldenTest(unittest.TestCase):
    def test_lens(self):
        name = f"lens-{BASE}-{HEAD}.md"
        self.assertEqual(CASES[name](), (GOLDEN / name).read_text())

    def test_change_facts(self):
        name = f"change-facts-{BASE}-{HEAD}.json"
        self.assertEqual(facts(CASES[name]()), facts((GOLDEN / name).read_text()))

    def test_graph_dumps(self):
        for ref in (BASE, HEAD):
            name = f"graph-{ref}.json"
            with self.subTest(ref=ref):
                self.assertEqual(json.loads(CASES[name]()), json.loads((GOLDEN / name).read_text()))


if __name__ == "__main__" and "--regen" in sys.argv:
    GOLDEN.mkdir(exist_ok=True)
    for name, run in CASES.items():
        (GOLDEN / name).write_text(run())
        print(f"wrote tests/golden/{name}")
