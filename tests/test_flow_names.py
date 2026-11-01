"""Naming proposed flows: a vocabulary entry adopts the passes' proposal, under its id or a new one."""

import sys
import unittest
from unittest import mock

from tests.helpers import REPO

sys.path.insert(0, str(REPO / "flowmap"))
import reconcile  # noqa: E402


def run(rid, *flows):
    return {"run_id": rid, "flows": [{"id": fid, "steps": [{"endpoints": eps}]} for fid, eps in flows]}


RUNS = [run("bu-1", ("new:tell-a-change", ["CLI x change"]), ("new:browse", ["CLI x atlas"])),
        run("td-1", ("new:explain-a-change", ["CLI x change"]), ("new:browse", ["CLI x atlas"]))]


def vocabulary(*entries):
    return mock.patch.object(reconcile.config, "load", return_value={"flows": {"vocabulary": list(entries)}})


class FlowNames(unittest.TestCase):
    def test_unnamed_proposals_keep_their_majority_id(self):
        with vocabulary():
            names = set(reconcile.canonical_new_flows(RUNS).values())
        # the two change proposals merge into one flow, named by one of the runs' ids
        self.assertEqual(len(names), 2)
        self.assertIn("new:browse", names)
        self.assertTrue(names & {"new:tell-a-change", "new:explain-a-change"})

    def test_a_vocabulary_id_equal_to_the_proposal_adopts_it(self):
        with vocabulary({"id": "browse", "scope": ""}):
            rename = reconcile.canonical_new_flows(RUNS)
        self.assertEqual(rename[("bu-1", "new:browse")], "browse")

    def test_a_renamed_flow_names_the_proposal_it_adopts(self):
        # either run's id for the merged proposal ties it to the human's name
        for proposed in ("new:tell-a-change", "explain-a-change"):
            with vocabulary({"id": "review-a-change", "proposed": proposed, "scope": ""}):
                rename = reconcile.canonical_new_flows(RUNS)
            self.assertEqual({rename[("bu-1", "new:tell-a-change")], rename[("td-1", "new:explain-a-change")]},
                             {"review-a-change"}, proposed)
            self.assertEqual(rename[("bu-1", "new:browse")], "new:browse")


if __name__ == "__main__":
    unittest.main()
