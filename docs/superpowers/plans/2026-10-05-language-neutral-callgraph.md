# Language-neutral call graph (phase 1 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split flowmap's Python-only call graph into a language-neutral core plus per-language builders. Remove every `.py` assumption from the code that uses the graph, so a TypeScript (Next.js) or Ruby (Rails) builder can be added later without touching lens, change, atlas or diagrams.

**Architecture:** `flowmap/callgraph.py` keeps the `Graph` class and its walking API (`defs`, `edges`, `reverse`, `bases`, `callers`, `callees`, `reaches`, `edge_set`). It no longer parses anything. Instead it asks each builder in the new `flowmap/graphs/` package to parse the files with its suffixes, then merges the results. The existing Python AST code moves almost unchanged into `flowmap/graphs/python.py`. Graph sources come from a new `[code].graph` key in `flowmap.toml`, with `python` kept as an alias. A new `flowmap callgraph check` reports whether every entry point's handler is a graph node. That check is the acceptance test for the Next.js and Ruby builders in phases 2 and 3.

**Tech Stack:** Python 3.11+ standard library only (`ast`, `tomllib`, `unittest`, `subprocess`). Fixture repos are built with git.

**Spec:** The gap analysis in this session, summarized under *Background* below.

## Global Constraints

- Python 3.11+, **no third-party dependencies**. Tests use `unittest`, not pytest.
- Modules import each other flat (`sys.path.insert(0, <flowmap dir>)`, then `import config`), the same way the existing tools do. Packages under `flowmap/` (`adapters/`, `graphs/`) use relative imports internally.
- **No behaviour change for Python repos.** The golden outputs captured in Task 1 must stay byte-identical (lens) or JSON-equal (change facts, graph dumps) through every later task.
- Node ids are always `repo/relative/file:Qual.name`. This is the spelling adapters use for handlers.
- Match the existing style: dense code, short docstrings that say *why*, few inline comments, commit subjects like `area: lowercase summary`.
- Do **not** regenerate anything under `docs/flowmap/`. The goldens read `docs/flowmap/map.json`, and the repo's own map is refreshed separately.

## Background

The Python-only parts of flowmap today:

- `callgraph.Graph` parses `[code].python` with `ast`.
- `lens.graph_at`, `atlas.overlay` and `diagrams.Diagrams` filter on `.py` and `python_roots()`.
- `lens.main` skips non-`.py` symbols for Reach (`lens.py:286`) and gates Reach diff on `python_roots()` (`lens.py:321`).
- `change.signature` is Python AST only.
- `lens.defs` dispatches to `py_symbols`, or to regex fallbacks for Ruby and TypeScript.

Phase 1 (this plan) makes all of these go through one builder registry. Phase 2 (a TypeScript builder through the target repo's `node_modules/typescript`) and phase 3 (a Ruby builder through Ruby's Ripper or Prism) each get their own plan once this one lands.

## Review Focus

1. **A file that doesn't parse at a git revision** (a syntax error at base or head). The graph skips it and `lens`, `change` and `callgraph dump` still run. Pinned in Task 2.
2. **A repo with no graph roots configured.** `lens` runs and simply has no Reach section. Pinned in Task 3.
3. **A graph root that doesn't exist at the revision being read** (a directory added in the PR). `git ls-tree` returns nothing, the graph is empty there, and nothing crashes. Pinned in Task 3.
4. **Vendored code under a graph root** (`node_modules/`, `.venv/`). It stays out of the graph, so it doesn't swamp the by-name method matching. Pinned in Task 3.
5. **A handler in a language with no builder yet** (a Next.js route next to a Python CLI). `callgraph check` reports it as *not graphed*, not *broken*, and exits 0. Pinned in Task 4.

---

### Task 1: Test harness and golden outputs of today's behaviour

**Files:**
- Modify: `flowmap/callgraph.py` (the `__main__` block, add `dump`)
- Create: `tests/__init__.py` (empty)
- Create: `tests/helpers.py`
- Create: `tests/test_golden.py`
- Create: `tests/golden/lens-6d9eaff-770f1a7.md`, `tests/golden/change-facts-6d9eaff-770f1a7.json`, `tests/golden/graph-6d9eaff.json`, `tests/golden/graph-770f1a7.json` (generated)

