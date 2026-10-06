"""Any stack: entry points are the matches of a regex the setup session writes for this repo.

    [[entry]]
    adapter = "pattern"
    files = ["svc/*.py"]                       # fnmatch globs on repo paths; `*` crosses directories
    match = '''@\\w+\\.(?P<verb>get|post)\\(\\s*["'](?P<path>[^"']*)'''
    endpoint = "{VERB} {path}"                 # {group}; {GROUP} upper-cases it; {a|b} first non-empty

The handler is the definition the match sits in (a def starts at its first decorator, so a
decorator match names the def it decorates), or, when the regex has a `handler` group, the
definition of that name in the same file (`app.get("/x", show)`). `{def}` is the handler's
own name, for tools named after their function. Symbols come from the call-graph builder,
else lens's regex outline, so handlers are spelled the way the graph spells nodes.
"""

import re
import subprocess
import sys
from fnmatch import fnmatch


def _files(globs, ref=None):
    from config import root
    cmd = ["git", "ls-tree", "-r", "--name-only", ref] if ref else ["git", "ls-files"]
    ls = subprocess.run(cmd, cwd=root(), capture_output=True, text=True).stdout.splitlines()
    return [f for f in ls if any(fnmatch(f, g) for g in globs)]


def _fill(template, groups):
    def one(m):
        for key in m[1].split("|"):
            val = groups.get(key) or (groups.get(key.lower()) or "").upper()
            if val:
                return val
        return ""
    return re.sub(r"\{([^}]+)\}", one, template)


def _handler(syms, line, name):
    """The innermost definition holding `line`, or the last one called `name` (by its own name)."""
    if name:
        named = [s for s in syms if s[2].rsplit(".", 1)[-1] == name]
        before = [s for s in named if s[0] <= line]
        return before[-1] if before else next(iter(named), None)
    return max((s for s in syms if s[0] <= line <= s[1]), key=lambda s: s[0], default=None)


def entries(spec, read):
    import lens  # late: lens imports the adapters
    rule = re.compile(spec["match"], re.M)
    out = []
    for rel in _files(spec["files"], getattr(read, "ref", None)):
        text = read(rel)
        if not text:
            continue
        syms = lens.defs(rel, text)
        for m in rule.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            groups = {k: v for k, v in m.groupdict().items() if v}
            sym = _handler(syms, line, groups.get("handler"))
            if sym is None:  # a match outside any definition names nothing the graph can walk
                print(f"flowmap: {rel}:{line} matches {spec['match']!r} but sits in no definition; skipped",
                      file=sys.stderr)
                continue
            groups["def"] = sym[2].rsplit(".", 1)[-1]
            out.append({"endpoint": _fill(spec["endpoint"], groups), "handler": f"{rel}:{sym[2]}", "line": line})
    return out
