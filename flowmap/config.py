"""Per-repo configuration. The tools live anywhere; the repo they map is the one you run them in.

The target repo is FLOWMAP_ROOT if set, else the git toplevel of the current directory. Its
`flowmap.toml` says where the code is, how to find entry points, and which flows you own.
Every key is optional; a repo with no config gets discovery mode and auto-detected adapters.

    name = "Acme"                              # shown on the atlas; defaults to the repo folder name
    out = "docs/flowmap"                       # where the map lives in the target repo
    viewer = "https://.../change.html"         # hosted `flowmap viewer`, for `flowmap change --link`

    [[entry]]                                  # one per app; see adapters/ for options
    adapter = "fastapi"                        # fastapi | rails | nextjs | cli | pattern | list
    main = "backend/app/main.py"

    [[entry]]                                  # any other stack: a regex for its registrations
    adapter = "pattern"
    files = ["svc/mcp/*.py"]
    match = '''@\\w+\\.tool\\b'''              # TOML '''...''': backslashes and quotes stay literal
    endpoint = "MCP {def}"

    [code]
    graph = ["backend/app", "web/src"]         # call-graph sources (deterministic reach); `python` is the old name
    tests = ["backend/tests"]                  # a step is "tested" when tests hit its endpoints
    other = ["frontend/src"]                   # other app code the PR lens should recognise

    [flows]
    engine = "backend/app/executor.py:run_workflow"   # optional: a hub to fold in diagrams
    plumbing = ["auth", "db"]                          # components hidden from the system view
    [[flows.vocabulary]]                               # empty = discovery mode
    id = "review-queue"
    scope = "held/released/rejected runs, annotations"
"""

import os
import re
import subprocess
import tomllib
from functools import cache
from pathlib import Path

DEFAULT_PLUMBING = ["auth", "db", "config", "settings", "analytics", "sentry", "logging", "serialisation"]


@cache
def root() -> Path:
    env = os.environ.get("FLOWMAP_ROOT")
    if env:
        return Path(env).resolve()
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
        return Path(top.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


@cache
def load() -> dict:
    path = root() / "flowmap.toml"
    cfg = tomllib.loads(path.read_text()) if path.exists() else {}
    cfg.setdefault("out", "docs/flowmap")
    cfg.setdefault("entry", [])
    code = cfg.setdefault("code", {})
    for k in ("graph", "python", "tests", "other"):
        code.setdefault(k, [])
    flows = cfg.setdefault("flows", {})
    flows.setdefault("vocabulary", [])
    flows.setdefault("engine", None)
    flows.setdefault("plumbing", DEFAULT_PLUMBING)
    if not cfg["entry"]:
        cfg["entry"] = detect_entries()
    return cfg


def detect_entries():
    """Best guess at adapters when flowmap.toml names none."""
    r, found = root(), []
    if (r / "config/routes.rb").exists():
        found.append({"adapter": "rails", "root": "."})
    for d in [".", "web", "frontend", "app", "apps/web"]:
        base = r / d
        if (base / "next.config.js").exists() or (base / "next.config.mjs").exists() or (base / "next.config.ts").exists():
            found.append({"adapter": "nextjs", "root": d})
    for main in r.glob("**/main.py"):
        if "node_modules" in main.parts or ".venv" in main.parts:
            continue
        if "FastAPI(" in main.read_text(errors="replace"):
            found.append({"adapter": "fastapi", "main": main.relative_to(r).as_posix()})
    return found


def out() -> Path:
    return root() / load()["out"]


def flow_order():
    return [f["id"] for f in load()["flows"]["vocabulary"]]


VENDORED = {"node_modules", ".venv", "venv", "__pycache__", ".next", ".git"}


def graph_roots():
    """Directories the call graph is built from: [code].graph, plus its old name `python`."""
    code = load()["code"]
    return list(dict.fromkeys(code["graph"] + code["python"]))


def graph_files(ref=None):
    """Files under graph_roots() that some call-graph builder parses: at a git revision, or in
    the working tree (untracked and ignored files included) when ref is None. Vendored dirs
    below a root never count; a root you name is yours even if it sits under one."""
    import graphs  # late: graphs imports config
    roots, ext = [r.strip("/") for r in graph_roots()], graphs.suffixes()
    if not roots:
        return []
    if ref:
        listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, "--", *roots], cwd=root(),
                                capture_output=True, text=True, check=True).stdout.splitlines()
    else:
        listed = []
        for d in roots:
            for here, dirs, files in os.walk(root() / d):  # prune vendored dirs instead of walking them
                dirs[:] = sorted(x for x in dirs if x not in VENDORED)
                listed += [(Path(here) / f).relative_to(root()).as_posix() for f in sorted(files) if f.endswith(ext)]

    def vendored(rel):
        r = next((r for r in roots if r in ("", ".") or rel.startswith(r + "/")), "")
        below = rel if r in ("", ".") else rel[len(r) + 1:]
        return VENDORED.intersection(below.split("/")[:-1])
    return [f for f in dict.fromkeys(listed) if f.endswith(ext) and not vendored(f)]


def app_dirs():
    """Every directory holding app code: call-graph sources, adapter roots, and `other`."""
    cfg = load()
    dirs = graph_roots() + list(cfg["code"]["other"])
    for e in cfg["entry"]:
        if e["adapter"] == "rails":
            base = e.get("root", ".").rstrip("/")
            dirs.append("app" if base in (".", "") else f"{base}/app")
        elif e["adapter"] == "nextjs":
            base = e.get("root", ".").rstrip("/")
            dirs.append("." if base in (".", "") else base)
        elif e["adapter"] == "fastapi":
            dirs.append(str(Path(e["main"]).parent))
        elif e["adapter"] == "cli":
            dirs += [e["commands"].strip("/")] if e.get("commands") else []
            dirs += [str(Path(e["main"]).parent)] if e.get("main") else []
        elif e["adapter"] == "pattern":  # a glob's directory part, up to its first wildcard
            dirs += [str(Path(re.split(r"[*?[]", g)[0] + "x").parent) for g in e["files"]]
        elif e["adapter"] == "list":
            dirs += [str(Path(x["handler"].split(":", 1)[0]).parent) for x in e["entries"]]
    return sorted(set(dirs))


def module_name(rel):
    """Dotted module for a python file, honouring each configured root's import base:
    the first parent directory (walking up) without an __init__.py is on sys.path."""
    path = root() / rel
    parts = [path.stem] if path.stem != "__init__" else []
    d = path.parent
    while (d / "__init__.py").exists() and d != root():
        parts.insert(0, d.name)
        d = d.parent
    return ".".join(parts)
