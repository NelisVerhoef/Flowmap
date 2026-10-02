"""Mermaid diagrams for the flow map, at three zoom levels. Generated — never hand-drawn,
so they cannot drift from map.json and the call graph.

  docs/flowmap/diagrams/README.md   system: flows, and how much backend code they share
  docs/flowmap/diagrams/<flow>.md   one flow: its steps in user order, coloured by evidence,
                                    each with its code path (call graph, grouped by file)

    python tools/flowmap/diagrams.py
"""

import json
import re
import sys
from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
from callgraph import Graph  # noqa: E402

ROOT = config.root()
OUT = config.out() / "diagrams"
UBIQUITOUS = 0.25   # code reached from more than this share of endpoints is plumbing (auth, session…)
MAX_NODES, MAX_DEPTH = 22, 4
# Optional hub whose exclusive reach is folded into one "workflow engine" node (flowmap.toml).
ENGINE_ROOT = config.load()["flows"]["engine"]
# Real dependencies that say nothing about flows (flowmap.toml [flows].plumbing).
PLUMBING = config.load()["flows"]["plumbing"]
# Directories whose files are each their own component rather than one package component.
ENTRY_LAYER = {"routers", "routes", "controllers", "api", "migrations", "pages"}
SPLIT_DIRS = set(config.load()["flows"].get("split", ["services"]))
APP_DIRS = sorted((d.rstrip("/") + "/" for d in config.app_dirs() if d not in (".", "")), key=len, reverse=True)

EVIDENCE_STYLE = """    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff"""


def nid(text):
    return "n" + re.sub(r"\W", "_", text)


def label(text, limit=60):
    text = text if len(text) <= limit else text[: limit - 1] + "…"
    return text.replace('"', "'").replace("<", "‹").replace(">", "›")


def short(node):
    rel, sym = node.rsplit(":", 1)
    for d in APP_DIRS:
        if rel.startswith(d):
            return rel[len(d):], sym
    return rel, sym


