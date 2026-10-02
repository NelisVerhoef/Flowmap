"""Rails: the route table as `bin/rails routes` prints it.

Rails' routing DSL (resources, scopes, concerns, constraints) is only reliably expanded by
Rails itself, so this adapter reads its output instead of parsing config/routes.rb:
- `routes_file = "tmp/routes.txt"` in the entry: parse a saved `bin/rails routes` dump
  (works anywhere, no Ruby needed — commit or regenerate it), else
- run `bin/rails routes` in the entry's root (needs the app's bundle installed).
Each route's handler is the controller action: app/controllers/<path>_controller.rb:<action>.
"""

import re
import subprocess
from pathlib import Path

LINE = re.compile(
    r"^\s*(?P<prefix>[a-z_0-9]+)?\s+(?P<verb>(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)(?:\|[A-Z|]+)?)"
    r"\s+(?P<path>/\S*)\s+(?P<target>[\w/]+#\w+)")
FRAMEWORK = ("rails/", "active_storage/", "action_mailbox/", "turbo/", "action_cable/")


def _routes_text(spec, root, read):
    if spec.get("routes_file"):
        rel = (Path(spec.get("root", ".")) / spec["routes_file"]).as_posix().removeprefix("./")
        text = read(rel)  # honours the git revision being inventoried
        return text if text is not None else (root / rel).read_text()
    try:
        return subprocess.run(["bin/rails", "routes"], cwd=root / spec.get("root", "."), capture_output=True,
                              text=True, check=True, timeout=180).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(
            f"rails adapter: could not run `bin/rails routes` ({exc}). Run it where the app boots and save "
            f"the output, e.g. `bin/rails routes > tmp/routes.txt`, then set routes_file in flowmap.toml.")


def _path(p):
    p = p.replace("(.:format)", "")
    p = re.sub(r"\(([^()]*)\)", r"\1", p)          # optional segments become plain
    p = re.sub(r"[:*](\w+)", r"{\1}", p)           # :id / *glob -> {id}
    return p.rstrip("/") or "/"


def _underscore(const):
    return "/".join(re.sub(r"(?<!^)(?=[A-Z])", "_", part).lower() for part in const.split("::"))


def _resolve(rel, action, read, prefix_dir, depth=0):
    """Where an action is really defined, in Ruby's lookup order: the controller itself, its
    included concerns, then its superclass chain. None when no `def` exists anywhere."""
    text = read(rel)
    if text is None or depth > 5:
        return None
    hit = re.search(rf"^\s*def\s+{re.escape(action)}\b", text, re.M)
    if hit:
        return rel, action, text[: hit.start()].count("\n") + 1
    for mod in re.findall(r"^\s*include\s+([\w:]+)", text, re.M):
        for cand in (f"{prefix_dir}app/controllers/concerns/{_underscore(mod)}.rb",
                     f"{prefix_dir}app/controllers/{_underscore(mod)}.rb"):
            found = _resolve(cand, action, read, prefix_dir, depth + 1)
            if found:
                return found
    sup = re.search(r"^\s*class\s+[\w:]+\s*<\s*([\w:]+)", text, re.M)
    if sup and sup[1] not in ("ActionController::Base", "ActionController::API"):
        return _resolve(f"{prefix_dir}app/controllers/{_underscore(sup[1])}.rb", action, read, prefix_dir, depth + 1)
    return None


def entries(spec, read):
    from config import root  # late import: adapters stay usable without the package layout
    base = spec.get("root", ".").strip("/")
    prefix_dir = "" if base in ("", ".") else base + "/"
    out, last_prefix = [], {}
    for line in _routes_text(spec, root(), read).splitlines():
        m = LINE.match(line)
        if not m:
            continue
        controller, action = m["target"].split("#")
        if controller.startswith(FRAMEWORK):
            continue
        rel = f"{prefix_dir}app/controllers/{controller}_controller.rb"
        if read(rel) is None:
            continue  # route served by a gem/engine, not this repo's code
        path = _path(m["path"])
        name = m["prefix"] or last_prefix.get(m["path"])
        if m["prefix"]:
            last_prefix[m["path"]] = m["prefix"]
        found = _resolve(rel, action, read, prefix_dir)
        if found:
            handler, line = f"{found[0]}:{found[1]}", found[2]
        else:  # implicit action: Rails renders the template; anchor on the controller class
            text = read(rel)
            cls = re.search(r"^\s*class\s+([\w:]+)", text, re.M)
            handler = f"{rel}:{cls[1].split('::')[-1]}" if cls else f"{rel}:{action}"
            line = text[: cls.start()].count("\n") + 1 if cls else 1
        for verb in m["verb"].split("|"):
            out.append({
                "endpoint": f"{verb} {path}",
                "handler": handler,
                "line": line,
                "aliases": [f"{name}_path", f"{name}_url"] if name else [],
                **({} if found else {"implicit": f"renders app/views/{controller}/{action}"}),
            })
    return out
