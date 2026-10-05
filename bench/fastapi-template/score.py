"""Score flowmap against the planted changes -> RESULTS.md and results/score.json.

Per change, what each source of truth and each reviewer said:

  CI        the repo's own tests                               (results/<pr>.json)
  prod      holdout invariants on seeded data + deploy replay  (results/<pr>.json)
  lens v0   `flowmap lens` as first shipped, at a95be17, Python 3.11 (results/lens-v0-py311/)
            QUIET = it printed nothing about existing code
  lens v1   with this bench's fixes, under Python 3.11 and the project's 3.14
            (results/lens-v1-py311/, results/lens-v1-py314/): its own contained/spreads/blind verdict
  LLM       the pr-lens skill run blind (llm/), and a plain diff review without flowmap (llm-control/)

    python score.py /path/to/full-stack-fastapi-template
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"


def llm_verdict(folder, pid):
    f = HERE / folder / f"{pid}.md"
    if not f.exists():
        return None
    m = re.findall(r"VERDICT:\s*`?([a-z-]+)", f.read_text())
    return m[-1] if m else "?"


def v0_quiet(lens):
    diff = lens.get("reach_diff", {})
    listed_off_map = [c for c in lens["off_map"] if not c.endswith(":<module>")]
    modified_reach = any(lens["reach"].get(c) for c in set(lens["changed"]) - set(lens["new_symbols"]))
    return not (lens["touched"] or modified_reach or diff.get("gained") or diff.get("lost")
                or lens["endpoints_added"] or lens["endpoints_removed"] or listed_off_map)


def v0_flagged(lens):
    modified = set(lens["changed"]) - set(lens["new_symbols"])
    diff = lens.get("reach_diff", {})
    return ({e for c in modified for e in lens["reach"].get(c, [])} | set(lens["endpoints_removed"])
            | {e for v in list(diff.get("gained", {}).values()) + list(diff.get("lost", {}).values()) for e in v})


def main(repo):
    key = {k: v for k, v in json.loads((HERE / "answer_key.json").read_text()).items() if not k.startswith("_")}
    inv = json.loads((Path(repo) / "docs/flowmap/inventory.json").read_text())["endpoints"]
    the_map = json.loads((Path(repo) / "docs/flowmap/map.json").read_text())
    runtime = json.loads((RES / "runtime_reach.json").read_text())
    ep_of_handler = defaultdict(set)
    for e in inv:
        ep_of_handler[e["handler"]].add(e["endpoint"])
    flows_of = defaultdict(set)
    for f in the_map["flows"]:
        for s in f["steps"]:
            for e in s["endpoints"]:
                flows_of[e].add(f["id"])
    ran = defaultdict(set)   # symbol -> endpoints that actually executed it on main (both suites)
    for handler, syms in runtime["endpoints"].items():
        for s in syms + [handler]:
            ran[s] |= ep_of_handler.get(handler, set())

    rows = []
    for pid, k in sorted(key.items()):
        r = json.loads((RES / f"{pid}.json").read_text())
        hold = {t: v for t, v in r["holdout"].items() if isinstance(v, dict) and v["outcome"] == "failed"}
        v0 = json.loads((RES / "lens-v0-py311" / f"{pid}.json").read_text())
        v1 = {cfg: json.loads((RES / f"lens-{cfg}" / f"{pid}.json").read_text()) for cfg in ("v1-py311", "v1-py314")}
        fixed = v1["v1-py314"]
        truth = set(k["affected"]) - {"deploy"}
        spreads = set(fixed.get("spreads_to", []))
        modified = set(fixed.get("changed", [])) - set(fixed.get("new_symbols", []))
        executed = {e for c in modified for e in ran.get(c, set())}
        row = {
            "id": pid, "short": k["short"], "subtlety": k["subtlety"], "kind": k["kind"],
            "breaks_prod": k["breaks_prod"], "expected": k["expected"], "what": k["what"], "truth": sorted(truth),
            "ci_caught": bool(r["ci"]["failed"]) or not r["ci"]["migrate_ok"], "ci_failed": r["ci"]["failed"],
            "deploy_ok": r["deploy"]["ok"], "holdout_failed": sorted(hold),
            "prod_caught": bool(hold) or not r["deploy"]["ok"],
            "v0": "crashed" if "_error" in v0 else "quiet" if v0_quiet(v0) else "speaks",
            "v0_flagged": sorted(v0_flagged(v0)) if "_error" not in v0 else [],
            "v1_py311": v1["v1-py311"].get("verdict", "crashed"),
            "v1": fixed.get("verdict", "crashed"), "v1_spreads": sorted(spreads),
            "v1_flows": sorted({f for e in spreads for f in flows_of.get(e, ())}),
            "v1_blind": fixed.get("blind", []), "v1_lost": fixed.get("reach_diff", {}).get("lost", {}),
            "v1_gained": fixed.get("reach_diff", {}).get("gained", {}),
            "missed": sorted(truth - spreads), "extra": sorted(spreads - truth),
            "executed": sorted(executed), "static_not_executed": sorted(spreads - executed - truth),
            "llm": llm_verdict("llm", pid), "llm_control": llm_verdict("llm-control", pid),
        }
        row["v0_false_comfort"] = k["breaks_prod"] and row["v0"] == "quiet"
        row["v1_false_comfort"] = k["breaks_prod"] and row["v1"] == "contained"
        rows.append(row)
    (RES / "score.json").write_text(json.dumps({r["id"]: r for r in rows}, indent=1))
    write_md(rows)


def tick(ok):
    return "✅" if ok else "❌"


def write_md(rows):
    prod = [r for r in rows if r["breaks_prod"]]
    benign = [r for r in rows if not r["breaks_prod"]]
    green = [r for r in prod if not r["ci_caught"]]
    with_truth = [r for r in rows if r["truth"]]
    hit = sum(len(set(r["truth"]) - set(r["missed"])) for r in with_truth)
    total = sum(len(r["truth"]) for r in with_truth)
    reviewed = [r for r in rows if r["llm"]]
    controlled = [r for r in rows if r["llm_control"]]

    def llm_ok(r, v):
        return (v in ("do-not-merge", "needs-answers")) if r["breaks_prod"] else v == "safe-to-merge"

    L = ["# Bench: 26 planted changes in the FastAPI full-stack template", "",
         "_Generated by `bench/fastapi-template/score.py`. See `bench/README.md` for the method._", "",
         "## Summary", "",
         f"- **{len(prod)}** of {len(rows)} changes break something for an existing deployment; {len(benign)} don't.",
         f"- **CI** (the repo's 58 tests) catches {sum(r['ci_caught'] for r in prod)} of {len(prod)}. "
         f"**{len(green)} would reach a reviewer green**: " + ", ".join(r["id"] for r in green) + ".",
         f"- **lens as first shipped** was quiet (said nothing about existing code) on "
         f"**{sum(r['v0_false_comfort'] for r in prod)}** prod-breaking changes and crashed on "
         f"{sum(r['v0'] == 'crashed' for r in rows)}.",
         f"- **lens after the bench's fixes** (project Python) says *contained* on "
         f"**{sum(r['v1_false_comfort'] for r in prod)}** prod-breaking changes; it says contained on "
         f"{sum(r['v1'] == 'contained' for r in benign)} of {len(benign)} harmless ones "
         f"({', '.join(r['id'] for r in benign if r['v1'] == 'contained')}). "
         f"Verdict matches the expected one on {sum(r['v1'] == r['expected'] for r in rows)}/{len(rows)}.",
         f"- Endpoint recall (static reach + reach diff): **{hit}/{total}** affected endpoints flagged after the fixes, "
         f"{sum(len(set(r['truth']) & set(r['v0_flagged'])) for r in with_truth)}/{total} before. "
         f"Over-reporting after the fixes: {sum(len(r['static_not_executed']) for r in rows)} flagged entry points "
         "that neither test suite ever saw execute the changed code (mostly model classes reached via ORM relationships).",
         f"- Under Python 3.11 the fixed lens says *blind* on {sum(r['v1_py311'] == 'blind' for r in rows)}/{len(rows)}: "
         "honest, but useless, because the app's auth module uses 3.14 syntax.",
         f"- **LLM review with flowmap** right on {sum(llm_ok(r, r['llm']) for r in reviewed)}/{len(reviewed)}; "
         f"**plain LLM review without flowmap** right on {sum(llm_ok(r, r['llm_control']) for r in controlled)}/{len(controlled)}.",
         "", "## Per change", "",
         "| PR | change | subtle | CI | prod | lens v0 | lens v1 | missed | LLM+map | LLM only |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        prod_cell = ("—" if not r["breaks_prod"] else
                     ("caught" if r["prod_caught"] else "not caught"))
        ci_cell = "—" if not r["breaks_prod"] else ("caught" if r["ci_caught"] else "**green**")
        v0 = f"**{r['v0']}**" if r["v0_false_comfort"] else r["v0"]
        v1 = f"**{r['v1']}**" if r["v1_false_comfort"] else r["v1"]
        v1 += f" ({len(r['v1_spreads'])})" if r["v1_spreads"] else ""
        L.append(f"| {r['id']} | {r['short']} | {r['subtlety'] or '–'} | {ci_cell} | {prod_cell} | {v0} | {v1} "
                 f"| {len(r['missed']) or '—'} | {r['llm'] or ''} | {r['llm_control'] or ''} |")
    L += ["", "_subtle: 1 = visible in the diff, 3 = looks like a harmless refactor. lens v1 (n) = existing entry "
          "points it says the change spreads to. **bold** = said nothing / contained on a change that breaks prod._",
          "", "## Per change, in detail", ""]
    for r in rows:
        L.append(f"### {r['id']}: {r['short']}")
        L.append(f"- **Truth:** {r['what']}")
        L.append(f"- **lens v1:** {r['v1']}" + (f", spreads to {len(r['v1_spreads'])} entry point(s) in "
                                               f"{', '.join(r['v1_flows']) or 'no mapped flow'}" if r["v1_spreads"] else ""))
        for s, eps in r["v1_lost"].items():
            L.append(f"  - no longer reachable: `{s.rsplit(':', 1)[1]}` from {', '.join(f'`{e}`' for e in eps)}")
        for s, eps in r["v1_gained"].items():
            L.append(f"  - newly reachable: `{s.rsplit(':', 1)[1]}` under {', '.join(f'`{e}`' for e in eps)}")
        for b in r["v1_blind"]:
            L.append(f"  - blind spot: {b}")
        if r["missed"]:
            L.append("- **Missed endpoints:** " + ", ".join(f"`{e}`" for e in r["missed"]))
        if r["static_not_executed"]:
            L.append(f"- **Over-reported** (static reach, never executed by either suite): {len(r['static_not_executed'])}")
        if r["holdout_failed"] or not r["deploy_ok"]:
            L.append("- **Prod:** " + ("deploy fails; " if not r["deploy_ok"] else "")
                     + ", ".join(f"`{t.split('::', 1)[1]}`" for t in r["holdout_failed"]))
        if r["ci_failed"]:
            L.append("- **CI:** " + ", ".join(f"`{t.split('::')[-1]}`" for t in r["ci_failed"]))
        L.append("")
    (HERE / "RESULTS.md").write_text("\n".join(L))
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main(sys.argv[1])