class Diagrams:
    def __init__(self):
        self.map = json.loads((config.out() / "map.json").read_text())
        inv = json.loads((config.out() / "inventory.json").read_text())["endpoints"]
        self.handler = {e["endpoint"]: e["handler"] for e in inv}
        self.g = Graph()
        reach_count = Counter()
        self.reach = {}
        for h in set(self.handler.values()):
            self.reach[h] = self._forward(h)
            reach_count.update(self.reach[h])
        cutoff = UBIQUITOUS * len(self.reach)
        # plumbing: reached from most endpoints, or a class (models/DTOs are data, not flow)
        self.noise = {n for n, c in reach_count.items() if c > cutoff} | set(self.g.bases)
        self.engine = self._forward(ENGINE_ROOT) if ENGINE_ROOT else set()
        self.plumbing = set(PLUMBING)
        # the entry layer (routers/controllers/route files) is where flows start, not shared code
        self.entry_files = {short(h)[0] for h in self.handler.values()}

    def _forward(self, src):
        seen, queue = {src}, deque([src])
        while queue:
            for n in self.g.edges.get(queue.popleft(), ()):
                if n not in seen:
                    seen.add(n)
                    queue.append(n)
        return seen

    def _forward_avoiding(self, src, block):
        """Forward reach that never passes through `block`."""
        seen, queue = {src}, deque([src])
        while queue:
            for n in self.g.edges.get(queue.popleft(), ()):
                if n not in seen and n != block:
                    seen.add(n)
                    queue.append(n)
        return seen

    # --- level 1: system
    def component(self, node):
        """Group code into components: a subpackage (scorers/, blocks/…) or a module file."""
        rel = short(node)[0]
        parts = rel.split("/")
        if rel in self.entry_files or parts[0] in ENTRY_LAYER:
            return None  # the entry layer is where flows start, not a shared component
        if parts[0] in SPLIT_DIRS or len(parts) == 1:
            return re.sub(r"\.(py|rb|tsx?|jsx?|mjs)$", "", rel).removesuffix("/__init__")
        return parts[0] + "/"

    def system(self):
        flows = self.map["flows"]
        # per flow: component -> how many of its steps run through it
        uses = {}
        for f in flows:
            counter = Counter()
            for st in f["steps"]:
                hs = [self.handler[e] for e in st["endpoints"] if e in self.handler]
                reached = set().union(*(self.reach[h] for h in hs)) - self.noise if hs else set()
                comps = set()
                if ENGINE_ROOT in reached:
                    comps.add("workflow engine")
                    # code reached only through the engine is part of "runs a workflow"
                    direct = set().union(*(self._forward_avoiding(h, ENGINE_ROOT) for h in hs))
                    reached = reached & direct
                comps |= {c for c in map(self.component, reached) if c}
                counter.update(comps - self.plumbing)
            uses[f["id"]] = counter
        flows_per_comp = Counter(c for u in uses.values() for c in u)
        shared_all = sorted(c for c, n in flows_per_comp.items() if n >= 2)
        # drawn: the 6 widest components, strong ties only; the matrix below carries the rest
        shared = sorted(shared_all, key=lambda c: (c != "workflow engine", -flows_per_comp[c], c))[:6]
        engine_parts = sorted({c for c in map(self.component, self.engine - self.noise) if c} - self.plumbing)
        lines = ["flowchart TB", '    subgraph flows["User flows"]', "    direction LR"]
        for f in flows:
            ev = Counter(st["evidence"] for st in f["steps"])
            solid = ev["tested"] + ev["agreed"] + ev["confirmed"]
            lines.append(f'        {nid(f["id"])}["<b>{label(f["id"])}</b><br/>{len(f["steps"])} steps · '
                         f'{solid} solid"]')
        lines += ["    end", '    subgraph core["Core: the components most flows run through"]', "    direction LR"]
        for c in sorted(shared, key=lambda c: -flows_per_comp[c]):
            lines.append(f'        {nid("c_" + c)}("{label(c)}<br/><i>{flows_per_comp[c]} flows</i>")')
        lines.append("    end")
        for f in flows:
            for c in shared:
                n = uses[f["id"]][c]
                if n >= 3:
                    lines.append(f"    {nid(f['id'])} -->|{n}| {nid('c_' + c)}")
        for f in flows:
            ev = Counter(st["evidence"] for st in f["steps"])
            solid = (ev["tested"] + ev["agreed"] + ev["confirmed"]) / max(1, len(f["steps"]))
            cls = "tested" if solid >= 0.75 else "agreed" if solid >= 0.5 else "contested"
            lines.append(f"    class {nid(f['id'])} {cls}")
            lines.append(f'    click {nid(f["id"])} "./{f["id"].replace(":", "-")}.md"')
        lines.append(EVIDENCE_STYLE)
        hubs = sorted(((flows_per_comp[c], c, sorted(fid for fid in uses if uses[fid][c])) for c in shared_all),
                      reverse=True)
        self.matrix = (flows, shared_all, uses)
        return "\n".join(lines), (hubs, engine_parts)

    # --- level 2: one flow
    def flow(self, f):
        lines = ["flowchart TD"]
        prev = None
        for i, s in enumerate(f["steps"], 1):
            sid = nid(f"{f['id']}_{s['id']}_{i}")
            busy = s["busyness"]["hops"]
            eps = "<br/>".join(f"<code>{label(e, 58)}</code>" for e in s["endpoints"][:3])
            if len(s["endpoints"]) > 3:
                eps += f"<br/>+{len(s['endpoints']) - 3} more"
            lines.append(f'    {sid}["<b>{i}. {label(s["name"], 70)}</b><br/><i>{s["actor"]} · {s["evidence"]} · '
                         f'busy {busy}</i>' + (f"<br/>{eps}" if eps else "") + '"]')
            lines.append(f"    class {sid} {s['evidence']}")
            if prev:
                lines.append(f"    {prev} --> {sid}")
            prev = sid
        lines.append(EVIDENCE_STYLE)
        return "\n".join(lines)

    # --- level 3: one step's code path
    def step(self, s):
        roots = [self.handler[e] for e in s["endpoints"] if e in self.handler]
        if not roots:
            return None, 0
        keep, depth, queue = [], {}, deque()
        for r in roots:
            depth[r] = 0
            queue.append(r)
        while queue and len(keep) < MAX_NODES:
            cur = queue.popleft()
            keep.append(cur)
            if depth[cur] >= MAX_DEPTH:
                continue
            for n in sorted(self.g.edges.get(cur, ())):
                if n not in depth and n not in self.noise:
                    depth[n] = depth[cur] + 1
                    queue.append(n)
        truncated = len(depth) - len(keep)
        kept = set(keep)
        by_file = defaultdict(list)
        for n in keep:
            by_file[short(n)[0]].append(n)
        lines = ["flowchart LR"]
        for i, (rel, nodes) in enumerate(by_file.items()):
            lines.append(f'    subgraph f{i}["{label(rel, 50)}"]')
            for n in nodes:
                lines.append(f'        {nid(n)}["{label(short(n)[1], 40)}"]')
            lines.append("    end")
        for n in keep:
            for m in sorted(self.g.edges.get(n, ())):
                if m in kept and m != n:
                    lines.append(f"    {nid(n)} --> {nid(m)}")
        for r in roots:
            lines.append(f"    class {nid(r)} handler")
        lines.append(EVIDENCE_STYLE)
        return "\n".join(lines), truncated

    def write(self):
        OUT.mkdir(parents=True, exist_ok=True)
        system, top = self.system()
        md = ["# System map", "",
              "_Generated by `tools/flowmap/diagrams.py` from `map.json` + the call graph. Do not hand-edit._", "",
              "Left: user flows (click to drill in), coloured by how much of the flow the map is sure of "
              "(green ≥75% of steps tested/agreed · light green ≥50% · amber below). Right: backend "
              "components that two or more flows run through. A line means 3+ of that "
              "flow's steps reach the component (call graph); its number is how many. Weaker ties are in the matrix. Plumbing reached from most endpoints "
              "(auth, sessions) and data classes are hidden so the lines mean something.", "",
              "```mermaid", system, "```", "", "## Shared components, widest first", "",
              "A component many flows run through is where a change has the widest blast radius — "
              "and where the system's real core is.", ""]
        hubs, engine_parts = top
        flows, comps, uses = self.matrix
        comps = sorted(comps, key=lambda c: (-sum(1 for f in flows if uses[f["id"]][c]), c))
        md += ["Every component two or more flows share. Cell = how many of the flow's steps reach it.", "",
               "| component | " + " | ".join(f["id"].removeprefix("new:") for f in flows) + " |",
               "|---|" + "---|" * len(flows)]
        for c in comps:
            md.append(f"| **{c}** | " + " | ".join(str(uses[f["id"]][c] or "") for f in flows) + " |")
        md += ["", f"**workflow engine** = `executor.run_workflow` and everything only it reaches: "
               + ", ".join(f"`{c}`" for c in engine_parts) + ".",
               "", f"**Hidden as plumbing:** {', '.join(f'`{c}`' for c in sorted(self.plumbing))} "
               "(override with `plumbing` in `decisions.json`)."]
        md += ["", "## Flows", ""]
        for f in self.map["flows"]:
            md.append(f"- [{f['id']}](./{f['id'].replace(':', '-')}.md) — {f['summary']}")
        (OUT / "README.md").write_text("\n".join(md) + "\n")

        for f in self.map["flows"]:
            md = [f"# {f['id']}", "", f"_{f['summary']}_", "",
                  "[← system map](./README.md) · generated, do not hand-edit", "",
                  "Steps in the order a user meets them. Colour = evidence "
                  "(dark green confirmed/tested → light green agreed → amber contested → red single-source). "
                  "Each box lists the endpoints the step calls.", "",
                  "```mermaid", self.flow(f), "```", "", "## Code flow per step", "",
                  "Call graph from the step's endpoint handler(s) (dark), grouped by file, depth ≤ "
                  f"{MAX_DEPTH}, plumbing hidden. More boxes and files = a busier step.", ""]
            for i, s in enumerate(f["steps"], 1):
                diagram, truncated = self.step(s)
                md.append(f"### {i}. {s['name']}")
                md.append("")
                md.append(f"`{s['evidence']}` · actor {s['actor']} · "
                          + (", ".join(f"`{e}`" for e in s["endpoints"]) or "no endpoint (system/UI step)"))
                if s["writes"]:
                    md.append(f"· writes {', '.join(f'`{w}`' for w in s['writes'][:6])}")
                md.append("")
                if diagram:
                    md += ["<details><summary>code flow</summary>", "", "```mermaid", diagram, "```", ""]
                    if truncated:
                        md.append(f"_{truncated} more reachable functions not drawn._")
                        md.append("")
                    md.append("</details>")
                    md.append("")
            (OUT / f"{f['id'].replace(':', '-')}.md").write_text("\n".join(md) + "\n")
        print(f"wrote {len(self.map['flows']) + 1} files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    Diagrams().write()
