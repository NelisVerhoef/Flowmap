"""Place a code change on the flow map.

Deterministic half of the PR lens: which flows and steps a diff touches, which
endpoints it adds or removes, which shared nodes it reaches (blast radius), and
which changed code the map has never heard of. The /pr-lens skill reads this
and writes the before/after and the questions.

    python tools/flowmap/lens.py <base> [<head>]      # e.g. main HEAD, or abc123^ abc123
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402
import graphs  # noqa: E402
import inventory  # noqa: E402
from callgraph import Graph  # noqa: E402

ROOT = config.root()
MAP = config.out() / "map.json"
_dirs = [d.rstrip("/") for d in config.app_dirs()]
CODE = re.compile(r"^(?:" + "|".join(re.escape(d) + "/" if d not in (".", "") else "" for d in _dirs) + r").*\.(py|rb|tsx?|jsx?|mjs)$")
TEST = re.compile(r"(^|/)(tests?|spec|__tests__)/|\.(test|spec)\.[jt]sx?$|_(test|spec)\.(py|rb)$|/test_[^/]*\.py$")
RB_DEF = re.compile(r"^(\s*)(?:def\s+(?:self\.)?([\w?!=]+)|class\s+([\w:]+)|module\s+([\w:]+))")
TS_DEF = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+(\w+)|(?:const|let)\s+(\w+)\s*[:=]|class\s+(\w+)|interface\s+(\w+)|type\s+(\w+)\s*=)")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def show(ref, rel):
    try:
        return git("show", f"{ref}:{rel}")
    except subprocess.CalledProcessError:
        return None


def ts_symbols(text):
    """Top-level-ish definitions; a definition runs until the next one starts."""
    starts = []
    for i, line in enumerate(text.splitlines(), 1):
        if line[:1] in (" ", "\t") and not line.lstrip().startswith("export"):
            continue
        m = TS_DEF.match(line)
        if m:
            starts.append((i, next(g for g in m.groups() if g)))
    total = text.count("\n") + 1
    return [(s, (starts[k + 1][0] - 1) if k + 1 < len(starts) else total, name)
            for k, (s, name) in enumerate(starts)]


def rb_symbols(text):
    """Ruby defs/classes/modules, closed by the `end` at the same indentation."""
    out, stack = [], []
    for i, line in enumerate(text.splitlines(), 1):
        m = RB_DEF.match(line)
        if m and not re.search(r"\bend\s*$", line[m.end():]):  # skip one-line `def x; end`
            name = next(g for g in m.groups()[1:] if g)
            prefix = ".".join(s[1] for s in stack if s[3])
            stack.append((len(m[1]), f"{prefix}.{name}" if prefix else name, i, not line.lstrip().startswith("def")))
        elif stack and re.match(r"^\s*end\b", line) and len(line) - len(line.lstrip()) == stack[-1][0]:
            indent, name, start, _ = stack.pop()
            out.append((start, i, name))
    return out


def defs(rel, text):
    """[(start, end, name)] for any supported language: its graph builder's parser if it has
    one, else a regex outline."""
    if not text:
        return []
    builder = graphs.builder_for(rel)
    if builder:
        return builder.symbols(text)
    return rb_symbols(text) if rel.endswith(".rb") else ts_symbols(text)


def symbols_at(rel, text, lines):
    if text is None or not lines:
        return set()
    syms = defs(rel, text)
    hit = set()
    for ln in lines:
        inner = [s for s in syms if s[0] <= ln <= s[1]]
        if inner:
            hit.add(max(inner, key=lambda s: s[0])[2])
        else:
            hit.add("<module>")
    return hit


def changed_lines(base, head):
    """rel -> (old_lines, new_lines) touched by the diff."""
    out = defaultdict(lambda: (set(), set()))
    rel = None
    for line in git("diff", "-U0", "--no-renames", base, head).splitlines():
        if line.startswith("+++ "):
            rel = line[6:] if line != "+++ /dev/null" else None
        elif line.startswith("--- ") and line != "--- /dev/null":
            rel = line[6:]
        elif line.startswith("@@") and rel:
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            o, oc, nw, nc = int(m[1]), int(m[2] or 1), int(m[3]), int(m[4] or 1)
            out[rel][0].update(range(o, o + oc))
            out[rel][1].update(range(nw, nw + nc))
    return out


def importers(ref, rel):
    """How many app files import this module: shared infrastructure the map may sit above."""
    if rel.endswith(".py"):
        mod = config.module_name(rel)
        if "." not in mod:
            return 0
        pat = rf"(from|import) {re.escape(mod)}\b|from {re.escape(mod.rsplit('.', 1)[0])} import {re.escape(mod.rsplit('.', 1)[1])}\b"
        where = config.python_roots() or ["."]
    elif rel.endswith(".rb"):
        return 0  # Ruby autoloads by constant name; import counting doesn't apply
    else:
        stem = Path(rel).with_suffix("").as_posix().split("/src/", 1)[-1]
        pat = rf"from ['\"][./@a-z]*{re.escape(stem.split('/')[-1])}['\"]"
        where = _dirs or ["."]
    try:
        hits = git("grep", "-lE", pat, ref, "--", *where)
    except subprocess.CalledProcessError:
        return 0
    return len([h for h in hits.splitlines() if not h.endswith(rel)])


def endpoint_set(ref):
    try:
        reader = lambda rel: show(ref, rel)  # noqa: E731
        reader.ref = ref
        return {e["endpoint"]: e["handler"] for e in inventory.endpoints(reader)}
    except SyntaxError:
        return {}


def graph_at(ref):
    """The static call graph of the Python roots as they are at `ref`."""
    roots = config.python_roots()
    files = [f for f in git("ls-tree", "-r", "--name-only", ref, "--", *roots).splitlines()
             if f.endswith(".py")] if roots else []
    return Graph(read=lambda rel: show(ref, rel) or "", files=files)


def reach_diff(old, new, old_eps, new_eps):
    """How the call graph moved between two revisions.

    old_eps/new_eps: endpoint -> handler node. Returns (edges added, edges removed,
    {symbol: (endpoints that newly reach it, endpoints that no longer do)}), counting only
    symbols and endpoints that exist on both sides: new code inherits its caller's reach and
    deleted code loses all of it, neither of which is news.
    """
    old_edges, new_edges = old.edge_set(), new.edge_set()
    added, removed = new_edges - old_edges, old_edges - new_edges
    # only endpoints that sit above a changed edge can have changed reach
    affected = set()
    for g, eps, edges in ((old, old_eps, removed), (new, new_eps, added)):
        above = set()
        for src in {a for a, _ in edges}:
            above |= g.callers(src) | {src}
        affected |= {e for e, h in eps.items() if h in above}
    both = old.defs.keys() & new.defs.keys()
    moved = defaultdict(lambda: (set(), set()))
    for e in affected & old_eps.keys() & new_eps.keys():
        before = old.callees(old_eps[e]) | {old_eps[e]}
        after = new.callees(new_eps[e]) | {new_eps[e]}
        for sym in (after - before) & both:
            moved[sym][0].add(e)
        for sym in (before - after) & both:
            moved[sym][1].add(e)
    return added, removed, dict(moved)


def main(base, head="HEAD"):
    the_map = json.loads(MAP.read_text())
    changes = changed_lines(base, head)
    files = sorted(changes)
    code = [f for f in files if CODE.match(f) and not TEST.search(f)]
    tests = [f for f in files if TEST.search(f)]

    changed = set()  # "rel:symbol"
    new_symbols = set()    # symbols that did not exist at base
    for rel in code:
        old, new = changes[rel]
        base_text = show(base, rel)
        base_syms = {sym for *_, sym in defs(rel, base_text)}
        for s in symbols_at(rel, show(head, rel), new) | symbols_at(rel, base_text, old):
            changed.add(f"{rel}:{s}")
            if s != "<module>" and s not in base_syms:
                new_symbols.add(f"{rel}:{s}")

    def hits(anchor):
        rel, sym = anchor.rsplit(":", 1)
        return any(c.rsplit(":", 1)[0] == rel and (c.rsplit(":", 1)[1] == sym
                   or c.rsplit(":", 1)[1].split(".")[-1] == sym.split(".")[-1]) for c in changed)

    base_eps, head_eps = endpoint_set(base), endpoint_set(head)
    handlers = {**base_eps, **head_eps}

    touched = []  # (flow, step, matched anchors)
    anchor_uses = defaultdict(list)
    for f in the_map["flows"]:
        for s in f["steps"]:
            anchors = s["ui"] + s["code_path"] + [handlers[e] for e in s["endpoints"] if e in handlers]
            for a in set(anchors):
                anchor_uses[a].append(f"{f['id']}/{s['id']}")
            matched = sorted(a for a in set(anchors) if hits(a))
            if matched:
                touched.append((f, s, matched))

    mapped = {a for a in anchor_uses if hits(a)}
    off_map = sorted(c for c in changed
                     if not any(c.rsplit(":", 1)[0] == a.rsplit(":", 1)[0]
                                and c.rsplit(":", 1)[1].split(".")[-1] == a.rsplit(":", 1)[1].split(".")[-1]
                                for a in mapped))

    out = [f"# Flow lens: `{base}..{head}`", "",
           f"{len(files)} files changed ({len(code)} app code, {len(tests)} tests, "
           f"{len(files) - len(code) - len(tests)} other) · {len(changed)} code symbols changed · "
           f"{len(touched)} map steps touched across {len({f['id'] for f, _, _ in touched})} flows", ""]

    added = sorted(set(head_eps) - set(base_eps))
    removed = sorted(set(base_eps) - set(head_eps))
    if added or removed:
        out += ["## Endpoint changes", ""]
        out += [f"- **added** `{e}` → `{head_eps[e]}`" for e in added]
        out += [f"- **removed** `{e}` (was `{base_eps[e]}`)" for e in removed]
        out.append("")

    out += ["## Flows and steps touched", ""]
    if not touched:
        out += ["_None — this change does not touch any code the map knows about._", ""]
    by_flow = defaultdict(list)
    for f, s, matched in touched:
        by_flow[f["id"]].append((s, matched))
    for fid, steps in by_flow.items():
        out.append(f"### {fid}")
        for s, matched in steps:
            out.append(f"- **{s['name']}** ({s['evidence']}, busy {s['busyness']['hops']}/"
                       f"{s['busyness']['files']}) — changed: " + ", ".join(f"`{a}`" for a in matched))
        out.append("")

    # Deterministic reach: walk the call graph backwards from every changed backend
    # symbol to the endpoints that can execute it, then up to map steps and flows.
    graph = graph_at(head)
    step_of = defaultdict(list)  # endpoint -> [(flow, step)]
    for f in the_map["flows"]:
        for s in f["steps"]:
            for e in s["endpoints"]:
                step_of[e].append((f["id"], s))
    handler_eps = defaultdict(list)
    for e, h in head_eps.items():
        handler_eps[h].append(e)
    anchored = {(f["id"], s["id"]) for f, s, _ in touched}
    reach = defaultdict(set)      # (flow, step id) -> changed symbols that reach it
    step_by_key, widest = {}, []
    for c in sorted(changed):
        if c not in graph.defs or not c.endswith(".py") and ".py:" not in c:
            continue
        eps = {e for n in graph.callers(c) | {c} for e in handler_eps.get(n, [])}
        flows = {fid for e in eps for fid, _ in step_of.get(e, [])}
        if eps and c not in new_symbols:
            # new helpers only inherit their caller's reach; modified existing code is the risk
            widest.append((len(eps), len(flows), c))
        for e in eps:
            for fid, s in step_of.get(e, []):
                if c not in new_symbols:
                    reach[(fid, s["id"])].add(c)
                step_by_key[(fid, s["id"])] = s
    hidden = {k: v for k, v in reach.items() if k not in anchored}
    if widest:
        out += ["## Reach (call graph, deterministic)", "",
                f"Changed backend code can execute under **{len(reach)} steps in "
                f"{len({k[0] for k in reach})} flows**; {len(hidden)} of those steps the map's own "
                "anchors did not show (hidden blast radius).", "",
                "Widest-reaching **modified** code (new code only inherits its caller's reach):", ""]
        for n_eps, n_flows, c in sorted(widest, reverse=True)[:8]:
            out.append(f"- `{c}` — reachable from {n_eps} endpoints in {n_flows} flows")
        if hidden:
            out += ["", "Steps reached but not anchored (look here):", ""]
            by_flow = defaultdict(list)
            for (fid, sid), syms in hidden.items():
                by_flow[fid].append((step_by_key[(fid, sid)]["name"], syms))
            for fid in sorted(by_flow):
                out.append(f"- **{fid}**")
                for name, syms in sorted(by_flow[fid]):
                    via = ", ".join(sorted(f"`{x.rsplit(':', 1)[1]}`" for x in syms)[:3])
                    out.append(f"  - {name} — via {via}")
        out.append("")

    # Reach diff: the call graph at base vs head. Catches a change that makes existing code
    # run under new endpoints (or stop running under old ones) without that code changing.
    if config.python_roots():
        added_edges, removed_edges, moved = reach_diff(graph_at(base), graph, base_eps, head_eps)
        short = lambda nid: f"{Path(nid.rsplit(':', 1)[0]).stem}.{nid.rsplit(':', 1)[1]}"  # noqa: E731
        flows_of = lambda eps: sorted({fid for e in eps for fid, _ in step_of.get(e, [])})  # noqa: E731
        anchors = set(anchor_uses)
        gained = {sym: g for sym, (g, _) in moved.items() if g}
        lost = {sym: lo for sym, (_, lo) in moved.items() if lo}
        if added_edges or removed_edges:
            out += ["## Reach diff (call graph, base → head)", "",
                    f"{len(added_edges)} call edges added, {len(removed_edges)} removed. "
                    f"Existing code newly reachable from some endpoint: **{len(gained)}**; "
                    f"no longer reachable from some endpoint: **{len(lost)}**.", ""]

            def listing(title, syms):
                if not syms:
                    return
                out.extend([title, ""])
                # widest first; map anchors break ties since they name a step
                for sym, eps in sorted(syms.items(), key=lambda kv: (-len(kv[1]), kv[0] not in anchors, kv[0]))[:10]:
                    names = ", ".join(f"`{e}`" for e in sorted(eps)[:3]) + (f" +{len(eps) - 3}" if len(eps) > 3 else "")
                    fl = flows_of(eps)
                    out.append(f"- `{sym}`{' (map anchor)' if sym in anchors else ''} — {names}"
                               + (f" · flows: {', '.join(fl)}" if fl else ""))
                if len(syms) > 10:
                    out.append(f"- … {len(syms) - 10} more")
                out.append("")
            listing("**Newly reachable** existing code (now runs under endpoints it didn't before):", gained)
            listing("**No longer reachable** (endpoints that stopped reaching it — a dropped check?):", lost)
            for title, edges in (("Edges added", sorted(added_edges)), ("Edges removed", sorted(removed_edges))):
                if edges:
                    out.append(f"{title}: " + ", ".join(f"`{short(a)}` → `{short(b)}`" for a, b in edges[:8])
                               + (f", … {len(edges) - 8} more" if len(edges) > 8 else ""))
            out.append("")

    if off_map:
        out += ["## Off-map changes (code the map doesn't know)", "",
                "New code, or a gap in the map. Either way: where does it sit in a flow?", ""]
        modified, new_syms = defaultdict(list), defaultdict(list)
        for c in off_map:
            rel, sym = c.rsplit(":", 1)
            if sym != "<module>":
                (new_syms if c in new_symbols else modified)[rel].append(sym)
        if modified:
            out += ["**Modified** — existing code changed; shared modules first:", ""]
            for rel, syms in sorted(modified.items(), key=lambda kv: -importers(head, kv[0])):
                n = importers(head, rel)
                reach = f" — **imported by {n} files**" if n >= 5 else ""
                out.append(f"- `{rel}`{reach}: " + ", ".join(f"`{s}`" for s in syms))
            out.append("")
        if new_syms:
            out += ["**New** — didn't exist before:", ""]
            for rel, syms in new_syms.items():
                out.append(f"- `{rel}`: " + ", ".join(f"`{s}`" for s in syms))
            out.append("")

    out += ["## Shape", "",
            f"- Steps touched: {len(touched)} · symbols changed: {len(changed)} · "
            f"ratio {len(changed) / max(1, len(touched)):.1f} symbols per step",
            f"- Tests changed: {len(tests)}" + (" — **no tests changed**" if code and not tests else ""),
            ""]
    print("\n".join(out))


if __name__ == "__main__":
    main(*sys.argv[1:3])
