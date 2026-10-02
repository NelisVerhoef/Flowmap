"""Static call graph of backend/app, for deterministic impact: which endpoints can reach a symbol.

Python is dynamic, so this resolves calls by what it can see:
- `f()` / `mod.f()` / `from x import f` -> exact edge.
- `obj.method()` where obj's type is unknown -> an edge to EVERY app method of that
  name (over-approximates; capped by AMBIGUOUS so `.get()` doesn't connect everything).
- a function referenced without being called (`Depends(f)`, `run_in_background(f)`,
  callbacks) -> edge, since it will be called by someone on our behalf.
Missed on purpose: string/registry dispatch (system workflows by name, block registry).

    python tools/flowmap/callgraph.py impact backend/app/providers/__init__.py:Provider.complete
"""

import ast
import json
import sys
from collections import defaultdict, deque
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

ROOT = config.root()
AMBIGUOUS = 6  # an obj.method() matching more app methods than this is too generic to follow


def module_of(rel):
    return config.module_name(rel)


class Graph:
    def __init__(self, read=lambda rel: (ROOT / rel).read_text(), files=None):
        """`read`/`files` let callers build the graph at any git revision."""
        self.defs = {}                          # "rel:Qual.name" -> (lineno, end)
        self.by_module = defaultdict(dict)      # module -> {top-level name: node id}
        self.methods = defaultdict(set)         # method name -> {node ids}
        self.bases = {}                         # class node id -> {base class names}
        self.edges = defaultdict(set)
        files = files or [p.relative_to(ROOT).as_posix() for d in config.python_roots()
                          for p in (ROOT / d).rglob("*.py")]
        self.packages = {module_of(rel).split(".")[0] for rel in files}
        trees = {}
        for rel in files:
            try:
                trees[rel] = ast.parse(read(rel))
            except (SyntaxError, FileNotFoundError):
                continue
            self._collect(rel, trees[rel])
        for rel, tree in trees.items():
            self._link(rel, tree)
        self.reverse = defaultdict(set)
        for a, bs in self.edges.items():
            for b in bs:
                self.reverse[b].add(a)

    def _collect(self, rel, tree):
        mod = module_of(rel)

        def walk(node, prefix, in_class):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qual = f"{prefix}{child.name}"
                    nid = f"{rel}:{qual}"
                    self.defs[nid] = (child.lineno, child.end_lineno)
                    if not prefix:
                        self.by_module[mod][child.name] = nid
                    if isinstance(child, ast.ClassDef):
                        self.bases[nid] = {b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "")
                                           for b in child.bases}
                    if in_class and not isinstance(child, ast.ClassDef):
                        self.methods[child.name].add(nid)
                    walk(child, f"{qual}.", isinstance(child, ast.ClassDef))
        walk(tree, "", False)

    def _imports(self, rel, tree):
        """local name -> ('mod', module) or ('sym', node id)."""
        names = {}
        pkg = module_of(rel).rsplit(".", 1)[0] if not rel.endswith("__init__.py") else module_of(rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in self.packages:
                        names[a.asname or a.name.split(".")[0]] = ("mod", a.name if a.asname else a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parts = pkg.split(".")
                    base = ".".join(parts[: len(parts) - node.level + 1] + ([base] if base else []))
                if base.split(".")[0] not in self.packages:
                    continue
                for a in node.names:
                    local = a.asname or a.name
                    if f"{base}.{a.name}" in self.by_module:
                        names[local] = ("mod", f"{base}.{a.name}")
                    elif a.name in self.by_module.get(base, {}):
                        names[local] = ("sym", self.by_module[base][a.name])
        return names

    def _link(self, rel, tree):
        mod = module_of(rel)
        imports = self._imports(rel, tree)
        local = self.by_module[mod]

        def resolve_name(name):
            if name in local:
                return {local[name]}
            kind, target = imports.get(name, (None, None))
            return {target} if kind == "sym" else set()

        def targets(node, called=True, owner=""):
            if isinstance(node, ast.Name):
                scope = owner  # closures first: a def nested in this function or its parents
                while ":" in scope:
                    if f"{scope}.{node.id}" in self.defs:
                        return {f"{scope}.{node.id}"}
                    scope = scope.rsplit(".", 1)[0] if "." in scope.split(":", 1)[1] else ""
                return resolve_name(node.id)
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    kind, target = imports.get(node.value.id, (None, None))
                    if kind == "mod":
                        hit = self.by_module.get(target, {}).get(node.attr)
                        return {hit} if hit else set()
                    if node.value.id in local and f"{local[node.value.id]}.{node.attr}" in self.defs:
                        return {f"{local[node.value.id]}.{node.attr}"}  # Class.method
                if not called:
                    return set()  # `x.score` read as a field is not a call to any .score()
                cands = self.methods.get(node.attr, set())
                return cands if len(cands) <= AMBIGUOUS or self._one_interface(cands) else set()
            return set()

        def walk(node, owner):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    nid = f"{rel}:{owner.split(':', 1)[1] + '.' if owner else ''}{child.name}"
                    # decorators and defaults run in the enclosing scope, but Depends(...) in
                    # defaults belongs to the endpoint: attribute them to the def itself
                    for d in child.decorator_list + getattr(getattr(child, "args", None), "defaults", []):
                        for sub in ast.walk(d):
                            if isinstance(sub, ast.Call):
                                self.edges[nid] |= targets(sub.func)
                            elif isinstance(sub, (ast.Name, ast.Attribute)):
                                self.edges[nid] |= targets(sub, called=False)
                    walk(child, nid)
                    continue
                if owner and isinstance(child, (ast.Call, ast.Name, ast.Attribute)):
                    if isinstance(child, ast.Call):
                        self.edges[owner] |= targets(child.func, owner=owner) - {owner}
                    elif isinstance(child.ctx, ast.Load):
                        self.edges[owner] |= targets(child, called=False, owner=owner) - {owner}
                walk(child, owner)
        walk(tree, "")

    def _one_interface(self, cands):
        """Many same-named methods that all implement one base class are polymorphic
        dispatch (scorer.score), not a generic name (.get) — keep the edges."""
        families = []
        for c in cands:
            cls = c.rsplit(".", 1)[0]
            if cls not in self.bases:
                return False
            families.append(self.bases[cls] | {cls.rsplit(":", 1)[1].split(".")[-1]})
        shared = set.intersection(*families) - {"object", "BaseModel", "Protocol", "Exception", ""}
        return bool(shared)

    def callers(self, nid):
        """Everything that can transitively reach nid (reverse BFS)."""
        seen, queue = {nid}, deque([nid])
        while queue:
            for prev in self.reverse.get(queue.popleft(), ()):
                if prev not in seen:
                    seen.add(prev)
                    queue.append(prev)
        return seen - {nid}

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
    g = Graph()
    if sys.argv[1:2] == ["impact"]:
        for nid in sys.argv[2:]:
            hits = impact(g, nid)
            flows = sorted({f for _, f in hits})
            print(f"{nid}: reachable from {len(hits)} endpoints in {len(flows)} flows: {', '.join(flows)}")
    else:
        n_edges = sum(len(v) for v in g.edges.values())
        print(f"{len(g.defs)} definitions, {n_edges} edges")