**Interfaces:**
- Produces: `flowmap callgraph dump [<ref>]` prints `{"defs": {node: [start, end]}, "edges": [[a, b], ...]}` sorted, from `lens.graph_at(ref)` or, with no ref, the working-tree `Graph()`.
- Produces: `tests.helpers.flowmap(*args, root=REPO) -> str`, `tests.helpers.fixture_repo(test, files) -> (Path, sha)`, `tests.helpers.commit(root, files, message="change") -> sha`, `tests.helpers.cli_app(code='python = ["tool"]', extra="") -> dict[str, str]`.

- [ ] **Step 1: Add `dump` to the callgraph command**

In `flowmap/callgraph.py`, replace the `if __name__ == "__main__":` block with:

```python
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
```

Run: `bin/flowmap callgraph dump 770f1a7 | head -5`
Expected: JSON starting with `{` and `"defs": {` and node ids like `"flowmap/atlas.py:..."`.

- [ ] **Step 2: Write the test helpers**

`tests/__init__.py`: empty file.

`tests/helpers.py`:

```python
"""Run flowmap as a user would (a subprocess per command, FLOWMAP_ROOT set) against this repo
or a throwaway fixture repo. Subprocesses because config caches the repo root per process."""

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FLOWMAP = REPO / "bin" / "flowmap"


def flowmap(*args, root=REPO):
    env = {**os.environ, "FLOWMAP_ROOT": str(root)}
    r = subprocess.run([sys.executable, str(FLOWMAP), *args], cwd=root, env=env, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"flowmap {' '.join(args)} exited {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=flowmap", "-c", "user.email=flowmap@example.com", *args],
                          cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def commit(root, files, message="change"):
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text).lstrip())
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def fixture_repo(test, files):
    """A git repo holding `files`, deleted when the test ends. Returns (root, sha of that commit)."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    root = Path(tmp.name).resolve()  # macOS: /var -> /private/var, as config.root() resolves it
    git(root, "init", "-q")
    return root, commit(root, files, "base")


def cli_app(code='python = ["tool"]', extra=""):
    """A two-file Python CLI: `tool run` calls helpers.shout. `code` is the [code] body;
    `extra` is more TOML placed before [code] (another [[entry]], say)."""
    return {
        "flowmap.toml": f'[[entry]]\nadapter = "cli"\nprog = "tool"\ncommands = "tool"\n{extra}\n[code]\n{code}\n',
        "tool/run.py": '''
            from helpers import shout


            def main():
                print(shout("hi"))


            if __name__ == "__main__":
                main()
        ''',
        "tool/helpers.py": '''
            def shout(s):
                return s.upper()
        ''',
        "docs/flowmap/map.json": '{"flows": [], "runs": []}\n',
    }
```

- [ ] **Step 3: Write the golden test (it fails because there are no goldens yet)**

`tests/test_golden.py`:

```python
"""Characterisation: flowmap's output on this repo's own history must not move while the call
graph is restructured. Regenerate only on purpose (python3 -m tests.test_golden --regen) and
read the diff: a changed golden is a behaviour change."""

import json
import sys
import unittest

from tests.helpers import REPO, flowmap

GOLDEN = REPO / "tests" / "golden"
BASE, HEAD = "6d9eaff", "770f1a7"


def facts(text):
    fx = json.loads(text)
    fx["symbols"] = sorted(fx["symbols"], key=lambda s: s["id"])  # built from a set: order varies per run
    return fx


CASES = {
    f"lens-{BASE}-{HEAD}.md": lambda: flowmap("lens", BASE, HEAD),
    f"change-facts-{BASE}-{HEAD}.json": lambda: flowmap("change", BASE, HEAD, "--facts"),
    f"graph-{BASE}.json": lambda: flowmap("callgraph", "dump", BASE),
    f"graph-{HEAD}.json": lambda: flowmap("callgraph", "dump", HEAD),
}


class GoldenTest(unittest.TestCase):
    def test_lens(self):
        name = f"lens-{BASE}-{HEAD}.md"
        self.assertEqual(CASES[name](), (GOLDEN / name).read_text())

    def test_change_facts(self):
        name = f"change-facts-{BASE}-{HEAD}.json"
        self.assertEqual(facts(CASES[name]()), facts((GOLDEN / name).read_text()))

    def test_graph_dumps(self):
        for ref in (BASE, HEAD):
            name = f"graph-{ref}.json"
            with self.subTest(ref=ref):
                self.assertEqual(json.loads(CASES[name]()), json.loads((GOLDEN / name).read_text()))


if __name__ == "__main__" and "--regen" in sys.argv:
    GOLDEN.mkdir(exist_ok=True)
    for name, run in CASES.items():
        (GOLDEN / name).write_text(run())
        print(f"wrote tests/golden/{name}")
```

