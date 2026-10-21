"""Every language codegraph parses besides Python (TypeScript/JS, Ruby, Go, Java, …), read from its index.

codegraph (https://github.com/colbymchenry/codegraph, `npm i -g @colbymchenry/codegraph`) is a
tree-sitter indexer. This builder writes the files at the revision being read into a scratch
directory, runs `codegraph init` there and reads the SQLite graph it leaves. It is optional:
without `codegraph` on PATH, EXT is empty and these files stay "no builder" blind spots.

- node ids: "rel:Qual.name", codegraph's `A::b` spelled `A.b`. Ruby keeps its namespace
  (`Admin.UsersController.index`), TS a component's handlers (`Dashboard.handleSubmit`).
- edges: calls, instantiations and references (a callback passed along, `before_action :auth`)
  between definitions; `new X()` also reaches X's constructor, as `X()` does in python.py.
- what it can't resolve (library calls, receivers of unknown type) has no edge.
- module-level code is not a node, so lens reports a change there as a blind spot.
Telemetry is off (DO_NOT_TRACK) and no watcher daemon starts.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from .part import Part

BIN = shutil.which("codegraph")
INSTALL = "npm i -g @colbymchenry/codegraph"
LANGS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rb", ".go", ".java", ".kt", ".swift", ".rs",
         ".php", ".cs", ".scala", ".dart")
EXT = LANGS if BIN else ()
DEFS = ("function", "method", "constructor", "class", "struct", "module", "component", "trait")
EDGES = ("calls", "instantiates", "references")
INITS = ("constructor", "initialize", "__init__", "init", "new")
CONFIG = ("tsconfig.json", "jsconfig.json", "package.json", "go.mod")  # how imports resolve
_SEEN = {}  # file text -> its outline, from every build: callers ask by text alone (see outline)


def build(files, read):
    texts = {rel: t for rel in files if (t := read(rel))}
    # project configs sit at the root or a package root (web/, apps/web/); deeper ones are rare
    dirs = {str(p) for rel in texts for p in PurePosixPath(rel).parents if str(p).count("/") < 2}
    extra = {}
    for d in dirs:
        for name in CONFIG:
            rel = name if d == "." else f"{d}/{name}"
            if t := read(rel):
                extra[rel] = t
    with tempfile.TemporaryDirectory() as tmp:
        for rel, text in {**extra, **texts}.items():
            (Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / rel).write_text(text)
        env = {**os.environ, "DO_NOT_TRACK": "1", "CODEGRAPH_NO_DAEMON": "1"}
        if subprocess.run([BIN, "init", "--yes", tmp], env=env, capture_output=True).returncode:
            return Part(unparsed=sorted(texts))
        db = sqlite3.connect(Path(tmp) / ".codegraph" / "codegraph.db")
        try:
            return _part(db, texts)
        finally:
            db.close()


def _part(db, texts):
    rows = db.execute(f"SELECT id, kind, name, qualified_name, file_path, start_line, end_line, signature, docstring "
                      f"FROM nodes WHERE kind IN ({','.join('?' * len(DEFS))})", DEFS).fetchall()
    ids, names, part = {}, {}, Part()
    outline = {rel: {"syms": [], "sig": {}, "doc": {}} for rel in texts}
    for cid, kind, name, qual, rel, start, end, sig, doc in rows:
        if rel not in texts:
            continue
        q = qual.replace("::", ".")
        ids[cid], names[cid] = f"{rel}:{q}", name
        part.defs[ids[cid]] = (start, end)
        o = outline[rel]
        o["syms"].append((start, end, q))
        o["sig"][q] = sig[1:-1] if sig and sig.startswith("(") and sig.endswith(")") else sig
        o["doc"][q] = (doc or "").strip().split("\n\n")[0].replace("\n", " ") or None
    for src, dst, kind in db.execute("SELECT source, target, kind FROM edges WHERE kind IN "
                                     "('calls', 'instantiates', 'references', 'contains', 'extends', 'implements')"):
        if src not in ids or dst not in ids:
            continue
        a, b = ids[src], ids[dst]
        if kind in EDGES:
            part.edges[a].add(b)
        elif kind == "contains" and names[dst] in INITS:
            part.edges[a].add(b)  # constructing a class runs its constructor
        elif kind in ("extends", "implements"):
            part.bases.setdefault(a, set()).add(names[dst])
    for rel, errors in db.execute("SELECT path, errors FROM files"):
        if rel in texts and errors and json.loads(errors):
            part.unparsed.append(rel)
    for rel, o in outline.items():
        o["syms"].sort()
        _SEEN[texts[rel]] = o
    return part


def hint(rels):
    """What to install so `rels` get a call graph: '' when codegraph is here or wouldn't help."""
    return "" if BIN or not any(r.endswith(LANGS) for r in rels) else f" (`{INSTALL}` gives these a call graph)"


def outline(rel, text):
    """Index `text` on its own if no build has seen it, so symbols/signature/doc can answer."""
    if text not in _SEEN:
        build([rel], lambda r: text if r == rel else None)


def symbols(text):
    return _SEEN.get(text, {}).get("syms", [])


def signature(text, sym):
    return _SEEN.get(text, {}).get("sig", {}).get(sym)


def doc(text, sym):
    return _SEEN.get(text, {}).get("doc", {}).get(sym)
