"""Build the interactive system atlas (docs/flowmap/atlas.html) from the map and the call graph.

Positions are fixed by the flow vocabulary and the map's step order, so the picture stays
familiar between rebuilds. Optional PR overlays paint a change's reach onto it.

    python tools/flowmap/atlas.py [--pr <base>..<head>=<label> ...]
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
import graphs  # noqa: E402
import lens  # noqa: E402
from diagrams import ENGINE_ROOT, MAX_DEPTH, MAX_NODES, Diagrams, short  # noqa: E402

ROOT = config.root()
TEMPLATE = Path(__file__).with_name("atlas.template.html")
OUT = config.out() / "atlas.html"


def step_code(d, step):
    """Breadth-first call graph from the step's handlers, as nodes + edges with depth."""
    roots = [d.handler[e] for e in step["endpoints"] if e in d.handler]
    depth, order, queue = {r: 0 for r in roots}, [], list(roots)
    while queue and len(order) < MAX_NODES:
        cur = queue.pop(0)
        order.append(cur)
        if depth[cur] >= MAX_DEPTH:
            continue
        for n in sorted(d.g.edges.get(cur, ())):
            if n not in depth and n not in d.noise:
                depth[n] = depth[cur] + 1
                queue.append(n)
    kept = set(order)
    # plumbing it calls directly: hidden from the drawing, still named so nothing vanishes silently
    also = sorted({short(n)[1] for a in order for n in d.g.edges.get(a, ()) if n in d.noise and n not in d.g.bases})
    nodes = [{"id": n, "file": short(n)[0], "sym": short(n)[1], "depth": depth[n], "root": n in roots}
             for n in order]
    edges = [[a, b] for a in order for b in sorted(d.g.edges.get(a, ())) if b in kept and b != a]
    return {"nodes": nodes, "edges": edges, "hidden": len(depth) - len(order), "also": also}


def functions(d, ids):
    """What each drawn function is: signature, first docstring paragraph, lines, and a link to
    those lines at this commit when the repo is on GitHub."""
    try:
        remote = lens.git("remote", "get-url", "origin").strip()
    except Exception:
        remote = ""
    m = re.match(r"(?:git@github\.com:|https://github\.com/)(.+?)(?:\.git)?$", remote)
    blob = f"https://github.com/{m[1]}/blob/{lens.git('rev-parse', 'HEAD').strip()}/" if m else None
    out = {}
    # ponytail: parses the file once per function; cache parsed trees if big repos get slow
    for n in sorted(ids):
        rel, sym = n.rsplit(":", 1)
        builder, path = graphs.builder_for(rel), ROOT / rel
        text = path.read_text(errors="replace") if path.is_file() else None  # the tree the graph was built from
        start, end = d.g.defs.get(n, (None, None))
        info = {"sig": builder.signature(text, sym) if builder and sym != "__main__" else None,
                "doc": builder.doc(text, sym) if hasattr(builder, "doc") else None,
                "lines": [start, end] if start else None}
        if blob and start:
            info["url"] = f"{blob}{rel}#L{start}-L{end}"
        out[n] = {k: v for k, v in info.items() if v}
    return out


def step_keys(the_map):
    """Unique, stable key per step: flow/id, with a suffix when a flow repeats an id."""
    keys, seen = {}, set()
    for f in the_map["flows"]:
        for i, s in enumerate(f["steps"]):
            key, n = f"{f['id']}/{s['id']}", 2
            while key in seen:
                key, n = f"{f['id']}/{s['id']}-{n}", n + 1
            seen.add(key)
            keys[(f["id"], i)] = key
    return keys


def merges(d, keys, limit=24):
    """Where flows meet: code that steps of two or more flows run, one interchange per file.
    Only the first meeting counts: a function whose caller is reached by exactly the same steps
    sits below the merge, not at it (reach is transitive, so a caller's steps are a subset of its
    callee's; equal means they met already). Code reached from over half the entry points is
    plumbing (config, auth) and meets everything, so it is left out."""
    hits = {}
    for r in d.reach.values():
        for n in r:
            hits[n] = hits.get(n, 0) + 1
    skip = {n for n, c in hits.items() if c > len(d.reach) / 2} | set(d.g.bases)
    by_node = {}
    for f in d.map["flows"]:
        for i, s in enumerate(f["steps"]):
            hs = [d.handler[e] for e in s["endpoints"] if e in d.handler]
            for n in set().union(*(d.reach[h] for h in hs)) - skip if hs else ():
                if d.component(n) not in d.plumbing:
                    by_node.setdefault(n, set()).add(keys[(f["id"], i)])
    callers = {}
    for a, bs in d.g.edges.items():
        for b in bs:
            if b != a:
                callers.setdefault(b, set()).add(a)
    by_file = {}
    for n, ss in by_node.items():
        if len({k.split("/")[0] for k in ss}) < 2 or any(by_node.get(p) == ss for p in callers.get(n, ())):
            continue
        m = by_file.setdefault(short(n)[0], {"file": short(n)[0], "at": [], "ids": [], "steps": set()})
        m["at"].append(short(n)[1])
        m["ids"].append(n)
        m["steps"] |= ss
    out = sorted(by_file.values(), key=lambda m: (-len({k.split("/")[0] for k in m["steps"]}), -len(m["steps"]), m["file"]))
    # ponytail: widest `limit` only; a big repo may want a "show all" toggle
    for i, m in enumerate(out[:limit]):
        m.update(id=f"m{i}", at=sorted(m["at"]), steps=sorted(m["steps"]),
                 flows=len({k.split("/")[0] for k in m["steps"]}))
    return out[:limit]