Run: `python3 -m unittest tests.test_golden -v`
Expected: FAIL / ERROR with `FileNotFoundError` for `tests/golden/...`.

- [ ] **Step 4: Generate the goldens from today's code**

Run: `python3 -m tests.test_golden --regen`
Expected: four `wrote tests/golden/...` lines. `tests/golden/lens-6d9eaff-770f1a7.md` starts with `# Flow lens: \`6d9eaff..770f1a7\`` and has `## Reach (call graph, deterministic)` and `## Reach diff (call graph, base → head)` sections.

- [ ] **Step 5: Run the goldens twice to prove they are stable**

Run: `python3 -m unittest tests.test_golden -v && python3 -m unittest tests.test_golden -v`
Expected: 3 tests pass both times. If a test fails only on the second run, the output depends on set ordering. Sort that field in `facts()` the same way `symbols` is sorted, then regenerate.

- [ ] **Step 6: Commit**

```bash
git add flowmap/callgraph.py tests/
git commit -m "tests: golden lens, change facts and graph dumps; callgraph dump"
```

---

### Task 2: Builder registry and the Python builder; `Graph` becomes language-neutral

**Files:**
- Create: `flowmap/graphs/__init__.py`
- Create: `flowmap/graphs/part.py`
- Create: `flowmap/graphs/python.py`
- Modify: `flowmap/callgraph.py` (whole file except `endpoint_flows`, `impact` and `__main__`)
- Modify: `flowmap/lens.py:47-65` (delete `py_symbols`), `flowmap/lens.py:97-101` (`defs`)
- Modify: `flowmap/change.py:839-855` (`signature`) and its call site at `flowmap/change.py:883`
- Test: `tests/test_graphs.py`

**Interfaces:**
- Consumes: `config.module_name(rel)`, `adapters.cli.main_guard(tree)`.
- Produces:
  - `graphs.Part(defs: dict[str, tuple[int, int]], edges: dict[str, set[str]], bases: dict[str, set[str]])`
  - `graphs.BUILDERS: list[module]`
  - `graphs.builder_for(rel: str) -> module | None`
  - `graphs.suffixes() -> tuple[str, ...]`
  - Each builder module has:
    - `EXT: tuple[str, ...]`
    - `build(files: list[str], read: Callable[[str], str | None]) -> Part`
    - `symbols(text: str) -> list[tuple[int, int, str]]`
    - `signature(text: str, sym: str) -> str | None`
  - `callgraph.Graph(read=None, files=None)` keeps its public attributes and methods unchanged.

- [ ] **Step 1: Write the failing tests**

`tests/test_graphs.py`:

```python
import json
import sys
import unittest

from tests.helpers import REPO, cli_app, fixture_repo, flowmap

sys.path.insert(0, str(REPO / "flowmap"))
import graphs  # noqa: E402


class RegistryTest(unittest.TestCase):
    def test_builder_dispatch_by_suffix(self):
        self.assertIs(graphs.builder_for("app/x.py"), graphs.python)
        self.assertIsNone(graphs.builder_for("app/page.tsx"))
        self.assertIn(".py", graphs.suffixes())

    def test_python_symbols_and_signature(self):
        text = "class A:\n    def m(self, x=1):\n        pass\n"
        self.assertEqual(graphs.python.symbols(text), [(1, 3, "A"), (2, 3, "A.m")])
        self.assertEqual(graphs.python.signature(text, "A.m"), "self, x=1")
        self.assertIsNone(graphs.python.signature(text, "A"))


class PythonBuilderTest(unittest.TestCase):
    def test_unparseable_file_is_skipped(self):
        files = cli_app()
        files["tool/broken.py"] = "def oops(:\n"
        root, base = fixture_repo(self, files)
        for args in (("callgraph", "dump", base), ("callgraph", "dump")):
            with self.subTest(args=args):
                g = json.loads(flowmap(*args, root=root))
                self.assertIn(["tool/run.py:main", "tool/helpers.py:shout"], g["edges"])
                self.assertIn(["tool/run.py:__main__", "tool/run.py:main"], g["edges"])
                self.assertFalse([d for d in g["defs"] if d.startswith("tool/broken.py")])
```

Run: `python3 -m unittest tests.test_graphs -v`
Expected: ERROR `ModuleNotFoundError: No module named 'graphs'`. (`PythonBuilderTest` already describes today's behaviour. It's there to guard the move.)

