"""The canvas: the map drawn as one left-to-right picture (docs/flowmap/canvas.html).

Screens on the left, then the flows and their steps, then the code they run (one card per file,
placed by call depth), then the data they write. A flow is a path on it; a change is paint on it.
The same picture serves the map, a flow and a change, so every PR is read on a map you know.

    flowmap canvas [--change <name>=<base>..<head> ...] [--from <atlas.html>] [--out <path>] [--link]

--change paints a change and, when docs/flowmap/changes/<name>.story.json exists, numbers its
chapters on the cards they touch. --from draws an existing atlas page's data instead of building
it (a map whose source isn't checked out here, like the bench's). --link also prints a link to the
hosted viewer that carries the map in its fragment, so it renders in any browser without publishing it.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
from viewer import BUDGET, link, locked, viewer_url  # noqa: E402

TEMPLATE = Path(__file__).with_name("canvas.template.html")
UI_EXT = (".tsx", ".jsx", ".vue", ".svelte", ".ts", ".js", ".html", ".erb", ".astro")


def flow_title(fid):
    return fid.removeprefix("new:").replace("-", " ").capitalize()


def screen_group(rel):
    """Screens by the folder that holds them (components/Admin/*.tsx is the Admin screen); a route
    or page file is a screen of its own."""
    parts = rel.split("/")
    stem = parts[-1].rsplit(".", 1)[0]
    if len(parts) == 1 or parts[-2] in ("routes", "pages", "app", "views", "screens") or rel.endswith(".html"):
        return "/".join(parts[:-1] + [stem]), stem.replace("_", "").replace("-", " ").strip() or stem
    return "/".join(parts[:-1]), parts[-2]


def data_label(w):
    """A write as the map records it: `User.email` is the User model, a path is that file."""
    if "/" in w or w.endswith((".json", ".md", ".html", ".toml")):
        return w, w.rsplit("/", 1)[-1], w.rsplit("/", 1)[0] if "/" in w else ""
    model, _, field = w.partition(".")
    return model, model, field


def graph(atlas):
    """Nodes and edges of the canvas. Every edge carries the steps that run along it, so a step,
    a flow or a change lights its own path."""
    flows, steps, files, fns, screens, datas, edges = [], {}, {}, {}, {}, {}, {}

    def edge(a, b, kind, sid, label=None):
        e = edges.setdefault((a, b, kind), {"a": a, "b": b, "kind": kind, "steps": set(), "w": 0})
        e["steps"].add(sid)
        e["w"] += 1
        if label:
            e.setdefault("labels", set()).add(label)

    for f in atlas["flows"]:
        flow = {"id": "flow:" + f["id"], "key": f["id"], "title": flow_title(f["id"]),
                "summary": f.get("summary", ""), "steps": [], "draft": f["id"].startswith("new:")}
        for s in f["steps"]:
            sid = "s:" + s["key"]
            code = s.get("code") or {"nodes": [], "edges": []}
            for n in code["nodes"]:
                fid = "f:" + n["file"]
                fns.setdefault(n["id"], {"id": n["id"], "sym": n["sym"], "file": fid})
                F = files.setdefault(fid, {"id": fid, "label": n["file"], "path": n["id"].rsplit(":", 1)[0],
                                           "fns": [], "steps": set()})
                if n["id"] not in F["fns"]:
                    F["fns"].append(n["id"])
                F["steps"].add(sid)
            roots = [n for n in code["nodes"] if n["root"]]
            for r in roots:
                edge(sid, "f:" + r["file"], "entry", sid, " · ".join(s["endpoints"]))
            calls = []
            for a, b in code["edges"]:
                calls.append([a, b])
                fa, fb = fns[a]["file"], fns[b]["file"]
                if fa != fb:
                    edge(fa, fb, "call", sid)
            for u in s.get("ui", []):
                rel, _, sym = u.rpartition(":")
                if rel.endswith(UI_EXT):
                    key, label = screen_group(rel)
                    uid = "u:" + key
                    U = screens.setdefault(uid, {"id": uid, "label": label, "path": key, "parts": []})
                    if (sym or rel) not in U["parts"]:
                        U["parts"].append(sym or rel.rsplit("/", 1)[-1])
                    edge(uid, sid, "ui", sid)
            for w in s.get("writes", []):
                key, label, part = data_label(w)
                did = "d:" + key
                D = datas.setdefault(did, {"id": did, "label": label, "parts": set(), "path": key})
                if part:
                    D["parts"].add(part)
                # the write is drawn from the step's handler file: the map records what a step
                # writes, not which function does it
                edge("f:" + roots[0]["file"] if roots else sid, did, "writes", sid)
            steps[sid] = {"id": sid, "key": s["key"], "flow": flow["id"], "name": s["name"],
                          "actor": s.get("actor"), "evidence": s.get("evidence"),
                          "endpoints": s["endpoints"], "writes": s.get("writes", []),
                          "ui": s.get("ui", []), "handlers": sorted({"f:" + r["file"] for r in roots}),
                          "roots": [r["id"] for r in roots], "fns": [n["id"] for n in code["nodes"]],
                          "calls": calls, "hidden": code.get("hidden", 0), "also": code.get("also", [])}
            flow["steps"].append(sid)
        flows.append(flow)

    # call depth of each file: longest path from a handler file, back edges ignored
    out = {}
    for e in edges.values():
        if e["kind"] == "call":
            out.setdefault(e["a"], set()).add(e["b"])
    depth = {h: 0 for s in steps.values() for h in s["handlers"]}

    def walk(n, d, stack):
        if d < depth.get(n, -1):
            return
        depth[n] = d
        for m in sorted(out.get(n, ())):
            if m not in stack:
                walk(m, d + 1, stack | {m})

    for h in sorted({h for s in steps.values() for h in s["handlers"]}):
        walk(h, 0, {h})
    for fid, F in files.items():
        F["depth"] = depth.get(fid, 0)
        F["steps"] = sorted(F["steps"])

    funcs = atlas.get("functions", {})
    for n, info in funcs.items():
        if n in fns:
            fns[n].update({k: v for k, v in info.items() if k in ("sig", "doc", "lines", "url")})
    return {
        "flows": flows, "steps": steps, "files": files, "fns": fns, "screens": screens,
        "data": {k: {**v, "parts": sorted(v["parts"])} for k, v in datas.items()},
        "edges": [{**e, "steps": sorted(e["steps"]), **({"labels": sorted(e["labels"])} if "labels" in e else {})}
                  for e in edges.values()],
        "plumbing": atlas.get("plumbing", []), "commit": atlas.get("commit"),
    }


def paint(g, overlay, story=None, verdict=None):
    """A change as paint: files holding changed or new code, steps it touches, and the story's
    chapters numbered on the cards they are about."""
    by_path = {}
    for F in g["files"].values():
        by_path.setdefault(F["path"], F["id"])

    def file_of(sym):
        rel = sym.rsplit(":", 1)[0]
        return by_path.get(rel) or next((fid for p, fid in by_path.items() if rel.endswith(p) or p.endswith(rel)), None)

    files, off = {}, []
    for kind, ids in (("changed", overlay.get("changed_ids", [])), ("new", overlay.get("new_ids", []))):
        for sym in ids:
            fid = file_of(sym)
            if fid:
                files.setdefault(fid, {"kind": kind, "syms": []})["syms"].append(sym.rsplit(":", 1)[1])
            else:
                off.append(sym)
    steps = {"s:" + k: v for k, v in overlay.get("steps", {}).items()}
    # changed code no step runs: the map doesn't know it yet, which is itself news for a reviewer
    off_files = {}
    for sym in off:
        rel, _, name = sym.rpartition(":")
        off_files.setdefault(rel, []).append(name)
    out = {"id": overlay["id"], "title": overlay["title"], "range": overlay["range"], "files": files,
           "steps": steps, "off": off,
           "off_files": [{"id": "o:" + rel, "path": rel, "label": rel.rsplit("/", 1)[-1], "syms": syms,
                          "new": all(f"{rel}:{s}" in overlay.get("new_ids", []) for s in syms)}
                         for rel, syms in sorted(off_files.items())], "changed": overlay.get("changed", 0), "new": overlay.get("new", 0),
           "added_endpoints": overlay.get("added_endpoints", [])}
    if verdict:
        out["verdict"] = verdict
    if story:
        chapters = []
        for i, c in enumerate(story.get("chapters", []), 1):
            cf = sorted({fid for s in c.get("symbols", []) if (fid := file_of(s))}
                        | {"o:" + s.rsplit(":", 1)[0] for s in c.get("symbols", []) if not file_of(s) and ":" in s})
            cs = sorted({sid for sid, s in g["steps"].items() if set(s["fns"]) & set(c.get("symbols", []))})
            chapters.append({"n": i, "title": c.get("title", ""), "role": c.get("role", ""),
                             "before": c.get("before", ""), "after": c.get("after", ""),
                             "claim": c.get("claim", ""), "why": c.get("why", ""),
                             "questions": [q.get("q", "") for q in c.get("questions", [])],
                             "verified": [v.get("how", "") for v in c.get("verified", [])],
                             "files": cf, "steps": cs, "outside": c.get("files", [])})
        out["story"] = {"title": story.get("title", ""), "intent": story.get("intent", ""),
                        "delta": story.get("delta", ""), "url": story.get("url", ""), "pr": story.get("pr", ""),
                        "no_longer": [n.get("was", "") for n in story.get("no_longer", [])],
                        "chapters": chapters}
    return out


def from_page(path):
    m = re.search(r"const DATA = (\{.*?\});\n", Path(path).read_text())
    if not m:
        sys.exit(f"{path}: no atlas data found")
    return json.loads(m.group(1))


def viewer_html():
    """The page with no data in it: it reads a link's fragment."""
    return locked(TEMPLATE.read_text()).replace("__CANVAS_NAME__", "flowmap")


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--change", action="append", default=[], help="<name>=<base>..<head>")
    ap.add_argument("--from", dest="src", help="draw this atlas page's data instead of building it")
    ap.add_argument("--name", help="map name (default: flowmap.toml's name, or the repo's)")
    ap.add_argument("--out", help="default: <out>/canvas.html")
    ap.add_argument("--link", action="store_true", help="also print a viewer link carrying the map")
    args = ap.parse_args()
    changes = []
    for spec in args.change:
        name, _, rng = spec.partition("=")
        if ".." not in rng:
            sys.exit(f"--change {spec}: expected <name>=<base>..<head>")
        changes.append((name, rng))
    if args.src:
        if changes:
            sys.exit("--change needs the repo's own map; it can't paint onto --from data")
        atlas = from_page(args.src)
        name = args.name or re.search(r"<title>(.*?) System Atlas</title>", Path(args.src).read_text())[1]
    else:
        import atlas as atlas_mod  # needs the map and the code: only import when building
        import lens
        atlas = atlas_mod.data([f"{rng}={name}" for name, rng in changes])
        name = args.name or config.load().get("name") or config.root().name.replace("-", " ").replace("_", " ").title()
    g = graph(atlas)
    g["name"] = name
    g["changes"] = []
    for (cname, rng), ov in zip(changes, atlas.get("overlays", [])):
        story_path = config.out() / "changes" / f"{cname}.story.json"
        story = json.loads(story_path.read_text()) if story_path.exists() else None
        base, head = rng.split("..")
        facts, _ = lens.analyse(base, head)
        verdict = {"verdict": facts.get("verdict"), "spreads_to": facts.get("spreads_to", []),
                   "blind": [b if isinstance(b, str) else b.get("what", str(b)) for b in facts.get("blind", [])][:6]}
        g["changes"].append(paint(g, {**ov, "id": cname, "title": story.get("pr") if story and story.get("pr") else cname}, story, verdict))
    out = Path(args.out) if args.out else config.out() / "canvas.html"
    html = (TEMPLATE.read_text().replace("__CANVAS_NAME__", name.replace("<", "&lt;"))
            .replace("/*__CANVAS_DATA__*/null", json.dumps(g, separators=(",", ":"))))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out} ({len(html) // 1024} KB: {len(g['flows'])} flows, {len(g['steps'])} steps, "
          f"{len(g['files'])} files, {len(g['data'])} data, {len(g['screens'])} screens, {len(g['changes'])} changes)",
          file=sys.stderr if args.link else sys.stdout)  # with --link, stdout is just the link
    if args.link:
        url = link(g, viewer_url().rsplit("/", 1)[0] + "/canvas.html")
        if len(url) > BUDGET:
            print(f"warning: the link is {len(url) // 1000}K characters, too long for a PR body; "
                  f"it still opens in a browser", file=sys.stderr)
        print(url)


if __name__ == "__main__":
    main()
