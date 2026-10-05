"""Python: the standard library's AST, resolved by what it can see.

- `f()` / `mod.f()` / `from x import f` -> exact edge.
- `obj.method()` where obj's type is unknown -> an edge to EVERY app method of that
  name (over-approximates; capped by AMBIGUOUS so `.get()` doesn't connect everything).
- a function referenced without being called (`Depends(f)`, `run_in_background(f)`,
  callbacks) -> edge, since it will be called by someone on our behalf.
- a script's `if __name__ == "__main__":` block -> node `file:__main__` (CLI entry points).
- `Class()` -> edge to `Class.__init__`, so what a constructor calls is reachable.
- `x.f()` where x may be an app module passed around as a value (`PLUGINS = [loud]`) -> also
  an edge to each such module's `f`; modules only ever used as `mod.f` don't count.
- a module-level alias that injects a dependency (FastAPI's `X = Annotated[T, Depends(f)]`) ->
  node `file:X` with an edge to f, so an endpoint annotated `user: X` reaches f.
- a def starts at its first decorator: dropping an auth dependency there changes the handler.
Missed on purpose: string/registry dispatch (system workflows by name, block registry).
"""

import ast
import copy
from collections import defaultdict

import config
from adapters.cli import main_guard

from .part import Part

EXT = (".py",)
AMBIGUOUS = 6  # an obj.method() matching more app methods than this is too generic to follow


def build(files, read):
    b = _Builder(files, read)
    return Part(defs=b.defs, edges=b.edges, bases=b.bases, unparsed=b.unparsed)


def _start(node):
    return min([d.lineno for d in node.decorator_list] + [node.lineno])


def symbols(text):
    """[(start, end, 'Class.method' or 'fn')] innermost-last."""
    out = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                out.append((_start(child), child.end_lineno, name))
                walk(child, f"{name}.")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    walk(tree, "")
    guard = main_guard(tree)
    if guard:
        out.append((guard.lineno, guard.end_lineno, "__main__"))
    return out


def signature(text, sym):
    """Argument list of a def, for spotting contract changes."""
    try:
        tree = ast.parse(text or "")
    except SyntaxError:
        return None
    parts = sym.split(".")
    nodes = tree.body
    for i, p in enumerate(parts):
        hit = next((n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and n.name == p), None)
        if hit is None:
            return None
        if i == len(parts) - 1:
            return ast.unparse(hit.args) if not isinstance(hit, ast.ClassDef) else None
        nodes = hit.body
    return None


def live(text):
    """Module-level lines that run: not blanks, comments, imports, docstrings or defs. None if
    the text doesn't parse, so every line counts."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    out = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        out |= set(range(node.lineno, node.end_lineno + 1))
    return out


def same(base_text, head_text, sym):
    """True when `sym` changed only in docstrings, comments or formatting."""
    try:
        a, b = _find(ast.parse(base_text), sym), _find(ast.parse(head_text), sym)
    except (SyntaxError, ValueError):
        return False
    return a is not None and b is not None and _shape(a) == _shape(b)


def _find(tree, sym):
    node = tree
    for part in sym.split("."):
        node = next((c for c in ast.iter_child_nodes(node)
                     if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and c.name == part), None)
        if node is None:
            return None
    return node


def _shape(node):
    """The node's AST without docstrings or positions: equal shapes can't behave differently."""
    node = copy.deepcopy(node)
    for n in ast.walk(node):
        body = getattr(n, "body", None)
        if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and body
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            n.body = body[1:] or [ast.Pass()]
    return ast.dump(node, include_attributes=False)


class _Builder:
    def __init__(self, files, read):
        self.defs = {}                          # "rel:Qual.name" -> (lineno, end)
        self.by_module = defaultdict(dict)      # module -> {top-level name: node id}
        self.methods = defaultdict(set)         # method name -> {node ids}
        self.bases = {}                         # class node id -> {base class names}
        self.edges = defaultdict(set)
        self.module_values = set()              # app modules used as values, not just `mod.f`
        self.aliases = {}                       # alias node id -> its value, e.g. Annotated[..., Depends(f)]
        self.unparsed = []                      # files this Python can't parse
        self.packages = {config.module_name(rel).split(".")[0] for rel in files}
        trees = {}
        for rel in files:
            text = read(rel)
            if text is None:
                continue
            try:
                trees[rel] = ast.parse(text)
            except (SyntaxError, ValueError):
                self.unparsed.append(rel)
                continue
            self._collect(rel, trees[rel])
        for rel, tree in trees.items():
            self._find_module_values(rel, tree)
        for rel, tree in trees.items():
            self._link(rel, tree)
        for cls in self.bases:
            if f"{cls}.__init__" in self.defs:
                self.edges[cls].add(f"{cls}.__init__")

    def _find_module_values(self, rel, tree):
        imports = self._imports(rel, tree)
        bases = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in bases:
                kind, target = imports.get(n.id, (None, None))
                if kind == "mod":
                    self.module_values.add(target)

    def _collect(self, rel, tree):
        mod = config.module_name(rel)

        def walk(node, prefix, in_class):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qual = f"{prefix}{child.name}"
                    nid = f"{rel}:{qual}"
                    self.defs[nid] = (_start(child), child.end_lineno)
                    if not prefix:
                        self.by_module[mod][child.name] = nid
                    if isinstance(child, ast.ClassDef):
                        self.bases[nid] = {b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "")
                                           for b in child.bases}
                    if in_class and not isinstance(child, ast.ClassDef):
                        self.methods[child.name].add(nid)
                    walk(child, f"{qual}.", isinstance(child, ast.ClassDef))
        walk(tree, "", False)
        guard = main_guard(tree)
        if guard:
            self.defs[f"{rel}:__main__"] = (guard.lineno, guard.end_lineno)
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and any(isinstance(s, ast.Call) and "Depends" in (getattr(s.func, "id", None),
                                                                      getattr(s.func, "attr", None))
                            for s in ast.walk(node.value))):
                nid = f"{rel}:{node.targets[0].id}"
                self.defs[nid] = (node.lineno, node.end_lineno)
                self.by_module[mod][node.targets[0].id] = nid
                self.aliases[nid] = node.value

    def _imports(self, rel, tree):
        """local name -> ('mod', module) or ('sym', node id)."""
        names = {}
        pkg = config.module_name(rel).rsplit(".", 1)[0] if not rel.endswith("__init__.py") else config.module_name(rel)
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
        mod = config.module_name(rel)
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
                cands = self.methods.get(node.attr, set()) | {
                    self.by_module[m][node.attr] for m in self.module_values if node.attr in self.by_module.get(m, {})}
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
        for nid, value in self.aliases.items():
            if nid.startswith(f"{rel}:"):
                for sub in ast.walk(value):
                    if isinstance(sub, ast.Call):
                        self.edges[nid] |= targets(sub.func)
                    elif isinstance(sub, (ast.Name, ast.Attribute)):
                        self.edges[nid] |= targets(sub, called=False)
        guard = main_guard(tree)
        walk(ast.Module(body=[n for n in tree.body if n is not guard], type_ignores=[]), "")
        if guard:
            walk(guard, f"{rel}:__main__")

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