- [ ] **Step 2: Create `flowmap/graphs/part.py`**

```python
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Part:
    """One builder's share of the graph."""
    defs: dict = field(default_factory=dict)                   # node id -> (first line, last line)
    edges: dict = field(default_factory=lambda: defaultdict(set))  # node id -> {node ids it can call}
    bases: dict = field(default_factory=dict)                  # class node id -> {base class names}
```

- [ ] **Step 3: Create `flowmap/graphs/__init__.py`**

```python
"""Call-graph builders: one per language, all spelling nodes the same way.

A builder module exposes:
    EXT = (".py",)                                  # file suffixes it parses
    build(files, read) -> Part                      # definitions, call edges, classes
    symbols(text) -> [(start, end, "Qual.name")]    # places diff lines on definitions
    signature(text, "Qual.name") -> str | None      # a def's parameters, for contract changes

Node ids are "repo/relative/file:Qual.name", the spelling adapters use for handlers, so every
entry point's handler is a node the graph can walk from (`flowmap callgraph check` says which
are not). `read(rel) -> text | None` lets a builder parse any git revision.
"""

from . import python
from .part import Part  # noqa: F401

BUILDERS = [python]


def builder_for(rel):
    return next((b for b in BUILDERS if rel.endswith(b.EXT)), None)


def suffixes():
    return tuple(s for b in BUILDERS for s in b.EXT)
```

- [ ] **Step 4: Create `flowmap/graphs/python.py` by moving code out of `callgraph.py` and `lens.py`**

Move the bodies over verbatim. The only changes are the ones listed after the code:

```python
"""Python: the standard library's AST, resolved by what it can see.

- `f()` / `mod.f()` / `from x import f` -> exact edge.
- `obj.method()` where obj's type is unknown -> an edge to EVERY app method of that
  name (over-approximates; capped by AMBIGUOUS so `.get()` doesn't connect everything).
- a function referenced without being called (`Depends(f)`, `run_in_background(f)`,
  callbacks) -> edge, since it will be called by someone on our behalf.
- a script's `if __name__ == "__main__":` block -> node `file:__main__` (CLI entry points).
Missed on purpose: string/registry dispatch (system workflows by name, block registry).
"""

import ast
from collections import defaultdict

import config
from adapters.cli import main_guard

from .part import Part

EXT = (".py",)
AMBIGUOUS = 6  # an obj.method() matching more app methods than this is too generic to follow


def build(files, read):
    b = _Builder(files, read)
    return Part(defs=b.defs, edges=b.edges, bases=b.bases)


def symbols(text):
    """[(start, end, 'Class.method' or 'fn')] innermost-last."""
    # body: lens.py py_symbols, lines 49-65, unchanged


def signature(text, sym):
    """Argument list of a def, for spotting contract changes."""
    # body: change.py signature, lines 841-855, unchanged


class _Builder:
    def __init__(self, files, read):
        self.defs = {}                          # "rel:Qual.name" -> (lineno, end)
        self.by_module = defaultdict(dict)      # module -> {top-level name: node id}
        self.methods = defaultdict(set)         # method name -> {node ids}
        self.bases = {}                         # class node id -> {base class names}
        self.edges = defaultdict(set)
        self.packages = {config.module_name(rel).split(".")[0] for rel in files}
        trees = {}
        for rel in files:
            text = read(rel)
            if text is None:
                continue
            try:
                trees[rel] = ast.parse(text)
            except (SyntaxError, ValueError):
                continue
            self._collect(rel, trees[rel])
        for rel, tree in trees.items():
            self._link(rel, tree)

    # _collect, _imports, _link, _one_interface: moved from callgraph.Graph unchanged,
    # except `module_of(rel)` becomes `config.module_name(rel)` (3 places).
```

The actual file has the real bodies wherever the comments above say "body: …" or "moved …". Copy each one character for character. The only edits are:

- `module_of(rel)` → `config.module_name(rel)`
- the `read`/parse loop shown above, which skips `None` the same way the old default reader's `FileNotFoundError` did, and also skips `ValueError` for files with null bytes.

`AMBIGUOUS` is used inside `_link`, which now lives in this module, so it moves here.

- [ ] **Step 5: Rewrite `flowmap/callgraph.py` as the language-neutral core**

Replace everything above `@cache def endpoint_flows` with the code below. Keep `endpoint_flows`, `impact` and the Task 1 `__main__` block.

