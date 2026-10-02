"""Turn N independent map runs into one map, by agreement.

Endpoints are the join key, so no prose matching is needed:

- flow placement: each run votes a flow per endpoint; >= AGREE of the runs = agreed.
- steps: two endpoints share a step when >= AGREE of the runs grouped them together;
  connected components of that graph are the consensus steps.
- code path: a hop survives when >= 2 runs cite it; hop count is the step's busyness.
- evidence ladder per step: cited -> agreed -> tested -> confirmed (human, decisions.json).

Disagreements are not noise: they are written to QUESTIONS.md as the places a human
should look.

    python tools/flowmap/reconcile.py docs/flowmap/runs/*.json
"""

import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

ROOT = config.root()
OUT = config.out()
FLOW_ORDER = config.flow_order()
LADDER = ["single-source", "contested", "agreed", "tested", "confirmed"]


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)

    def groups(self, items):
        out = defaultdict(list)
        for i in items:
            out[self.find(i)].append(i)
        return list(out.values())


def canonical_new_flows(runs):
    """Runs invent `new:*` flows independently; merge ones covering the same endpoints."""
    news = []  # (run_id, flow_id, endpoints)
    for r in runs:
        for f in r["flows"]:
            if f["id"].startswith("new:"):
                eps = {e for s in f["steps"] for e in s.get("endpoints", [])}
                news.append((r["run_id"], f["id"], eps))
    uf = UnionFind()
    keys = [(rid, fid) for rid, fid, _ in news]
    for i, (ri, fi, ei) in enumerate(news):
        uf.find((ri, fi))
        for rj, fj, ej in news[i + 1:]:
            if ri != rj and jaccard(ei, ej) >= 0.3:
                uf.union((ri, fi), (rj, fj))
    rename = {}
    for group in uf.groups(keys):
        name = Counter(fid for _, fid in group).most_common(1)[0][0]
        if name.removeprefix("new:") in FLOW_ORDER:
            name = name.removeprefix("new:")  # the human adopted it into the vocabulary
        for k in group:
            rename[k] = name
    return rename


def path_regex(path):
    return re.compile(re.sub(r"\\\{[^}]+\\\}", r"[^/\"'`?]+", re.escape(path)) + r"(?![\w/])")


TEST_EXT = {".py", ".rb", ".ts", ".tsx", ".js", ".jsx", ".mjs"}


def tested_endpoints(inventory):
    """Entry points a test names: their concrete path, or an alias such as a Rails path
    helper (cheap, honest proxy). Test dirs come from flowmap.toml [code].tests."""
    text = "\n".join(p.read_text(errors="replace") for d in config.load()["code"]["tests"]
                     for p in (ROOT / d).rglob("*") if p.suffix in TEST_EXT and p.is_file())
    hits = set()
    for e in inventory:
        kind, _, target = e["endpoint"].partition(" ")
        if kind == "CLI":
            module = e["handler"].rsplit(":", 1)[0].rsplit("/", 1)[-1].removesuffix(".py")
            target_hit = re.search(rf"\b{re.escape(module)}\.py\b|\bimport\s+{re.escape(module)}\b|"
                                   rf"['\"]{re.escape(target.split(' ', 1)[-1])}['\"]", text) if " " in target else None
        elif kind == "ACTION":
            target_hit = re.search(rf"\b{re.escape(target.rsplit('#', 1)[1])}\b", text)
        else:
            target_hit = path_regex(re.sub(r"\{(\w+):\w+\}", r"{\1}", target)).search(text)
        if target_hit or any(re.search(rf"\b{re.escape(a)}\b", text) for a in e.get("aliases", [])):
            hits.add(e["endpoint"])
    return hits


