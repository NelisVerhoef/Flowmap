"""A change, told as how the system moves: chapters anchored to the flow map, each saying where
it sits, what it changes in the system, why that matters, and what to ask. Code comes last.

The facts are deterministic (diff, call graph at base and head, map.json). The prose is optional
and comes from a story file the /pr-lens skill writes; without one, chapters are grouped by the
flow steps that run the changed code and say only what the graph can.

    python tools/flowmap/change.py <base> [<head>] [--name pr-12] [--story path.json] [--facts] [--link]

Writes <out>/changes/<name>.html. --facts prints the facts as JSON instead (input for a story).
--link also prints a link to the hosted viewer (`viewer` in flowmap.toml, or FLOWMAP_VIEWER) that
carries the whole page in its fragment, so it renders in any browser without publishing the data.
Story format: see STORY in the /pr-lens skill.
"""

import argparse
import base64
import json
import math
import os
import re
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
import graphs  # noqa: E402
import lens  # noqa: E402
from atlas import step_keys  # noqa: E402

ROOT = config.root()
TEMPLATE = Path(__file__).with_name("change.template.html")
DOC = re.compile(r"\.(md|rst|txt)$|^docs/|(^|/)LICENSE")


def file_kind(rel):
    if lens.CODE.match(rel):
        return "test" if lens.TEST.search(rel) else "code"
    if rel.startswith(config.load().get("out", "docs/flowmap").rstrip("/") + "/"):
        return "generated"
    return "doc" if DOC.search(rel) else "outside"


def hunks(base, head):
    """[{file, old, new, lines}] with 2 lines of context."""
    out, rel = [], None
    for line in lens.git("diff", "-U2", "--no-renames", base, head).splitlines():
        if line.startswith("+++ "):
            rel = line[6:] if line != "+++ /dev/null" else rel
        elif line.startswith("--- "):
            rel = line[6:] if line != "--- /dev/null" else None
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", line)
            out.append({"file": rel, "old": int(m[1]), "new": int(m[3]), "ctx": m[5].strip(), "lines": []})
        elif out and line[:1] in (" ", "+", "-"):
            out[-1]["lines"].append(line)
    return out


def signature(rel, text, sym):
    """A def's parameter list, for spotting contract changes (None where no builder parses rel)."""
    builder = graphs.builder_for(rel)
    return builder.signature(text, sym) if builder else None