```python
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
        if files is None:
            files = [p.relative_to(ROOT).as_posix() for d in config.python_roots() for p in (ROOT / d).rglob("*.py")]
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

    # callers, callees, _closure, edge_set, reaches: unchanged from the old Graph
```

(Copy `callers`, `callees`, `_closure`, `edge_set` and `reaches` over unchanged. Delete `module_of`, `AMBIGUOUS`, `_collect`, `_imports`, `_link`, `_one_interface`, and the imports `ast` and `from adapters.cli import main_guard`. The `files is None` default is temporary; Task 3 replaces it with `config.graph_files()`.)

- [ ] **Step 6: Point `lens.defs` and `change.signature` at the builders**

In `flowmap/lens.py`, delete `py_symbols` (lines 47-65), add `import graphs  # noqa: E402` next to the other flat imports, and replace `defs`:

```python
def defs(rel, text):
    """[(start, end, name)] for any supported language: its graph builder's parser if it has
    one, else a regex outline."""
    if not text:
        return []
    builder = graphs.builder_for(rel)
    if builder:
        return builder.symbols(text)
    return rb_symbols(text) if rel.endswith(".rb") else ts_symbols(text)
```

If `main_guard` is no longer used in `lens.py`, remove its import.

In `flowmap/change.py`, add `import graphs  # noqa: E402` next to `import lens`, drop `import ast`, and replace `signature`:

```python
def signature(rel, text, sym):
    """A def's parameter list, for spotting contract changes (None where no builder parses rel)."""
    builder = graphs.builder_for(rel)
    return builder.signature(text, sym) if builder else None
```

Then update its call site (around `change.py:883`):

```python
            sig_b, sig_h = signature(rel, base_text, s), signature(rel, head_text, s)
```

- [ ] **Step 7: Run all the tests**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: all pass, including the 3 golden tests (the Python output is unchanged).

- [ ] **Step 8: Smoke-test the commands that build the graph from the working tree**

Run: `bin/flowmap callgraph && bin/flowmap callgraph impact flowmap/callgraph.py:Graph.callers`
Expected: a `N definitions, M edges` line (the numbers differ from before because the code moved), and an impact line that lists flows. No traceback.

- [ ] **Step 9: Commit**

```bash
git add flowmap/graphs flowmap/callgraph.py flowmap/lens.py flowmap/change.py tests/test_graphs.py
git commit -m "callgraph: language-neutral core over per-language builders; python builder"
```

---

### Task 3: `[code].graph` roots, and no `.py` assumptions in lens, atlas and diagrams

**Files:**
- Modify: `flowmap/config.py` (docstring, `load`, replace `python_roots` with `graph_roots`, add `graph_files`, `app_dirs`)
- Modify: `flowmap/callgraph.py` (`Graph.__init__` default files)
- Modify: `flowmap/lens.py:135-170` (`importers`, `graph_at`), `flowmap/lens.py:286`, `flowmap/lens.py:321`
- Modify: `flowmap/atlas.py:18,82-85` (use `lens.graph_at`, drop the `Graph` import)
- Modify: `flowmap.toml` (this repo: `python` → `graph`)
- Modify: `skills/flowmap-build/SKILL.md:17`
- Test: `tests/test_graph_roots.py`

**Interfaces:**
- Consumes: `graphs.suffixes()` from Task 2.
- Produces:
  - `config.graph_roots() -> list[str]`: `[code].graph` followed by `[code].python`, deduplicated.
  - `config.graph_files(ref: str | None = None) -> list[str]`: repo-relative files under the graph roots that some builder parses, at `ref` or in the working tree, with vendored directories skipped.
  - `config.python_roots` is removed.

- [ ] **Step 1: Write the failing tests**

`tests/test_graph_roots.py`:

