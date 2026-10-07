"""Interchanges: the atlas draws where steps of different flows first run the same code."""

import sys
import unittest
from types import SimpleNamespace

from tests.helpers import REPO

sys.path.insert(0, str(REPO / "flowmap"))
import atlas  # noqa: E402

# a and b both call shared.py:meet, which calls shared.py:below; c, d and e only reach their own code.
EDGES = {"x.py:ha": {"shared.py:meet"}, "x.py:hb": {"shared.py:meet"}, "x.py:hc": {"x.py:own"},
         "shared.py:meet": {"shared.py:below"}}


def fake(edges=EDGES, flows=("a", "b", "c", "d", "e")):
    handlers = {f"E{f}": f"x.py:h{f}" for f in flows}
    reach = {}
    for h in handlers.values():
        seen, todo = {h}, [h]
        while todo:
            for n in edges.get(todo.pop(), ()):
                if n not in seen:
                    seen.add(n)
                    todo.append(n)
        reach[h] = seen
    the_map = {"flows": [{"id": f, "steps": [{"id": "s", "endpoints": [f"E{f}"]}]} for f in flows]}
    return SimpleNamespace(map=the_map, handler=handlers, reach=reach, plumbing=set(),
                           g=SimpleNamespace(edges=edges, bases={}), component=lambda n: None)


class MergesTest(unittest.TestCase):
    def test_flows_meet_at_the_first_shared_function_only(self):
        d = fake()
        [m] = atlas.merges(d, atlas.step_keys(d.map))
        self.assertEqual((m["file"], m["at"], m["steps"], m["flows"]), ("shared.py", ["meet"], ["a/s", "b/s"], 2))

    def test_code_most_entry_points_reach_is_plumbing(self):
        edges = {**EDGES, "x.py:hc": {"shared.py:meet"}}
        d = fake(edges)  # 3 of 5 entry points
        self.assertEqual(atlas.merges(d, atlas.step_keys(d.map)), [])


if __name__ == "__main__":
    unittest.main()