def facts(base, head):
    the_map = json.loads(lens.MAP.read_text())
    keys = step_keys(the_map)
    changes = lens.changed_lines(base, head)
    files = []
    for rel, (old, new) in sorted(changes.items()):
        files.append({"path": rel, "kind": file_kind(rel), "added": len(new), "removed": len(old)})

    g_base, g_head = lens.graph_at(base), lens.graph_at(head)
    eps_base, eps_head = lens.endpoint_set(base), lens.endpoint_set(head)

    # changed symbols, with status
    symbols = {}
    for f in files:
        if f["kind"] != "code":
            continue
        rel = f["path"]
        old, new = changes[rel]
        base_text, head_text = lens.show(base, rel), lens.show(head, rel)
        base_syms = {s for *_, s in lens.defs(rel, base_text)}
        head_syms = {s for *_, s in lens.defs(rel, head_text)}
        for s in lens.symbols_at(rel, head_text, new) | lens.symbols_at(rel, base_text, old):
            if s == "<module>":
                continue
            status = "new" if s not in base_syms else "deleted" if s not in head_syms else "modified"
            sig_b, sig_h = signature(rel, base_text, s), signature(rel, head_text, s)
            symbols[f"{rel}:{s}"] = {"id": f"{rel}:{s}", "file": rel, "sym": s, "status": status,
                                     "contract": status == "modified" and sig_b != sig_h,
                                     "signature": [sig_b, sig_h] if sig_b != sig_h else None}

    # a class reported alongside its own methods is just the lines between them
    for sid in [k for k in symbols if any(o.startswith(k + ".") for o in symbols)]:
        del symbols[sid]

    # where each step's code lives: what its handlers can reach at head
    step_info, handler_eps = [], defaultdict(list)
    for e, h in eps_head.items():
        handler_eps[h].append(e)
    for f in the_map["flows"]:
        for i, s in enumerate(f["steps"]):
            hs = [eps_head.get(e) or eps_base.get(e) for e in s["endpoints"]]
            hs = [h for h in hs if h]
            reach = set(hs)
            for h in hs:
                reach |= g_head.callees(h)
            anchors = set(s["ui"]) | set(s["code_path"]) | set(hs)
            step_info.append({"key": keys[(f["id"], i)], "flow": f["id"], "name": s["name"],
                              "handlers": hs, "reach": reach, "anchors": anchors})

    def node_for(sid):
        """The call-graph node that stands for a symbol: constructors are called via the class."""
        if sid.endswith(".__init__"):
            return sid[: -len(".__init__")]
        return sid

    for sid, s in symbols.items():
        node = node_for(sid)
        s["steps"], s["witness"] = [], {}
        for st in step_info:
            if node in st["reach"] or sid in st["anchors"]:
                s["steps"].append(st["key"])
                for h in st["handlers"]:
                    path = g_head.reaches(h, node)
                    if path:
                        s["witness"][st["key"]] = path
                        break
        graph = g_base if s["status"] == "deleted" else g_head
        s["callers"] = [{"id": c, "edited": c in symbols} for c in sorted(graph.reverse.get(node, ()))
                        if c != node and not c.startswith(node + ".")]

    added_edges, removed_edges, moved = lens.reach_diff(g_base, g_head, eps_base, eps_head)

    def module(nid):
        return nid.rsplit(":", 1)[0]
    mod_base = {(module(a), module(b)) for a, b in g_base.edge_set() if module(a) != module(b)}
    mod_head = {(module(a), module(b)) for a, b in g_head.edge_set() if module(a) != module(b)}

    # how a change spreads over flows: Hassan's change entropy, over flows instead of files
    share = Counter()
    for s in symbols.values():
        for k in {k.split("/")[0] for k in s["steps"]} or {"(off-map)"}:
            share[k] += 1
    total = sum(share.values())
    entropy = max(0.0, -sum(n / total * math.log2(n / total) for n in share.values())) if total else 0.0

    hs = hunks(base, head)
    for h in hs:
        rel = h["file"]
        if not lens.CODE.match(rel or ""):
            h["symbols"] = []
            continue
        new_lines = {h["new"] + i for i, ln in enumerate(x for x in h["lines"] if x[0] != "-")}
        old_lines = {h["old"] + i for i, ln in enumerate(x for x in h["lines"] if x[0] != "+")}
        syms = lens.symbols_at(rel, lens.show(head, rel), new_lines) | lens.symbols_at(rel, lens.show(base, rel), old_lines)
        ids = {f"{rel}:{s}" for s in syms}
        # lines between a class's methods belong to the changed methods around them
        h["symbols"] = sorted({i for i in ids if i in symbols} |
                              {k for i in ids if i not in symbols for k in symbols if k.startswith(i + ".")})

    tests_cfg = config.load().get("code", {}).get("tests", [])
    return {
        "base": base, "head": head,
        "base_sha": lens.git("rev-parse", "--short", base).strip(),
        "head_sha": lens.git("rev-parse", "--short", head).strip(),
        "name": config.load().get("name") or ROOT.name,
        "map": [{"id": f["id"], "steps": [{"key": keys[(f["id"], i)], "name": s["name"],
                                            "endpoints": s["endpoints"], "evidence": s["evidence"]}
                                           for i, s in enumerate(f["steps"])]} for f in the_map["flows"]],
        "files": files,
        "symbols": list(symbols.values()),
        "endpoints": {"added": sorted(set(eps_head) - set(eps_base)), "removed": sorted(set(eps_base) - set(eps_head))},
        "reach": {"gained": {k: sorted(v[0]) for k, v in moved.items() if v[0]},
                  "lost": {k: sorted(v[1]) for k, v in moved.items() if v[1]}},
        "edges": {"added": sorted(map(list, added_edges)), "removed": sorted(map(list, removed_edges))},
        "modules": {"added": sorted(map(list, mod_head - mod_base)), "removed": sorted(map(list, mod_base - mod_head))},
        "flow_share": dict(share), "flow_entropy": round(entropy, 2),
        "tests": {"configured": bool(tests_cfg),
                  "changed": [f["path"] for f in files if f["kind"] == "test"]},
        "hunks": hs,
    }