```python
import json
import unittest

from tests.helpers import cli_app, commit, fixture_repo, flowmap

REACH = "- `tool/helpers.py:shout` — reachable from 1 endpoints in 0 flows"


class GraphRootsTest(unittest.TestCase):
    def lens_after_editing_helper(self, code):
        root, base = fixture_repo(self, cli_app(code))
        head = commit(root, {"tool/helpers.py": "def shout(s):\n    return s.upper() + '!'\n"})
        return flowmap("lens", base, head, root=root)

    def test_graph_key_drives_reach(self):
        self.assertIn(REACH, self.lens_after_editing_helper('graph = ["tool"]'))

    def test_python_key_still_works(self):
        self.assertIn(REACH, self.lens_after_editing_helper('python = ["tool"]'))

    def test_no_graph_roots_means_no_reach(self):
        out = self.lens_after_editing_helper('tests = []')
        self.assertIn("# Flow lens:", out)
        self.assertNotIn("## Reach", out)

    def test_vendored_dirs_and_missing_roots_stay_out(self):
        files = cli_app('graph = ["tool", "later"]')
        files["tool/node_modules/dep/index.py"] = "def vendored():\n    pass\n"
        files["tool/.venv/lib/site.py"] = "def vendored():\n    pass\n"
        root, base = fixture_repo(self, files)
        for args in (("callgraph", "dump", base), ("callgraph", "dump")):
            with self.subTest(args=args):
                defs = json.loads(flowmap(*args, root=root))["defs"]
                self.assertIn("tool/helpers.py:shout", defs)
                self.assertEqual([d for d in defs if "node_modules" in d or ".venv" in d], [])
```

Run: `python3 -m unittest tests.test_graph_roots -v`
Expected: `test_graph_key_drives_reach` FAILS (no Reach line, because `graph` is ignored), and `test_vendored_dirs_and_missing_roots_stay_out` FAILS (`graph` ignored, so `defs` is empty). The other two pass.

- [ ] **Step 2: Add graph roots and graph files to `flowmap/config.py`**

In the module docstring, replace the `python = [...]` line with:

```
    graph = ["backend/app", "web/src"]         # call-graph sources (deterministic reach); `python` is the old name
```

In `load()`, change the `for k in ("python", "tests", "other"):` line to:

```python
    for k in ("graph", "python", "tests", "other"):
```

Replace `python_roots()` with:

```python
VENDORED = {"node_modules", ".venv", "venv", "__pycache__", ".next", "vendor"}


def graph_roots():
    """Directories the call graph is built from: [code].graph, plus its old name `python`."""
    code = load()["code"]
    return list(dict.fromkeys(code["graph"] + code["python"]))


def graph_files(ref=None):
    """Files under graph_roots() that some call-graph builder parses: at a git revision, or in
    the working tree (untracked files included) when ref is None. Vendored dirs never count."""
    import graphs  # late: graphs imports config
    roots, ext = graph_roots(), graphs.suffixes()
    if not roots:
        return []
    if ref:
        listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, "--", *roots], cwd=root(),
                                capture_output=True, text=True, check=True).stdout.splitlines()
    else:
        listed = [p.relative_to(root()).as_posix() for d in roots for p in sorted((root() / d).rglob("*"))
                  if p.is_file()]
    return [f for f in dict.fromkeys(listed) if f.endswith(ext) and not VENDORED.intersection(f.split("/"))]
```

In `app_dirs()`, change the first line of the body that builds `dirs` to:

```python
    dirs = graph_roots() + list(cfg["code"]["other"])
```

- [ ] **Step 3: Use `graph_files` everywhere the graph is built**

`flowmap/callgraph.py`, `Graph.__init__`: replace the temporary default with:

```python
        files = config.graph_files() if files is None else files
```

`flowmap/lens.py`, `graph_at`:

```python
def graph_at(ref):
    """The static call graph of the graph roots as they are at `ref`."""
    return Graph(read=lambda rel: show(ref, rel) or "", files=config.graph_files(ref))
```

`flowmap/lens.py`, `importers`: change `where = config.python_roots() or ["."]` to `where = config.graph_roots() or ["."]`.

`flowmap/lens.py`, in the Reach loop (line 286): change

```python
        if c not in graph.defs or not c.endswith(".py") and ".py:" not in c:
```

to

```python
        if c not in graph.defs:
```

`flowmap/lens.py`, line 321: change `if config.python_roots():` to `if config.graph_roots():`.

`flowmap/atlas.py`, in `overlay`, replace the three lines from `roots = config.python_roots()` to `g = Graph(...)` with:

```python
    g = lens.graph_at(head)
```

and delete `from callgraph import Graph  # noqa: E402` (nothing else in atlas uses it).

`flowmap/diagrams.py` needs no change: `Graph()` now defaults to `config.graph_files()`.

Run: `grep -n "python_roots\|endswith(\".py\")" flowmap/*.py`
Expected: no hits in `config.py`, `callgraph.py`, `lens.py`, `atlas.py` or `diagrams.py`. Hits in `adapters/` (CLI and FastAPI adapters, which are legitimately Python) and in `reconcile.py:100` (CLI module names for test detection) are fine.

- [ ] **Step 4: Switch this repo and the build skill to the new key**

