"""FastAPI: routes declared with @router.<method>(path) and mounted via app.include_router."""

import ast
from pathlib import PurePosixPath

METHODS = {"get", "post", "put", "patch", "delete"}


def _str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _kw(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return _str(kw.value)
    return None


def _import_base(main, read):
    """Directory on sys.path for the app package: walk up while __init__.py exists."""
    d = PurePosixPath(main).parent
    while str(d) not in ("", ".") and read(f"{d}/__init__.py") is not None:
        d = d.parent
    return "" if str(d) in ("", ".") else f"{d}/"


def _mounts(main, read):
    """module -> prefix passed to include_router in the main file."""
    tree = ast.parse(read(main))
    alias_to_module = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                local = a.asname or a.name
                alias_to_module[local] = node.module if a.name == "router" else f"{node.module}.{a.name}"
    prefixes = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router" and node.args):
            target = node.args[0]
            # include_router(import_module(...).router) and friends can't be resolved statically;
            # their endpoints drop out of the inventory, which lens reports as a blind spot
            alias = (getattr(target.value, "id", None) if isinstance(target, ast.Attribute)
                     else getattr(target, "id", None))
            if alias in alias_to_module:
                prefixes[alias_to_module[alias]] = _kw(node, "prefix") or ""
    return prefixes


def entries(spec, read):
    main = spec["main"]
    base = _import_base(main, read)
    out = []
    for module, mount in _mounts(main, read).items():
        rel = base + module.replace(".", "/") + ".py"
        text = read(rel)
        if text is None:
            text = read(base + module.replace(".", "/") + "/__init__.py")
            rel = base + module.replace(".", "/") + "/__init__.py"
        if text is None:
            continue
        tree = ast.parse(text)
        router_prefix = {}
        for node in tree.body:
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                    and getattr(node.value.func, "id", None) == "APIRouter"):
                for t in node.targets:
                    router_prefix[t.id] = _kw(node.value, "prefix") or ""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr in METHODS and isinstance(dec.func.value, ast.Name)
                        and dec.func.value.id in router_prefix):
                    continue
                route = _str(dec.args[0]) if dec.args else ""
                out.append({
                    "endpoint": f"{dec.func.attr.upper()} {mount}{router_prefix[dec.func.value.id]}{route or ''}",
                    "handler": f"{rel}:{node.name}",
                    "line": node.lineno,
                })
    return out