def auto_chapters(fx):
    """No story: one chapter per set of steps that run the changed code; the rest outside the map."""
    groups = defaultdict(list)
    for s in fx["symbols"]:
        groups[tuple(sorted(s["steps"]))].append(s["id"])
    names = {st["key"]: st["name"] for f in fx["map"] for st in f["steps"]}
    chapters = []
    for steps, syms in sorted(groups.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        title = ("Changes run by " + "; ".join(names[k] for k in steps[:2]) + (" …" if len(steps) > 2 else "")
                 if steps else "New or changed code no flow runs")
        chapters.append({"title": title, "kind": "behaviour" if steps else "off-map", "symbols": syms})
    other = [f["path"] for f in fx["files"] if f["kind"] in ("outside", "doc")]
    if other:
        chapters.append({"title": "Changed outside the map", "kind": "outside", "files": other})
    return chapters


def merge(fx, story):
    """Attach facts to the story's chapters; anything the story leaves out gets its own chapter."""
    chapters = story.get("chapters") or auto_chapters(fx)
    claimed_syms = {s for c in chapters for s in c.get("symbols", [])}
    claimed_files = {f for c in chapters for f in c.get("files", [])}
    known = {s["id"] for s in fx["symbols"]}
    stray = [s for s in known if s not in claimed_syms]
    if stray and story.get("chapters"):
        chapters.append({"title": "Changes the story does not cover", "kind": "unassigned", "symbols": sorted(stray)})
    loose = [f["path"] for f in fx["files"] if f["kind"] in ("outside", "doc") and f["path"] not in claimed_files]
    if loose and story.get("chapters"):
        chapters.append({"title": "Changed outside the map", "kind": "outside", "files": loose})
    unknown = sorted(claimed_syms - known)
    if unknown:
        print("story names symbols this diff does not change: " + ", ".join(unknown), file=sys.stderr)
    folded = [f for f in fx["files"] if f["kind"] in ("generated", "test") or
              (f["kind"] in ("doc", "outside") and f["path"] not in claimed_files and not story.get("chapters"))]
    return {"facts": fx, "story": {k: v for k, v in story.items() if k != "chapters"},
            "chapters": chapters, "folded": [f["path"] for f in folded if f["path"] not in loose]}


def viewer_html():
    """The page with no data in it: it reads a link's fragment or a dropped file. No fonts or other
    requests, and a CSP that forbids any, so a reader can see their data stays in the tab."""
    csp = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
           "base-uri 'none'; form-action 'none'")
    return re.sub(r"<!--fonts-->.*?<!--/fonts-->", f'<meta http-equiv="Content-Security-Policy" content="{csp}">',
                  TEMPLATE.read_text(), count=1, flags=re.S).replace("__TITLE__", "flowmap change")


def link(data, viewer):
    """The viewer URL with the data in its fragment: #v1.<base64url of raw-deflated JSON>."""
    z = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = z.compress(json.dumps(data, separators=(",", ":")).encode()) + z.flush()
    return f"{viewer}#v1.{base64.urlsafe_b64encode(packed).rstrip(b'=').decode()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("head", nargs="?", default="HEAD")
    ap.add_argument("--name", help="output name (default: <head>)")
    ap.add_argument("--story", help="story JSON (default: <out>/changes/<name>.story.json if present)")
    ap.add_argument("--facts", action="store_true", help="print facts as JSON and exit")
    ap.add_argument("--link", action="store_true", help="also print a viewer link carrying the page")
    a = ap.parse_args()
    fx = facts(a.base, a.head)
    if a.facts:
        print(json.dumps({k: v for k, v in fx.items() if k != "hunks"}, indent=1))
        return
    name = a.name or re.sub(r"[^\w.-]", "-", a.head)
    out_dir = config.out() / "changes"
    out_dir.mkdir(parents=True, exist_ok=True)
    story_path = Path(a.story) if a.story else out_dir / f"{name}.story.json"
    story = json.loads(story_path.read_text()) if story_path.exists() else {}
    data = merge(fx, story)
    title = story.get("title") or f"{a.base}..{a.head}"
    html = (TEMPLATE.read_text().replace("__TITLE__", title.replace("&", "&amp;").replace("<", "&lt;"))
            .replace("/*__CHANGE_DATA__*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
    out = out_dir / f"{name}.html"
    out.write_text(html)
    print(f"wrote {out.relative_to(ROOT)} ({len(data['chapters'])} chapters"
          f"{', story ' + str(story_path.relative_to(ROOT) if story_path.is_relative_to(ROOT) else story_path) if story else ', no story'})",
          file=sys.stderr if a.link else sys.stdout)  # with --link, stdout is just the link
    if a.link:
        viewer = os.environ.get("FLOWMAP_VIEWER") or config.load().get("viewer")
        if not viewer:
            sys.exit("no viewer: set viewer = \"https://.../change.html\" in flowmap.toml or FLOWMAP_VIEWER "
                     "(build it with `flowmap viewer <dir>`)")
        url = link(data, viewer)
        if len(url) > 60000:  # a PR body holds 65536 characters
            print(f"warning: link is {len(url)} characters, too long for a PR body; "
                  f"open {out.relative_to(ROOT)} in the viewer instead", file=sys.stderr)
        print(url)


if __name__ == "__main__":
    main()