def main(paths):
    runs = [json.loads(Path(p).read_text()) for p in paths]
    n = len(runs)
    agree = max(2, math.ceil(0.75 * n))
    inventory = json.loads((OUT / "inventory.json").read_text())["endpoints"]
    handler = {e["endpoint"]: e["handler"] for e in inventory}
    decisions_path = OUT / "decisions.json"
    decisions = json.loads(decisions_path.read_text()) if decisions_path.exists() else {}
    pinned_flow = decisions.get("endpoint_flow", {})
    confirmed = set(decisions.get("confirmed_steps", []))

    rename = canonical_new_flows(runs)

    # endpoint -> run -> (flow, step dict, position)
    placements = defaultdict(dict)
    for r in runs:
        for f in r["flows"]:
            fid = rename.get((r["run_id"], f["id"]), f["id"])
            for pos, s in enumerate(f["steps"]):
                for ep in s.get("endpoints", []):
                    # first placement wins for flow voting; extra placements are shared use
                    placements[ep].setdefault(r["run_id"], (fid, s, pos / max(1, len(f["steps"]))))

    # --- flow votes
    endpoint_flow, flow_status, contested, ties = {}, {}, [], []
    for ep in handler:
        votes = Counter(fid for fid, _, _ in placements[ep].values())
        if ep in pinned_flow:
            endpoint_flow[ep], flow_status[ep] = pinned_flow[ep], "confirmed"
            continue
        if not votes:
            endpoint_flow[ep], flow_status[ep] = None, "unplaced"
            continue
        (top, count), = votes.most_common(1)
        endpoint_flow[ep] = top
        flow_status[ep] = "agreed" if count >= agree else "contested" if count >= 2 else "single-source"
        if len(votes) > 1:
            contested.append((ep, {rid: fid for rid, (fid, _, _) in placements[ep].items()}))
        if [c for _, c in votes.most_common()].count(count) > 1:
            ties.append((ep, [f for f, c in votes.items() if c == count]))

    # Ties go where the rest of the endpoint's router file agreed to live; still a question.
    module_flows = defaultdict(Counter)
    for ep, fid in endpoint_flow.items():
        if fid and flow_status[ep] in ("agreed", "confirmed"):
            module_flows[handler[ep].rsplit(":", 1)[0]][fid] += 1
    for ep, options in ties:
        affinity = module_flows[handler[ep].rsplit(":", 1)[0]]
        endpoint_flow[ep] = max(options, key=lambda f: (affinity[f], f == endpoint_flow[ep]))

    # --- step clustering by co-grouping
    together = Counter()
    for r in runs:
        for f in r["flows"]:
            for s in f["steps"]:
                eps = sorted(set(s.get("endpoints", [])))
                for i, a in enumerate(eps):
                    for b in eps[i + 1:]:
                        together[(a, b)] += 1
    uf = UnionFind()
    for ep in handler:
        uf.find(ep)
    for (a, b), c in together.items():
        if c >= agree and endpoint_flow.get(a) == endpoint_flow.get(b):
            uf.union(a, b)

    tested = tested_endpoints(inventory)
    flows = defaultdict(list)
    for group in uf.groups(handler):
        fid = endpoint_flow[group[0]]
        if fid is None:
            continue
        g = set(group)
        # every run's step that overlaps this group, best match first
        matches = []
        for r in runs:
            best = None
            for f in r["flows"]:
                for pos, s in enumerate(f["steps"]):
                    j = jaccard(g, set(s.get("endpoints", [])))
                    if j and (best is None or j > best[0]):
                        best = (j, s, pos / max(1, len(f["steps"])), r["run_id"])
            if best:
                matches.append(best)
        matches.sort(key=lambda m: -m[0])
        exact = sum(1 for m in matches if m[0] == 1.0)
        status = "agreed" if exact >= agree else "contested" if len(matches) >= 2 else "single-source"
        if all(flow_status[e] == "single-source" for e in g):
            status = "single-source"
        elif status == "agreed" and any(flow_status[e] not in ("agreed", "confirmed") for e in g):
            status = "contested"  # grouped alike, but the runs disagree which flow it's in
        hop_votes, hop_pos = Counter(), defaultdict(list)
        for _, s, _, _ in matches:
            path = s.get("code_path", [])
            for i, h in enumerate(dict.fromkeys(path)):
                hop_votes[h] += 1
                hop_pos[h].append(i / max(1, len(path)))
        hops = sorted((h for h, c in hop_votes.items() if c >= 2 or n == 1),
                      key=lambda h: sum(hop_pos[h]) / len(hop_pos[h]))
        disputed_hops = sorted(h for h, c in hop_votes.items() if c == 1 and n > 1)
        names = [m[1]["name"] for m in matches]
        sid = Counter(m[1]["id"] for m in matches).most_common(1)[0][0]
        level = status
        if status == "agreed" and g <= tested:
            level = "tested"
        if f"{fid}/{sid}" in confirmed:
            level = "confirmed"
        flows[fid].append({
            "id": sid,
            "name": names[0],
            "alt_names": sorted(set(names[1:]) - {names[0]}),
            "actor": Counter(m[1].get("actor", "?") for m in matches).most_common(1)[0][0],
            "endpoints": sorted(g),
            "ui": sorted({u for m in matches for u in m[1].get("ui", [])}),
            "code_path": hops,
            "disputed_hops": disputed_hops,
            "writes": sorted({w for m in matches for w in m[1].get("writes", [])}),
            "busyness": {"hops": len(hops), "files": len({h.rsplit(":", 1)[0] for h in hops})},
            "evidence": level,
            "untested_endpoints": sorted(g - tested),
            "runs": sorted({m[3] for m in matches}),
            "position": sum(m[2] for m in matches) / len(matches),
        })

    # endpoint-less steps (pure UI or system): cluster across runs by code_path overlap
    loose = [(r["run_id"], rename.get((r["run_id"], f["id"]), f["id"]), s)
             for r in runs for f in r["flows"] for s in f["steps"] if not s.get("endpoints")]
    uf2 = UnionFind()
    for i, (ri, fi, si) in enumerate(loose):
        uf2.find(i)
        for j in range(i + 1, len(loose)):
            rj, fj, sj = loose[j]
            anchors_i = set(si.get("code_path", []) + si.get("ui", []))
            anchors_j = set(sj.get("code_path", []) + sj.get("ui", []))
            if ri != rj and fi == fj and jaccard(anchors_i, anchors_j) >= 0.3:
                uf2.union(i, j)
    for group in uf2.groups(range(len(loose))):
        members = [loose[i] for i in group]
        run_ids = {m[0] for m in members}
        if len(run_ids) < 2:
            continue  # a code-only step only one run saw stays out of the map (see QUESTIONS)
        fid = Counter(m[1] for m in members).most_common(1)[0][0]
        hop_votes = Counter(h for m in members for h in dict.fromkeys(m[2].get("code_path", [])))
        hops = [h for h, c in hop_votes.items() if c >= 2]
        flows[fid].append({
            "id": Counter(m[2]["id"] for m in members).most_common(1)[0][0],
            "name": members[0][2]["name"],
            "alt_names": sorted({m[2]["name"] for m in members[1:]} - {members[0][2]["name"]}),
            "actor": Counter(m[2].get("actor", "?") for m in members).most_common(1)[0][0],
            "endpoints": [],
            "ui": sorted({u for m in members for u in m[2].get("ui", [])}),
            "code_path": hops,
            "disputed_hops": sorted(h for h, c in hop_votes.items() if c == 1),
            "writes": sorted({w for m in members for w in m[2].get("writes", [])}),
            "busyness": {"hops": len(hops), "files": len({h.rsplit(":", 1)[0] for h in hops})},
            "evidence": "agreed" if len(run_ids) >= agree else "contested",
            "untested_endpoints": [],
            "runs": sorted(run_ids),
            "position": 0.5,
        })

    summaries = defaultdict(list)
    for r in runs:
        for f in r["flows"]:
            summaries[rename.get((r["run_id"], f["id"]), f["id"])].append(f.get("summary", ""))
    order = FLOW_ORDER + sorted(set(flows) - set(FLOW_ORDER))
    the_map = {
        "runs": [r["run_id"] for r in runs],
        "agree_threshold": agree,
        "flows": [{
            "id": fid,
            "summary": next((s for s in summaries[fid] if s), ""),
            "steps": sorted(flows[fid], key=lambda s: (round(s["position"], 6), s["endpoints"][:1], s["id"])),
        } for fid in order if fid in flows],
    }
    for f in the_map["flows"]:
        for s in f["steps"]:
            del s["position"]
    (OUT / "map.json").write_text(json.dumps(the_map, indent=1) + "\n")
    write_map_md(the_map)
    write_questions_md(runs, the_map, contested, endpoint_flow, flow_status, handler, ties)
    counts = Counter(s["evidence"] for f in the_map["flows"] for s in f["steps"])
    print(f"{len(the_map['flows'])} flows, {sum(counts.values())} steps: "
          + ", ".join(f"{counts[k]} {k}" for k in LADDER if counts[k]))


