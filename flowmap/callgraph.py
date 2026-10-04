"""Static call graph of the app, for deterministic impact: which entry points can reach a symbol.

Language-neutral: each builder in graphs/ parses its language into node ids
"repo/relative/file:Qual.name" (the spelling adapters use for handlers) and call edges, and
this merges them into one graph to walk. What a builder resolves, and what it misses on
purpose, is in its own docstring.

    flowmap callgraph                       definitions and edges in the working tree
    flowmap callgraph impact <file:sym>...  which entry points (and flows) can reach a symbol
    flowmap callgraph dump [<ref>]          the graph as JSON, at a git revision or the working tree
"""

import json
import sys
from collections import defaultdict, deque
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
import graphs  # noqa: E402

ROOT = config.root()


def _read_worktree(rel):
    p = ROOT / rel
    return p.read_text(errors="replace") if p.is_file() else None


class Graph:
    def __init__(self, read=None, files=None):
        """`read`/`files` let callers build the graph at any git revision; by default it is the
        working tree's graph sources."""
        read = read or _read_worktree
        files = config.graph_files() if files is None else files
        self.defs, self.edges, self.bases = {}, defaultdict(set), {}
        for builder in graphs.BUILDERS:
            mine = [f for f in files if f.endswith(builder.EXT)]
            if not mine:
                continue
            part = builder.build(mine, read)
            self.defs.update(part.defs)
            self.bases.update(part.bases)
            for a, bs in part.edges.items():
                self.edges[a] |= bs
        self.reverse = defaultdict(set)
        for a, bs in self.edges.items():
            for b in bs:
                self.reverse[b].add(a)

    def callers(self, nid):
        """Everything that can transitively reach nid (reverse BFS)."""
        return self._closure(self.reverse, nid)

    def callees(self, nid):
        """Everything nid can transitively reach (forward BFS)."""
        return self._closure(self.edges, nid)

    @staticmethod
    def _closure(adj, nid):
        seen, queue = {nid}, deque([nid])
        while queue:
            for nxt in adj.get(queue.popleft(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen - {nid}

    def edge_set(self):
        return {(a, b) for a, bs in self.edges.items() for b in bs}

    def reaches(self, src, dst, limit=12):
        """Shortest call chain src -> dst, or None."""
        prev, queue = {src: None}, deque([src])
        while queue:
            cur = queue.popleft()
            if cur == dst:
                path = []
                while cur:
                    path.append(cur)
                    cur = prev[cur]
                return path[::-1]
            if len(prev) > 20000:
                break
            for nxt in self.edges.get(cur, ()):
                if nxt not in prev:
                    prev[nxt] = cur
                    queue.append(nxt)
        return None


@cache
def endpoint_flows():
    """handler node id -> [(endpoint, flow id)] from inventory + map."""
    inv = json.loads((config.out() / "inventory.json").read_text())["endpoints"]
    mp = json.loads((config.out() / "map.json").read_text())
    flow_of = {e: f["id"] for f in mp["flows"] for s in f["steps"] for e in s["endpoints"]}
    out = defaultdict(list)
    for e in inv:
        out[e["handler"]].append((e["endpoint"], flow_of.get(e["endpoint"], "unplaced")))
    return out


def impact(graph, nid):
    """Endpoints (and their flows) that can reach nid."""
    handlers = endpoint_flows()
    hits = [(ep, flow) for c in graph.callers(nid) | {nid} for ep, flow in handlers.get(c, [])]
    return sorted(set(hits))


if __name__ == "__main__":
    if sys.argv[1:2] == ["dump"]:
        import lens  # late: lens imports this module
        g = lens.graph_at(sys.argv[2]) if len(sys.argv) > 2 else Graph()
        print(json.dumps({"defs": {k: list(v) for k, v in sorted(g.defs.items())},
                          "edges": sorted([a, b] for a, b in g.edge_set())}, indent=1))
        sys.exit(0)
    g = Graph()
    if sys.argv[1:2] == ["impact"]:
        for nid in sys.argv[2:]:
            hits = impact(g, nid)
            flows = sorted({f for _, f in hits})
            print(f"{nid}: reachable from {len(hits)} endpoints in {len(flows)} flows: {', '.join(flows)}")
    else:
        n_edges = sum(len(v) for v in g.edges.values())
        print(f"{len(g.defs)} definitions, {n_edges} edges")