def split_votes():
    path = config.out() / "QUESTIONS.md"
    if not path.exists():
        return {}
    text = path.read_text()
    section = text.split("## Split votes", 1)[-1].split("\n## ", 1)[0]
    return {m[1]: m[2] for m in re.finditer(r"- `([^`]+)`: (.+?) → placed", section)}


def overlay(d, spec, ms):
    rng, _, title = spec.partition("=")
    base, head = rng.split("..")
    changes = lens.changed_lines(base, head)
    changed, new = set(), set()
    for rel, (old, cur) in changes.items():
        if not lens.CODE.match(rel) or lens.TEST.search(rel):
            continue
        base_text = lens.show(base, rel)
        before = {s for *_, s in lens.defs(rel, base_text)}
        for s in lens.symbols_at(rel, lens.show(head, rel), cur) | lens.symbols_at(rel, base_text, old):
            if s == "<module>":
                continue
            (new if s not in before else changed).add(f"{rel}:{s}")
    g = lens.graph_at(head)
    added_eps = set(lens.endpoint_set(head)) - set(lens.endpoint_set(base))
    handlers = {}
    for e, h in lens.endpoint_set(head).items():
        handlers.setdefault(h, []).append(e)
    reach_eps = {}
    for c in changed:
        if c in g.defs:
            for n in g.callers(c) | {c}:
                for e in handlers.get(n, []):
                    reach_eps.setdefault(e, set()).add(short(c)[1])
    steps, keys = {}, step_keys(d.map)
    for f in d.map["flows"]:
        for i, s in enumerate(f["steps"]):
            key = keys[(f["id"], i)]
            direct = (set(s["code_path"]) | {d.handler.get(e) for e in s["endpoints"]}) & (changed | new)
            if any(e in added_eps for e in s["endpoints"]):
                steps[key] = {"kind": "new", "via": sorted(short(x)[1] for x in direct)[:4]}
            elif direct:
                steps[key] = {"kind": "direct", "via": sorted(short(x)[1] for x in direct)[:4]}
            else:
                via = set().union(*(reach_eps.get(e, set()) for e in s["endpoints"]))
                if via:
                    steps[key] = {"kind": "reach", "via": sorted(via)[:4]}
    widest = sorted(((len({e for n in g.callers(c) | {c} for e in handlers.get(n, [])}), short(c)[1])
                     for c in changed if c in g.defs), reverse=True)[:6]
    hit = [m["id"] for m in ms if changed & set().union(*(d._forward(n) for n in m["ids"]))]
    return {"id": re.sub(r"\W", "", title) or "pr", "title": title or rng, "range": rng,
            "steps": steps, "merges": hit, "changed": len(changed), "new": len(new),
            "widest": [{"sym": s, "endpoints": n} for n, s in widest if n]}


def build(prs):
    d = Diagrams()
    d.system()  # fills d.matrix
    flows, comps, _ = d.matrix
    splits, keys = split_votes(), step_keys(d.map)
    ms = merges(d, keys)
    data = {"flows": [], "merges": ms, "overlays": [overlay(d, p, ms) for p in prs],
            "plumbing": sorted(d.plumbing), "runs": d.map["runs"]}
    for f in flows:
        steps = []
        for i, s in enumerate(f["steps"]):
            hs = [d.handler[e] for e in s["endpoints"] if e in d.handler]
            reached = set().union(*(d.reach[h] for h in hs)) - d.noise if hs else set()
            touched = set()
            if ENGINE_ROOT in reached:
                touched.add("workflow engine")
                reached &= set().union(*(d._forward_avoiding(h, ENGINE_ROOT) for h in hs))
            touched |= {c for c in map(d.component, reached) if c}
            steps.append({
                "key": keys[(f["id"], i)], "name": s["name"], "actor": s["actor"],
                "evidence": s["evidence"], "busy": s["busyness"], "endpoints": s["endpoints"],
                "writes": s["writes"], "ui": s["ui"], "runs": s["runs"],
                "split": {e: splits[e] for e in s["endpoints"] if e in splits},
                "components": sorted((touched - d.plumbing) & set(comps)),
                "code": step_code(d, s) if hs else None,
            })
        data["flows"].append({"id": f["id"], "summary": f["summary"], "steps": steps})
    data["functions"] = functions(d, {n["id"] for f in data["flows"] for s in f["steps"] if s["code"] for n in s["code"]["nodes"]})
    commit = lens.git("rev-parse", "--short", "HEAD").strip()
    data["commit"] = commit
    name = config.load().get("name") or ROOT.name.replace("-", " ").replace("_", " ").title()
    html = (TEMPLATE.read_text().replace("__ATLAS_NAME__", name.replace("<", "&lt;"))
            .replace("/*__ATLAS_DATA__*/null", json.dumps(data, separators=(",", ":"))))
    OUT.write_text(html)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html) // 1024} KB, {len(ms)} merges, {len(data['overlays'])} overlays)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", action="append", default=[], help="<base>..<head>=<label>")
    build(ap.parse_args().pr)
