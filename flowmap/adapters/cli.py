"""Python CLIs: each command is a script with an `if __name__ == "__main__":` block.

    [[entry]]
    adapter = "cli"
    prog = "flowmap"          # the command users type; defaults to the commands dir name
    commands = "flowmap"      # dir: every top-level *.py with a __main__ block is a subcommand
    main = "tool.py"          # or a single-script CLI (either key, or both)

`commands` -> "CLI <prog> <module stem>"; `main` -> "CLI <prog>". The handler is
`<file>:__main__`, the guard block itself: the call graph models it as a node, so reach
works even when a command is dispatched by name (runpy, importlib).
"""

import ast
import subprocess


def main_guard(tree):
    """The module's top-level `if __name__ == "__main__":` statement, or None."""
    for node in tree.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == "__main__"):
            return node
    return None


def _files(base, ref=None):
    from config import root
    cmd = ["git", "ls-tree", "--name-only", ref, "--", f"{base}/"] if ref else ["git", "ls-files", "--", base]
    ls = subprocess.run(cmd, cwd=root(), capture_output=True, text=True)
    pre = f"{base}/"
    return [f for f in ls.stdout.splitlines()
            if f.endswith(".py") and f.startswith(pre) and "/" not in f[len(pre):]]


def _entry(rel, endpoint, read):
    text = read(rel)
    if text is None:
        return None
    try:
        guard = main_guard(ast.parse(text))
    except SyntaxError:
        return None
    if guard is None:
        return None
    return {"endpoint": endpoint, "handler": f"{rel}:__main__", "line": guard.lineno}


def entries(spec, read):
    out = []
    commands = spec.get("commands", "").strip("/")
    prog = spec.get("prog") or (commands.rsplit("/", 1)[-1] if commands else spec.get("main", "cli").rsplit("/", 1)[-1].removesuffix(".py"))
    if spec.get("main"):
        e = _entry(spec["main"], f"CLI {prog}", read)
        if e:
            out.append(e)
    if commands:
        for rel in _files(commands, getattr(read, "ref", None)):
            stem = rel.rsplit("/", 1)[-1].removesuffix(".py")
            e = _entry(rel, f"CLI {prog} {stem}", read)
            if e:
                out.append(e)
    return out