def write_map_md(m):
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    lines = [
        "# Flow map",
        "",
        f"_Generated by `tools/flowmap/reconcile.py` from runs {', '.join(m['runs'])} at `{commit}`. "
        "Do not hand-edit — pin decisions in `decisions.json` and re-run._",
        "",
        "Evidence: **confirmed** (you said so) > **tested** (agreed + a backend test hits every endpoint) "
        "> **agreed** (runs independently grouped it the same way) > **contested** > **single-source**. "
        "Busyness = consensus code hops / files.",
        "",
    ]
    for f in m["flows"]:
        lines += [f"## {f['id']}", "", f"_{f['summary']}_", "",
                  "| # | Step | Actor | Evidence | Busy | Endpoints |", "|---|---|---|---|---|---|"]
        for i, s in enumerate(f["steps"], 1):
            eps = "<br>".join(f"`{e}`" for e in s["endpoints"]) or "—"
            lines.append(f"| {i} | {s['name']} | {s['actor']} | {s['evidence']} | "
                         f"{s['busyness']['hops']}/{s['busyness']['files']} | {eps} |")
        lines.append("")
    (OUT / "MAP.md").write_text("\n".join(lines))


def write_questions_md(runs, m, contested, endpoint_flow, flow_status, handler, ties):
    lines = ["# Open questions from the flow map", "",
             "Where independent runs disagreed. Each answer can be pinned in `decisions.json`.", ""]
    proposed = [f for f in m["flows"] if f["id"].startswith("new:")]
    if proposed:
        lines += ["## Proposed flows (name them, then paste into flowmap.toml)", "",
                  "Passes proposed these flows independently; ones covering the same entry points were "
                  "merged. Rename, merge or drop them, then paste the block into `flowmap.toml`. "
                  "From then on they are your fixed vocabulary.", "",
                  "| proposed id | steps | entry points | seen by | summary |", "|---|---|---|---|---|"]
        for f in proposed:
            eps = sum(len(s["endpoints"]) for s in f["steps"])
            seen = sorted({r for s in f["steps"] for r in s["runs"]})
            lines.append(f"| `{f['id']}` | {len(f['steps'])} | {eps} | {', '.join(seen)} | {f['summary']} |")
        lines += ["", "```toml"]
        for f in proposed:
            lines += ["[[flows.vocabulary]]", f'id = "{f["id"].removeprefix("new:")}"',
                      f'scope = "{f["summary"].replace(chr(34), chr(39))}"']
        lines += ["```", ""]
    lines += ["## Split votes (placed by router-file affinity — please decide)", ""]
    for ep, options in sorted(ties):
        lines.append(f"- `{ep}`: {' vs '.join(options)} → placed in **{endpoint_flow[ep]}**")
    lines += ["", "## Endpoints the runs put in different flows", ""]
    for ep, by_run in sorted(contested):
        votes = ", ".join(f"{rid}→{fid}" for rid, fid in sorted(by_run.items()))
        lines.append(f"- `{ep}` (`{handler[ep]}`): {votes}")
    unplaced = defaultdict(list)
    for r in runs:
        for u in r.get("unplaced_endpoints", []):
            unplaced[u["endpoint"]].append(f"{r['run_id']}: {u.get('why', '')}")
    lines += ["", "## Endpoints at least one run could not place in any flow", ""]
    for ep in sorted(unplaced):
        lines.append(f"- `{ep}` — " + " · ".join(unplaced[ep]))
    lines += ["", "## Busiest steps (hops ≥ 8)", ""]
    for f in m["flows"]:
        for s in f["steps"]:
            if s["busyness"]["hops"] >= 8:
                lines.append(f"- {f['id']} / **{s['name']}** — {s['busyness']['hops']} hops over "
                             f"{s['busyness']['files']} files")
    lines += ["", "## Observations (\"fighting the system\"), by run", ""]
    for r in runs:
        lines.append(f"### {r['run_id']} ({r.get('method', '?')})")
        lines += [f"- {o}" for o in r.get("observations", [])] + [""]
    (OUT / "QUESTIONS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1:])