`flowmap.toml`: change `python = ["flowmap"]` to `graph = ["flowmap"]`.

`skills/flowmap-build/SKILL.md:17`: change `and, for Python, \`python = [...]\`` to `and \`graph = [...]\` (the app's source dirs the call graph is built from; Python today)`.

- [ ] **Step 5: Run all the tests**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: all pass. The goldens stay unchanged even though this repo now uses `graph`, which shows the new key is equivalent.

- [ ] **Step 6: Smoke-test atlas and diagrams without overwriting committed docs**

Run: `bin/flowmap atlas --pr '6d9eaff..770f1a7=PR #1' && bin/flowmap diagrams && git status --short docs/flowmap && git checkout -- docs/flowmap`
Expected: `wrote docs/flowmap/atlas.html (…, 1 overlays)` and the diagrams output with no traceback. Then `git checkout` discards the regenerated docs. The repo's own map is refreshed separately.

- [ ] **Step 7: Commit**

```bash
git add flowmap/config.py flowmap/callgraph.py flowmap/lens.py flowmap/atlas.py flowmap.toml skills/flowmap-build/SKILL.md tests/test_graph_roots.py
git commit -m "config: [code].graph roots; lens, atlas and diagrams build the graph from any language"
```

---

### Task 4: `flowmap callgraph check`, which tells you whether handlers and graph nodes agree

**Files:**
- Modify: `flowmap/callgraph.py` (add `classify`, a `check` branch in `__main__`, docstring line)
- Modify: `bin/flowmap` (docstring)
- Modify: `README.md` (the *Adding a stack* section)
- Test: `tests/test_check.py`

**Interfaces:**
- Consumes: `config.graph_files()`, `graphs.builder_for`, `inventory.endpoints()`.
- Produces:
  - `callgraph.classify(eps: list[dict], defs: dict, parsed: set[str]) -> {"node": [...], "not graphed": [...], "broken": [...]}`
  - `flowmap callgraph check` exits 1 if anything is broken. Phases 2 and 3 use it as their acceptance test.

- [ ] **Step 1: Write the failing tests**

`tests/test_check.py`:

```python
import sys
import unittest

from tests.helpers import REPO, cli_app, fixture_repo, flowmap

sys.path.insert(0, str(REPO / "flowmap"))
import callgraph  # noqa: E402

NEXT_ROUTE = "export async function GET() {\n  return Response.json({ ok: true })\n}\n"


class ClassifyTest(unittest.TestCase):
    def test_sorts_handlers_by_whether_the_graph_can_walk_from_them(self):
        eps = [{"endpoint": "A", "handler": "a.py:f"}, {"endpoint": "B", "handler": "a.py:g"},
               {"endpoint": "C", "handler": "b.ts:GET"}]
        got = callgraph.classify(eps, {"a.py:f": (1, 2)}, {"a.py"})
        self.assertEqual({k: [e["endpoint"] for e in v] for k, v in got.items()},
                         {"node": ["A"], "not graphed": ["C"], "broken": ["B"]})


class CheckCommandTest(unittest.TestCase):
    def test_python_handlers_resolve(self):
        root, _ = fixture_repo(self, cli_app('graph = ["tool"]'))
        out = flowmap("callgraph", "check", root=root)
        self.assertIn("1 entry points: 1 handlers are graph nodes, 0 not graphed, 0 broken", out)

    def test_handler_without_builder_is_not_graphed_not_broken(self):
        files = cli_app('graph = ["tool"]', extra='\n[[entry]]\nadapter = "nextjs"\nroot = "web"\n')
        files["web/next.config.js"] = "module.exports = {}\n"
        files["web/app/api/ping/route.ts"] = NEXT_ROUTE
        root, _ = fixture_repo(self, files)
        out = flowmap("callgraph", "check", root=root)  # raises if it exits non-zero
        self.assertIn("2 entry points: 1 handlers are graph nodes, 1 not graphed, 0 broken", out)
        self.assertIn("NOT GRAPHED GET /api/ping -> web/app/api/ping/route.ts:GET (no builder for .ts)", out)
```

Run: `python3 -m unittest tests.test_check -v`
Expected: `AttributeError: module 'callgraph' has no attribute 'classify'`, and the command tests fail because `check` falls through to the stats line.

- [ ] **Step 2: Add `classify` and the `check` branch to `flowmap/callgraph.py`**

Add after `impact`:

```python
def classify(eps, defs, parsed):
    """Can the graph walk from each entry point's handler? 'node': yes. 'not graphed': its file
    is outside the graph roots or no builder parses that language yet (expected, not a fault).
    'broken': the file is parsed but has no such node, so the adapter and the builder spell the
    handler differently, and every reach number for that entry point is silently zero."""
    out = {"node": [], "not graphed": [], "broken": []}
    for e in eps:
        h = e["handler"]
        out["node" if h in defs else "broken" if h.rsplit(":", 1)[0] in parsed else "not graphed"].append(e)
    return out
```

In `__main__`, add this branch right after the `dump` branch, before `g = Graph()`:

```python
    if sys.argv[1:2] == ["check"]:
        import inventory
        files = config.graph_files()
        eps = inventory.endpoints()
        got = classify(eps, Graph(files=files).defs, set(files))
        print(f"{len(eps)} entry points: {len(got['node'])} handlers are graph nodes, "
              f"{len(got['not graphed'])} not graphed, {len(got['broken'])} broken")
        for e in got["not graphed"]:
            rel = e["handler"].rsplit(":", 1)[0]
            why = f"no builder for {Path(rel).suffix or rel}" if graphs.builder_for(rel) is None else "outside [code].graph"
            print(f"  NOT GRAPHED {e['endpoint']} -> {e['handler']} ({why})")
        for e in got["broken"]:
            print(f"  BROKEN {e['endpoint']} -> {e['handler']} (file is parsed, no such node)")
        sys.exit(1 if got["broken"] else 0)
```

Add this line to the module docstring's usage block:

```
    flowmap callgraph check                 is every entry point's handler a node the graph can walk from?
```

- [ ] **Step 3: Run the tests**

Run: `python3 -m unittest tests.test_check -v`
Expected: 3 pass.

- [ ] **Step 4: Run `check` on this repo**

Run: `bin/flowmap callgraph check`
Expected: `8 entry points: 8 handlers are graph nodes, 0 not graphed, 0 broken`, exit 0. (All 8 are `CLI flowmap <cmd>` with `file:__main__` handlers.)

- [ ] **Step 5: Update the docs**

`bin/flowmap` docstring: replace the `flowmap callgraph impact <file:sym>   which entry points can reach a symbol (Python)` line with:

```
  flowmap callgraph impact <file:sym>   which entry points can reach a symbol
  flowmap callgraph check               is every entry point's handler a call-graph node?
```

`README.md`, *Adding a stack* section: replace the paragraph with:

```markdown
Write `flowmap/adapters/<name>.py` with `entries(spec, read) -> [{"endpoint", "handler", "line",
"aliases"?}]`, register it in `adapters/__init__.py`, and add its guidance to `STACK` in
`flowmap/brief.py`. The `endpoint` string is the join key between passes, so derive it from code,
never from a model.

For deterministic reach, the language also needs a call-graph builder: `flowmap/graphs/<lang>.py`
with `EXT`, `build(files, read)`, `symbols(text)` and `signature(text, sym)` (see
`graphs/__init__.py`), registered in `BUILDERS`. Point `[code].graph` at its sources, then
`flowmap callgraph check` must report 0 broken: every handler the adapter emits has to be a node
the builder emits.
```

- [ ] **Step 6: Run the full suite and commit**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: all pass.

```bash
git add flowmap/callgraph.py bin/flowmap README.md tests/test_check.py
git commit -m "callgraph: check that every entry point's handler is a graph node"
```

---

## Follow-on plans (not in this plan)

- **Phase 2, the TypeScript/Next.js builder** (`graphs/typescript.py`). It runs `node` with the target repo's `node_modules/typescript` (`ts.createSourceFile`, syntax only) and passes file contents in as JSON on stdin. It resolves ES imports exactly, including `tsconfig` `paths` and barrel re-exports. JSX `<Comp/>` counts as a call, and a reference that isn't called (`action={fn}`) counts as an edge. Node ids must match the adapter's `rel:GET` and `rel:<DefaultName>`. Done when `callgraph check` reports 0 broken on a Next.js fixture app.
- **Phase 3, the Ruby/Rails builder** (`graphs/ruby.py`). It runs `ruby` with Ripper or Prism. Constants resolve to files by Zeitwerk naming. A bare `foo` resolves through the class, its concerns and its superclass. `before_action :x` becomes edges from every action, and `perform_later` becomes an edge to `#perform`. This phase also settles the handler spelling: today the Rails adapter emits `controller.rb:action` but the builder will naturally emit `UsersController.action`.
